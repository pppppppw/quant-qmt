from __future__ import annotations

import json
import logging
import time
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Any

from quant_qmt.config import GatewayServerConfig, configure_import_paths
from quant_qmt.gateway.helpers import (
    build_account_info_payload,
    normalize_account_type,
    normalize_stock_code,
    now_iso,
    to_jsonable,
)


logger = logging.getLogger(__name__)

configure_import_paths()

settings = GatewayServerConfig.from_env()
xt_trader: Any | None = None
accounts: dict[str, Any] = {}
account_subscribed: dict[str, bool] = {}
qmt_connected = False
last_connect_attempt = 0.0

callback_events = deque(maxlen=max(100, settings.callback_buffer_size))
callback_events_lock = Lock()
callback_log_lock = Lock()

whole_quote_subscriptions: dict[tuple[str, ...], int] = {}
whole_quote_lock = Lock()
realtime_quote_cache: dict[str, dict[str, Any]] = {}
realtime_quote_cache_lock = Lock()

xtconstant_mod: Any | None = None
XtQuantTraderCls: Any | None = None
XtQuantTraderCallbackCls: Any | None = None
StockAccountCls: Any | None = None
callback_cls: Any | None = None


def reload_settings() -> GatewayServerConfig:
    global settings
    global callback_events

    settings = GatewayServerConfig.from_env()
    if callback_events.maxlen != max(100, settings.callback_buffer_size):
        callback_events = deque(list(callback_events), maxlen=max(100, settings.callback_buffer_size))
    return settings


def current_callback_log_file() -> str:
    return settings.callback_log_file


def account_key(account_id: str, account_type: str) -> str:
    return f"{account_id}_{account_type.upper()}"


def ensure_xttrader_imports() -> None:
    global xtconstant_mod
    global XtQuantTraderCls
    global XtQuantTraderCallbackCls
    global StockAccountCls

    if XtQuantTraderCls is not None and XtQuantTraderCallbackCls is not None and StockAccountCls is not None:
        return

    configure_import_paths()
    from xtquant import xtconstant as xtconstant_import
    from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
    from xtquant.xttype import StockAccount

    xtconstant_mod = xtconstant_import
    XtQuantTraderCls = XtQuantTrader
    XtQuantTraderCallbackCls = XtQuantTraderCallback
    StockAccountCls = StockAccount


def get_xtconstant() -> Any:
    ensure_xttrader_imports()
    return xtconstant_mod


def get_xtdata() -> tuple[Any | None, Exception | None]:
    try:
        configure_import_paths()
        from xtquant import xtdata

        return xtdata, None
    except Exception as exc:
        return None, exc


def is_connected() -> bool:
    return bool(qmt_connected and xt_trader is not None)


def record_callback(event_type: str, payload_obj: Any) -> None:
    event = {
        "event_type": event_type,
        "timestamp": now_iso(),
        "payload": to_jsonable(payload_obj),
    }
    with callback_events_lock:
        callback_events.append(event)

    callback_file = current_callback_log_file()
    if not callback_file:
        return

    try:
        log_path = Path(callback_file).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False)
        with callback_log_lock:
            with log_path.open("a", encoding="utf-8") as file_handle:
                file_handle.write(line + "\n")
    except Exception as exc:
        logger.warning("failed to write callback log: %s", exc)


def update_realtime_quote_cache(datas: dict[str, Any]) -> None:
    if not isinstance(datas, dict):
        return

    updated_at = now_iso()
    normalized_items: dict[str, dict[str, Any]] = {}
    for code, payload in datas.items():
        stock_code = normalize_stock_code(code)
        if not stock_code:
            continue
        item = to_jsonable(payload)
        if not isinstance(item, dict):
            item = {"raw": item}
        item["ts_code"] = stock_code
        item["updated_at"] = updated_at
        normalized_items[stock_code] = item

    if not normalized_items:
        return

    with realtime_quote_cache_lock:
        realtime_quote_cache.update(normalized_items)


def get_cached_realtime_quotes(code_list: list[str]) -> dict[str, dict[str, Any]]:
    normalized = [normalize_stock_code(code) for code in code_list if normalize_stock_code(code)]
    with realtime_quote_cache_lock:
        return {code: dict(realtime_quote_cache[code]) for code in normalized if code in realtime_quote_cache}


def ensure_whole_quote_subscription(xtdata: Any, code_list: list[str]) -> int | None:
    normalized = tuple(sorted({normalize_stock_code(code) for code in code_list if normalize_stock_code(code)}))
    if not normalized:
        return None

    with whole_quote_lock:
        existing = whole_quote_subscriptions.get(normalized)
        if existing and existing > 0:
            return existing
        if not hasattr(xtdata, "subscribe_whole_quote"):
            return None
        seq = xtdata.subscribe_whole_quote(list(normalized), callback=update_realtime_quote_cache)
        if isinstance(seq, int) and seq > 0:
            whole_quote_subscriptions[normalized] = seq
            return seq
        raise RuntimeError(f"subscribe_whole_quote failed: {seq}")


def build_callback_class() -> Any:
    global callback_cls
    if callback_cls is not None:
        return callback_cls

    ensure_xttrader_imports()

    class QmtCallback(XtQuantTraderCallbackCls):  # type: ignore[misc, valid-type]
        def on_disconnected(self):
            global qmt_connected
            logger.warning("QMT connection closed")
            qmt_connected = False
            record_callback("on_disconnected", {"qmt_connected": False})

        def on_account_status(self, status):
            record_callback("on_account_status", status)

        def on_stock_order(self, order):
            record_callback("on_stock_order", order)

        def on_stock_trade(self, trade):
            record_callback("on_stock_trade", trade)

        def on_stock_asset(self, asset):
            record_callback("on_stock_asset", asset)

        def on_stock_position(self, position):
            record_callback("on_stock_position", position)

        def on_order_error(self, order_error):
            record_callback("on_order_error", order_error)

        def on_cancel_error(self, cancel_error):
            record_callback("on_cancel_error", cancel_error)

        def on_order_stock_async_response(self, response):
            record_callback("on_order_stock_async_response", response)

    callback_cls = QmtCallback
    return callback_cls


def init_qmt() -> bool:
    global xt_trader
    global qmt_connected

    reload_settings()
    try:
        qmt_path = str(settings.qmt_path or "").strip()
        if not qmt_path:
            raise RuntimeError("QMT_PATH is required and must point to MiniQMT userdata_mini")
        qmt_dir = Path(qmt_path).expanduser()
        if not qmt_dir.exists():
            raise RuntimeError(f"QMT_PATH does not exist: {qmt_dir}")

        ensure_xttrader_imports()
        logger.info("initializing QMT trader: path=%s session_id=%s", qmt_dir, settings.session_id)
        xt_trader = XtQuantTraderCls(str(qmt_dir), settings.session_id)
        xt_trader.register_callback(build_callback_class()())
        xt_trader.start()
        result = xt_trader.connect()
        if result != 0:
            raise RuntimeError(f"connect failed: {result}")
        qmt_connected = True
        logger.info("QMT connection established")
        return True
    except Exception as exc:
        xt_trader = None
        qmt_connected = False
        logger.error("QMT initialization failed: %s", exc)
        return False


def try_reconnect(force: bool = False) -> bool:
    global last_connect_attempt
    global qmt_connected

    if is_connected():
        return True

    reload_settings()
    now = time.time()
    if not force and (now - last_connect_attempt) < settings.reconnect_interval:
        return False
    last_connect_attempt = now

    if xt_trader is None:
        return init_qmt()

    try:
        result = xt_trader.connect()
        if result == 0:
            qmt_connected = True
            logger.info("QMT reconnect succeeded")
            return True
        logger.error("QMT reconnect failed: %s", result)
    except Exception as exc:
        logger.error("QMT reconnect raised an exception: %s", exc)

    qmt_connected = False
    return False


def must_have_qmt_trader() -> None:
    if xt_trader is None:
        raise RuntimeError("QMT trader instance is not initialized")


def resolve_default_account_id(account_type: str = "STOCK") -> str:
    if settings.default_account_id:
        return settings.default_account_id

    for key in sorted(accounts.keys()):
        account_id, cached_type = key.rsplit("_", 1)
        if account_id and cached_type == account_type.upper():
            return account_id

    try:
        if xt_trader is not None and hasattr(xt_trader, "query_account_infos"):
            infos = xt_trader.query_account_infos() or []
            for info in infos:
                payload = build_account_info_payload(info)
                account_id = str(payload.get("account_id") or "").strip()
                if not account_id:
                    continue
                acc_type = normalize_account_type(payload.get("account_type"))
                key = account_key(account_id, acc_type)
                if key not in accounts:
                    accounts[key] = StockAccountCls(account_id, acc_type)
                return account_id
    except Exception as exc:
        logger.warning("failed to resolve default account id: %s", exc)
    return ""


def get_account(account_id: str, account_type: str = "STOCK", auto_subscribe: bool = True) -> Any:
    ensure_xttrader_imports()
    must_have_qmt_trader()

    normalized_id = str(account_id or "").strip()
    if not normalized_id:
        raise ValueError("account_id must not be empty")
    normalized_type = normalize_account_type(account_type)
    key = account_key(normalized_id, normalized_type)

    if key not in accounts:
        accounts[key] = StockAccountCls(normalized_id, normalized_type)

    if auto_subscribe and not account_subscribed.get(key, False):
        result = xt_trader.subscribe(accounts[key])
        if result == 0:
            account_subscribed[key] = True
        else:
            logger.warning(
                "account subscribe failed but execution will continue: account_id=%s account_type=%s result=%s",
                normalized_id,
                normalized_type,
                result,
            )
            account_subscribed[key] = False

    return accounts[key]


def resolve_stock_market_price_type(stock_code: str) -> int | None:
    xtconstant = get_xtconstant()
    suffix = str(stock_code or "").strip().upper().split(".")[-1]
    if suffix in {"SH", "SSE", "XSHG", "BJ", "BSE"}:
        return getattr(xtconstant, "MARKET_SH_CONVERT_5_CANCEL", None)
    if suffix in {"SZ", "SZSE", "XSHE"}:
        return getattr(xtconstant, "MARKET_SZ_CONVERT_5_CANCEL", None)
    return None


def resolve_price_type(price_type: Any, stock_code: str | None = None) -> int:
    xtconstant = get_xtconstant()
    if isinstance(price_type, int):
        return price_type
    text = str(price_type or "fix").strip().lower()
    latest_price = getattr(xtconstant, "LATEST_PRICE", None)
    market_price = resolve_stock_market_price_type(stock_code or "")
    mapping = {
        "fix": xtconstant.FIX_PRICE,
        "limit": xtconstant.FIX_PRICE,
        "latest": latest_price,
        "market": market_price or latest_price,
    }
    if text not in mapping or mapping[text] is None:
        raise ValueError("price_type only supports fix, market, latest, or native xt constants")
    return mapping[text]


def resolve_order_type(order_type: Any) -> int:
    xtconstant = get_xtconstant()
    if isinstance(order_type, int):
        return order_type
    text = str(order_type or "").strip().lower()
    mapping = {
        "buy": xtconstant.STOCK_BUY,
        "sell": xtconstant.STOCK_SELL,
        "stock_buy": xtconstant.STOCK_BUY,
        "stock_sell": xtconstant.STOCK_SELL,
    }
    if text not in mapping:
        raise ValueError("order_type only supports buy, sell, or native xt constants")
    return mapping[text]


def resolve_market(market: Any) -> int:
    xtconstant = get_xtconstant()
    if isinstance(market, int):
        return market
    text = str(market or "").strip().upper()
    market_map = {
        "SH": "SH_MARKET",
        "SSE": "SH_MARKET",
        "XSHG": "SH_MARKET",
        "1": "SH_MARKET",
        "SZ": "SZ_MARKET",
        "SZSE": "SZ_MARKET",
        "XSHE": "SZ_MARKET",
        "2": "SZ_MARKET",
    }
    name = market_map.get(text)
    if not name or not hasattr(xtconstant, name):
        raise ValueError("market only supports SH/SZ, 1/2, or native xt constants")
    return getattr(xtconstant, name)


def build_position_payload(pos: Any) -> dict[str, Any]:
    volume = getattr(pos, "volume", None)
    avg_price = getattr(pos, "avg_price", None)
    market_value = getattr(pos, "market_value", None)
    profit_loss = getattr(pos, "position_profit", None)
    if profit_loss is None:
        try:
            if volume is not None and avg_price is not None and market_value is not None:
                profit_loss = float(market_value) - float(volume) * float(avg_price)
        except Exception:
            profit_loss = None
    stock_code = getattr(pos, "stock_code", None)
    return {
        "stock_code": stock_code,
        "ts_code": stock_code,
        "stock_name": getattr(pos, "instrument_name", None),
        "volume": volume,
        "available_volume": getattr(pos, "can_use_volume", getattr(pos, "available_volume", None)),
        "cost_price": avg_price,
        "open_price": getattr(pos, "open_price", None),
        "last_price": getattr(pos, "last_price", None),
        "market_value": market_value,
        "profit_loss": profit_loss,
        "profit_rate": getattr(pos, "profit_rate", None),
        "float_profit": getattr(pos, "float_profit", None),
        "direction": getattr(pos, "direction", None),
        "offset_flag": getattr(pos, "offset_flag", None),
        "secu_account": getattr(pos, "secu_account", None),
        "open_date": getattr(pos, "open_date", None),
    }


def build_order_payload(order: Any) -> dict[str, Any]:
    stock_code = getattr(order, "stock_code", None)
    return {
        "order_id": getattr(order, "order_id", None),
        "order_sysid": getattr(order, "order_sysid", None),
        "stock_code": stock_code,
        "ts_code": stock_code,
        "stock_name": getattr(order, "instrument_name", None),
        "order_type": getattr(order, "order_type", None),
        "order_status": getattr(order, "order_status", None),
        "order_time": getattr(order, "order_time", None),
        "price": getattr(order, "price", None),
        "volume": getattr(order, "order_volume", None),
        "filled_volume": getattr(order, "traded_volume", None),
        "status_msg": getattr(order, "status_msg", None),
        "strategy_name": getattr(order, "strategy_name", None),
        "order_remark": getattr(order, "order_remark", None),
        "direction": getattr(order, "direction", None),
        "offset_flag": getattr(order, "offset_flag", None),
        "secu_account": getattr(order, "secu_account", None),
    }


def build_trade_payload(trade: Any) -> dict[str, Any]:
    stock_code = getattr(trade, "stock_code", None)
    return {
        "traded_id": getattr(trade, "traded_id", None),
        "order_id": getattr(trade, "order_id", None),
        "order_sysid": getattr(trade, "order_sysid", None),
        "stock_code": stock_code,
        "ts_code": stock_code,
        "stock_name": getattr(trade, "instrument_name", None),
        "traded_time": getattr(trade, "traded_time", None),
        "traded_price": getattr(trade, "traded_price", None),
        "traded_volume": getattr(trade, "traded_volume", None),
        "traded_amount": getattr(trade, "traded_amount", None),
        "order_type": getattr(trade, "order_type", None),
        "strategy_name": getattr(trade, "strategy_name", None),
        "order_remark": getattr(trade, "order_remark", None),
        "direction": getattr(trade, "direction", None),
        "offset_flag": getattr(trade, "offset_flag", None),
        "secu_account": getattr(trade, "secu_account", None),
        "commission": getattr(trade, "commission", None),
    }
