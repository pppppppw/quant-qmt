from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from quant_qmt import __version__
from quant_qmt.config import ClientConfig, configure_import_paths, public_env_snapshot
from quant_qmt.gateway import run_gateway
from quant_qmt.sdk import QmtGatewayClient
from quant_qmt.strategy.small_cap_proxy import (
    DEFAULT_A_STOCK_SECTOR,
    SmallCapEnhancedProxyConfig,
    run_small_cap_enhanced_proxy_demo,
)


def _json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _print(data: Any) -> None:
    print(_json_text(data))


def _write_output(data: Any, output: str) -> None:
    path = Path(output).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(_json_text(data) + "\n", encoding="utf-8")
        return
    if not isinstance(data, list):
        raise ValueError(f"{path.name} only supports JSON for object payloads")
    frame = pd.DataFrame(data)
    if suffix == ".csv":
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        return
    if suffix == ".parquet":
        frame.to_parquet(path, index=False)
        return
    raise ValueError(f"unsupported output format: {path.suffix}")


def _apply_common_env(args: argparse.Namespace) -> None:
    if getattr(args, "base_url", None):
        os.environ["QMT_GATEWAY_URL"] = str(args.base_url)
    if getattr(args, "xtquant_path", None):
        os.environ["QMT_XTQUANT_PATH"] = str(args.xtquant_path)
    if getattr(args, "pythonpath", None):
        os.environ["QMT_PYTHONPATH"] = str(args.pythonpath)
    if getattr(args, "qmt_path", None):
        os.environ["QMT_PATH"] = str(args.qmt_path)
    if getattr(args, "session_id", None) is not None:
        os.environ["QMT_SESSION_ID"] = str(args.session_id)
    if getattr(args, "host", None):
        os.environ["QMT_GATEWAY_HOST"] = str(args.host)
    if getattr(args, "port", None) is not None:
        os.environ["QMT_GATEWAY_PORT"] = str(args.port)
    if getattr(args, "callback_log_file", None):
        os.environ["QMT_CALLBACK_LOG_FILE"] = str(args.callback_log_file)
    if getattr(args, "default_account_id", None):
        os.environ["QMT_DEFAULT_ACCOUNT_ID"] = str(args.default_account_id)


def _client_from_args(args: argparse.Namespace) -> QmtGatewayClient:
    _apply_common_env(args)
    config = ClientConfig.from_env()
    timeout = getattr(args, "timeout", None) or config.timeout
    return QmtGatewayClient(base_url=config.base_url, timeout=timeout)


def _resolve_account_id(
    client: QmtGatewayClient,
    requested_account_id: str,
    *,
    account_type: str,
) -> tuple[str, list[dict[str, Any]]]:
    infos = client.query_account_infos()
    if requested_account_id.strip():
        return requested_account_id.strip(), infos
    for item in infos:
        account_id = str(item.get("account_id") or "").strip()
        candidate_type = str(item.get("account_type") or "").strip().upper()
        if account_id and (not candidate_type or candidate_type == account_type.upper()):
            return account_id, infos
    for item in infos:
        account_id = str(item.get("account_id") or "").strip()
        if account_id:
            return account_id, infos
    return "", infos


def cmd_doctor(args: argparse.Namespace) -> int:
    _apply_common_env(args)
    report: dict[str, Any] = {
        "tool": "quant-qmt doctor",
        "version": __version__,
        "python": {
            "version": sys.version,
            "executable": sys.executable,
        },
        "platform": platform.platform(),
        "env": public_env_snapshot(),
        "checks": {},
        "warnings": [],
        "errors": [],
    }

    qmt_path = os.getenv("QMT_PATH", "").strip()
    report["checks"]["qmt_path"] = {"value": qmt_path, "exists": bool(qmt_path and Path(qmt_path).exists())}
    if qmt_path and not Path(qmt_path).exists():
        report["errors"].append(f"QMT_PATH does not exist: {qmt_path}")
    if not qmt_path:
        report["warnings"].append("QMT_PATH is not set")

    added_paths = configure_import_paths()
    report["checks"]["import_paths_added"] = added_paths

    try:
        import xtquant  # type: ignore

        report["checks"]["xtquant"] = {
            "ok": True,
            "file": getattr(xtquant, "__file__", ""),
        }
    except Exception as exc:
        report["checks"]["xtquant"] = {"ok": False, "error": str(exc)}
        report["errors"].append(f"xtquant import failed: {exc}")
        report["warnings"].append(
            "On the Windows gateway host, first try `pip install xtquant`. "
            "If you prefer the broker-bundled runtime, set QMT_XTQUANT_PATH or rely on auto-discovery from QMT_PATH."
        )

    try:
        from xtquant import xtdata  # type: ignore

        report["checks"]["xtdata"] = {"ok": True}
        if hasattr(xtdata, "get_stock_list_in_sector"):
            try:
                items = xtdata.get_stock_list_in_sector(DEFAULT_A_STOCK_SECTOR)
                report["checks"]["xtdata"]["a_share_sector_count"] = len(items or [])
            except Exception as exc:
                report["checks"]["xtdata"]["sector_probe_error"] = str(exc)
                report["warnings"].append(f"xtdata sector probe failed: {exc}")
    except Exception as exc:
        report["checks"]["xtdata"] = {"ok": False, "error": str(exc)}
        report["errors"].append(f"xtdata import failed: {exc}")

    if args.check_gateway:
        client = _client_from_args(args)
        gateway_checks: dict[str, Any] = {}
        try:
            gateway_checks["health"] = client.health()
        except Exception as exc:
            gateway_checks["health_error"] = str(exc)
            report["errors"].append(f"gateway health failed: {exc}")
        try:
            gateway_checks["data_health"] = client.data_health()
        except Exception as exc:
            gateway_checks["data_health_error"] = str(exc)
            report["warnings"].append(f"gateway data health failed: {exc}")
        report["checks"]["gateway"] = gateway_checks

    report["status"] = "ok" if not report["errors"] else "error"
    _print(report)
    return 0 if not report["errors"] else 1


def cmd_gateway_start(args: argparse.Namespace) -> int:
    _apply_common_env(args)
    run_gateway(host=args.host, port=args.port)
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    report: dict[str, Any] = {"tool": "quant-qmt smoke", "steps": []}

    def record(name: str, data: Any) -> None:
        report["steps"].append({"name": name, "ok": True, "data": data})

    health = client.health()
    if not health.get("qmt_connected"):
        raise RuntimeError(f"health check reported qmt_connected=false: {health}")
    record("health", health)

    data_health = client.data_health()
    record("data_health", data_health)

    kline = client.get_kline_rows(
        [args.stock_code],
        period="1d",
        count=args.kline_count,
        dividend_type="none",
        fill_data=True,
        download=True,
    )
    record("kline_rows", {"count": kline.get("count", 0)})

    full_tick = client.get_full_tick([args.stock_code], subscribe=True)
    record("full_tick", {"count": full_tick.get("count", 0)})

    realtime_cache = client.get_realtime_cache([args.stock_code], subscribe=True, fill_missing=True)
    record("realtime_cache", {"cached_count": realtime_cache.get("cached_count", 0)})

    if args.cb_code:
        cb_info = client.get_cb_info([args.cb_code], refresh=True)
        record("cb_info", {"count": cb_info.get("count", 0)})

    account_id, account_infos = _resolve_account_id(client, args.account_id, account_type=args.account_type)
    record("query_account_infos", {"count": len(account_infos), "account_id": account_id})

    if account_id:
        subscribe_result = client.subscribe_account(account_id, args.account_type)
        record("account_subscribe", subscribe_result)
        record("query_asset", client.query_asset(account_id, args.account_type))
        record("query_positions", {"count": len(client.query_positions(account_id, args.account_type))})
        record("query_orders", {"count": len(client.query_orders(account_id, args.account_type))})
        record("query_trades", {"count": len(client.query_trades(account_id, args.account_type))})

        if args.place_order:
            order_result = client.order_stock(
                account_id=account_id,
                account_type=args.account_type,
                stock_code=args.stock_code,
                order_type="buy",
                volume=args.volume,
                price_type="fix",
                price=args.price,
                strategy_name="quant_qmt_smoke",
                order_remark="quant_qmt_smoke_order",
            )
            order_id = int(order_result.get("order_id"))
            record("order_stock", order_result)

            single_order = client.query_order(account_id, order_id, args.account_type)
            if not single_order or not single_order.get("order_id"):
                orders = client.query_orders(account_id, args.account_type)
                single_order = next((item for item in orders if int(item.get("order_id") or 0) == order_id), single_order)
            record("query_order", single_order)

            cancel_payload: dict[str, Any] = {"account_id": account_id, "account_type": args.account_type}
            if args.cancel_by == "order_sysid":
                order_sysid = str((single_order or {}).get("order_sysid") or "").strip()
                if not order_sysid:
                    raise RuntimeError("cancel_by=order_sysid but order_sysid is empty")
                cancel_payload["order_sysid"] = order_sysid
                cancel_payload["market"] = "SH" if str(args.stock_code).upper().endswith(".SH") else "SZ"
            else:
                cancel_payload["order_id"] = order_id
            cancel_result = client.cancel_order(**cancel_payload)
            record("cancel_order", cancel_result)
    else:
        message = "no account_id was provided or discovered; account-level steps were skipped"
        if args.require_account:
            raise RuntimeError(message)
        record("account_steps_skipped", {"message": message})

    callbacks = client.recent_callbacks(limit=20)
    record("callbacks_recent", {"count": callbacks.get("count", 0)})

    if args.output:
        _write_output(report, args.output)
    _print(report)
    return 0


def cmd_data_sector(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.sector_stocks(args.sector_name)
    if args.output:
        items = [{"ts_code": code} for code in result.get("items", [])]
        if Path(args.output).suffix.lower() == ".json":
            _write_output(result, args.output)
        else:
            _write_output(items, args.output)
    _print(result)
    return 0


def cmd_data_kline(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    stock_list = [item.strip() for item in args.stock_list.split(",") if item.strip()]
    result = client.get_kline_rows(
        stock_list,
        period=args.period,
        start_time=args.start_time,
        end_time=args.end_time,
        count=args.count,
        dividend_type=args.dividend_type,
        fill_data=not args.no_fill_data,
        download=not args.no_download,
    )
    if args.output:
        if Path(args.output).suffix.lower() == ".json":
            _write_output(result, args.output)
        else:
            _write_output(result.get("rows", []), args.output)
    _print({"count": result.get("count", 0), "period": result.get("period"), "rows_preview": result.get("rows", [])[:5]})
    return 0


def cmd_data_cb_info(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    stock_list = [item.strip() for item in args.stock_list.split(",") if item.strip()] if args.stock_list else None
    result = client.get_cb_info(stock_list, refresh=not args.no_refresh)
    if args.output:
        if Path(args.output).suffix.lower() == ".json":
            _write_output(result, args.output)
        else:
            _write_output(result.get("items", []), args.output)
    _print({"count": result.get("count", 0), "items_preview": result.get("items", [])[:5]})
    return 0


def cmd_data_full_tick(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    stock_list = [item.strip() for item in args.stock_list.split(",") if item.strip()]
    result = client.get_full_tick(stock_list, subscribe=not args.no_subscribe)
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_data_realtime_cache(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    stock_list = [item.strip() for item in args.stock_list.split(",") if item.strip()]
    result = client.get_realtime_cache(
        stock_list,
        subscribe=not args.no_subscribe,
        fill_missing=not args.no_fill_missing,
    )
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_account_infos(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.query_account_infos()
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_subscribe(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.subscribe_account(args.account_id, args.account_type)
    _print(result)
    return 0


def cmd_trade_asset(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.query_asset(args.account_id, args.account_type)
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_positions(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.query_positions(args.account_id, args.account_type)
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_position(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.query_position(args.account_id, args.stock_code, args.account_type)
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_orders(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.query_orders(args.account_id, args.account_type, cancelable_only=args.cancelable_only)
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_order_info(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.query_order(args.account_id, args.order_id, args.account_type)
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_trades(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    result = client.query_trades(args.account_id, args.account_type)
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_order(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    price_type = str(args.price_type or "fix").strip().lower()
    if price_type in {"fix", "limit"} and (args.price is None or float(args.price) <= 0):
        raise ValueError("price must be > 0 for limit orders")
    price = float(args.price if args.price is not None else 0.0)
    result = client.order_stock(
        account_id=args.account_id,
        account_type=args.account_type,
        stock_code=args.stock_code,
        order_type=args.order_type,
        volume=args.volume,
        price_type=args.price_type,
        price=price,
        strategy_name=args.strategy_name,
        order_remark=args.order_remark,
        async_mode=args.async_mode,
    )
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_trade_cancel(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    if args.order_id is None and not str(args.order_sysid or "").strip():
        raise ValueError("either order_id or order_sysid must be provided")
    if args.order_id is None and str(args.order_sysid or "").strip() and not str(args.market or "").strip():
        raise ValueError("market is required when cancelling by order_sysid")
    result = client.cancel_order(
        account_id=args.account_id,
        account_type=args.account_type,
        order_id=args.order_id,
        order_sysid=args.order_sysid,
        market=args.market,
        async_mode=args.async_mode,
    )
    if args.output:
        _write_output(result, args.output)
    _print(result)
    return 0


def cmd_demo_small_cap(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    config = SmallCapEnhancedProxyConfig(
        size_lookback_days=args.size_lookback_days,
        liquidity_lookback_days=args.liquidity_lookback_days,
        momentum_lookback_days=args.momentum_lookback_days,
        skip_recent_days=args.skip_recent_days,
        volatility_lookback_days=args.volatility_lookback_days,
        min_liquidity_amount=args.min_liquidity_amount,
        min_liquidity_percentile=args.min_liquidity_percentile,
        min_price=args.min_price,
        min_history_days=args.min_history_days,
        exclude_bj=not args.include_bj,
        exclude_kcb=args.exclude_kcb,
        top_k=args.top_n,
    )
    result = run_small_cap_enhanced_proxy_demo(
        client,
        sector_name=args.sector_name,
        stock_limit=args.stock_limit,
        lookback_days=args.lookback_days,
        top_n=args.top_n,
        order_type=args.order_type,
        price_type=args.price_type,
        price_offset_bps=args.price_offset_bps,
        budget_per_order=args.budget_per_order,
        lot_size=args.lot_size,
        account_id=args.account_id,
        account_type=args.account_type,
        submit=args.submit,
        dedupe=not args.no_dedupe,
        strategy_name=args.strategy_name,
        order_remark_prefix=args.order_remark_prefix,
        config=config,
    )
    if args.plan_output:
        _write_output(result, args.plan_output)
    if args.orders_output:
        _write_output(result.get("planned_orders", []), args.orders_output)
    _print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant-qmt", description="Quant-QMT gateway, SDK, and demo CLI")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Inspect local runtime and optional gateway connectivity")
    doctor.add_argument("--qmt-path", default=os.getenv("QMT_PATH", ""))
    doctor.add_argument("--xtquant-path", default=os.getenv("QMT_XTQUANT_PATH", ""))
    doctor.add_argument("--pythonpath", default=os.getenv("QMT_PYTHONPATH", ""))
    doctor.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    doctor.add_argument("--check-gateway", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    gateway = subparsers.add_parser("gateway", help="Gateway lifecycle commands")
    gateway_sub = gateway.add_subparsers(dest="gateway_command", required=True)
    gateway_start = gateway_sub.add_parser("start", help="Start the Windows QMT gateway")
    gateway_start.add_argument("--host", default=os.getenv("QMT_GATEWAY_HOST", "127.0.0.1"))
    gateway_start.add_argument("--port", type=int, default=int(os.getenv("QMT_GATEWAY_PORT", "9527")))
    gateway_start.add_argument("--qmt-path", default=os.getenv("QMT_PATH", ""))
    gateway_start.add_argument("--session-id", type=int, default=int(os.getenv("QMT_SESSION_ID", "123456")))
    gateway_start.add_argument("--callback-log-file", default=os.getenv("QMT_CALLBACK_LOG_FILE", ""))
    gateway_start.add_argument("--xtquant-path", default=os.getenv("QMT_XTQUANT_PATH", ""))
    gateway_start.add_argument("--pythonpath", default=os.getenv("QMT_PYTHONPATH", ""))
    gateway_start.add_argument("--default-account-id", default=os.getenv("QMT_DEFAULT_ACCOUNT_ID", ""))
    gateway_start.set_defaults(func=cmd_gateway_start)

    smoke = subparsers.add_parser("smoke", help="Run an end-to-end smoke check against the gateway")
    smoke.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    smoke.add_argument("--timeout", type=int, default=15)
    smoke.add_argument("--account-id", default="")
    smoke.add_argument("--account-type", default="STOCK")
    smoke.add_argument("--require-account", action="store_true")
    smoke.add_argument("--stock-code", default="600000.SH")
    smoke.add_argument("--cb-code", default="")
    smoke.add_argument("--kline-count", type=int, default=5)
    smoke.add_argument("--place-order", action="store_true")
    smoke.add_argument("--price", type=float, default=10.0)
    smoke.add_argument("--volume", type=int, default=100)
    smoke.add_argument("--cancel-by", choices=["order_id", "order_sysid"], default="order_id")
    smoke.add_argument("--output", default="")
    smoke.set_defaults(func=cmd_smoke)

    data = subparsers.add_parser("data", help="Data helpers")
    data_sub = data.add_subparsers(dest="data_command", required=True)
    data_sector = data_sub.add_parser("sector", help="Fetch a sector universe from xtdata")
    data_sector.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    data_sector.add_argument("--timeout", type=int, default=15)
    data_sector.add_argument("--sector-name", default=DEFAULT_A_STOCK_SECTOR)
    data_sector.add_argument("--output", default="")
    data_sector.set_defaults(func=cmd_data_sector)

    data_kline = data_sub.add_parser("kline", help="Fetch kline rows from the gateway")
    data_kline.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    data_kline.add_argument("--timeout", type=int, default=15)
    data_kline.add_argument("--stock-list", required=True, help="Comma-separated stock list")
    data_kline.add_argument("--period", default="1d")
    data_kline.add_argument("--start-time", default="")
    data_kline.add_argument("--end-time", default="")
    data_kline.add_argument("--count", type=int, default=-1)
    data_kline.add_argument("--dividend-type", default="none")
    data_kline.add_argument("--no-fill-data", action="store_true")
    data_kline.add_argument("--no-download", action="store_true")
    data_kline.add_argument("--output", default="")
    data_kline.set_defaults(func=cmd_data_kline)

    data_cb_info = data_sub.add_parser("cb-info", help="Fetch convertible bond base information")
    data_cb_info.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    data_cb_info.add_argument("--timeout", type=int, default=30)
    data_cb_info.add_argument("--stock-list", default="", help="Optional comma-separated bond list")
    data_cb_info.add_argument("--no-refresh", action="store_true")
    data_cb_info.add_argument("--output", default="")
    data_cb_info.set_defaults(func=cmd_data_cb_info)

    data_full_tick = data_sub.add_parser("full-tick", help="Fetch full tick snapshots")
    data_full_tick.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    data_full_tick.add_argument("--timeout", type=int, default=15)
    data_full_tick.add_argument("--stock-list", required=True, help="Comma-separated stock list")
    data_full_tick.add_argument("--no-subscribe", action="store_true")
    data_full_tick.add_argument("--output", default="")
    data_full_tick.set_defaults(func=cmd_data_full_tick)

    data_realtime = data_sub.add_parser("realtime-cache", help="Read realtime cache snapshots")
    data_realtime.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    data_realtime.add_argument("--timeout", type=int, default=15)
    data_realtime.add_argument("--stock-list", required=True, help="Comma-separated stock list")
    data_realtime.add_argument("--no-subscribe", action="store_true")
    data_realtime.add_argument("--no-fill-missing", action="store_true")
    data_realtime.add_argument("--output", default="")
    data_realtime.set_defaults(func=cmd_data_realtime_cache)

    trade = subparsers.add_parser("trade", help="Trade and account helpers")
    trade_sub = trade.add_subparsers(dest="trade_command", required=True)

    trade_infos = trade_sub.add_parser("account-infos", help="Query available account infos")
    trade_infos.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_infos.add_argument("--timeout", type=int, default=15)
    trade_infos.add_argument("--output", default="")
    trade_infos.set_defaults(func=cmd_trade_account_infos)

    trade_subscribe = trade_sub.add_parser("subscribe", help="Subscribe an account")
    trade_subscribe.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_subscribe.add_argument("--timeout", type=int, default=15)
    trade_subscribe.add_argument("--account-id", required=True)
    trade_subscribe.add_argument("--account-type", default="STOCK")
    trade_subscribe.set_defaults(func=cmd_trade_subscribe)

    trade_asset = trade_sub.add_parser("asset", help="Query stock asset")
    trade_asset.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_asset.add_argument("--timeout", type=int, default=15)
    trade_asset.add_argument("--account-id", required=True)
    trade_asset.add_argument("--account-type", default="STOCK")
    trade_asset.add_argument("--output", default="")
    trade_asset.set_defaults(func=cmd_trade_asset)

    trade_positions = trade_sub.add_parser("positions", help="Query positions")
    trade_positions.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_positions.add_argument("--timeout", type=int, default=15)
    trade_positions.add_argument("--account-id", required=True)
    trade_positions.add_argument("--account-type", default="STOCK")
    trade_positions.add_argument("--output", default="")
    trade_positions.set_defaults(func=cmd_trade_positions)

    trade_position = trade_sub.add_parser("position", help="Query a single position")
    trade_position.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_position.add_argument("--timeout", type=int, default=15)
    trade_position.add_argument("--account-id", required=True)
    trade_position.add_argument("--account-type", default="STOCK")
    trade_position.add_argument("--stock-code", required=True)
    trade_position.add_argument("--output", default="")
    trade_position.set_defaults(func=cmd_trade_position)

    trade_orders = trade_sub.add_parser("orders", help="Query orders")
    trade_orders.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_orders.add_argument("--timeout", type=int, default=15)
    trade_orders.add_argument("--account-id", required=True)
    trade_orders.add_argument("--account-type", default="STOCK")
    trade_orders.add_argument("--cancelable-only", action="store_true")
    trade_orders.add_argument("--output", default="")
    trade_orders.set_defaults(func=cmd_trade_orders)

    trade_order_info = trade_sub.add_parser("order-info", help="Query a single order")
    trade_order_info.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_order_info.add_argument("--timeout", type=int, default=15)
    trade_order_info.add_argument("--account-id", required=True)
    trade_order_info.add_argument("--account-type", default="STOCK")
    trade_order_info.add_argument("--order-id", type=int, required=True)
    trade_order_info.add_argument("--output", default="")
    trade_order_info.set_defaults(func=cmd_trade_order_info)

    trade_trades = trade_sub.add_parser("trades", help="Query trades")
    trade_trades.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_trades.add_argument("--timeout", type=int, default=15)
    trade_trades.add_argument("--account-id", required=True)
    trade_trades.add_argument("--account-type", default="STOCK")
    trade_trades.add_argument("--output", default="")
    trade_trades.set_defaults(func=cmd_trade_trades)

    trade_order = trade_sub.add_parser("order", help="Place a stock order")
    trade_order.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_order.add_argument("--timeout", type=int, default=15)
    trade_order.add_argument("--account-id", required=True)
    trade_order.add_argument("--account-type", default="STOCK")
    trade_order.add_argument("--stock-code", required=True)
    trade_order.add_argument("--order-type", default="buy")
    trade_order.add_argument("--volume", type=int, required=True)
    trade_order.add_argument("--price-type", default="fix")
    trade_order.add_argument("--price", type=float)
    trade_order.add_argument("--strategy-name", default="quant_qmt_cli")
    trade_order.add_argument("--order-remark", default="")
    trade_order.add_argument("--async-mode", action="store_true")
    trade_order.add_argument("--output", default="")
    trade_order.set_defaults(func=cmd_trade_order)

    trade_cancel = trade_sub.add_parser("cancel", help="Cancel an order")
    trade_cancel.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    trade_cancel.add_argument("--timeout", type=int, default=15)
    trade_cancel.add_argument("--account-id", required=True)
    trade_cancel.add_argument("--account-type", default="STOCK")
    trade_cancel.add_argument("--order-id", type=int)
    trade_cancel.add_argument("--order-sysid", default="")
    trade_cancel.add_argument("--market", default="")
    trade_cancel.add_argument("--async-mode", action="store_true")
    trade_cancel.add_argument("--output", default="")
    trade_cancel.set_defaults(func=cmd_trade_cancel)

    demo = subparsers.add_parser("demo", help="Demo strategy helpers")
    demo_sub = demo.add_subparsers(dest="demo_command", required=True)
    small_cap = demo_sub.add_parser("small-cap-enhanced", help="Run the QMT-only proxy small-cap demo")
    small_cap.add_argument("--base-url", default=os.getenv("QMT_GATEWAY_URL", "http://127.0.0.1:9527"))
    small_cap.add_argument("--timeout", type=int, default=30)
    small_cap.add_argument("--sector-name", default=DEFAULT_A_STOCK_SECTOR)
    small_cap.add_argument("--stock-limit", type=int, default=300)
    small_cap.add_argument("--lookback-days", type=int, default=220)
    small_cap.add_argument("--top-n", type=int, default=10)
    small_cap.add_argument("--order-type", default="buy")
    small_cap.add_argument("--price-type", default="market")
    small_cap.add_argument("--price-offset-bps", type=float, default=20.0)
    small_cap.add_argument("--budget-per-order", type=float, default=20_000.0)
    small_cap.add_argument("--lot-size", type=int, default=100)
    small_cap.add_argument("--account-id", default="")
    small_cap.add_argument("--account-type", default="STOCK")
    small_cap.add_argument("--submit", action="store_true")
    small_cap.add_argument("--no-dedupe", action="store_true")
    small_cap.add_argument("--strategy-name", default="small_cap_enhanced_qmt_proxy_demo")
    small_cap.add_argument("--order-remark-prefix", default="small-cap-proxy")
    small_cap.add_argument("--plan-output", default="")
    small_cap.add_argument("--orders-output", default="")
    small_cap.add_argument("--size-lookback-days", type=int, default=20)
    small_cap.add_argument("--liquidity-lookback-days", type=int, default=20)
    small_cap.add_argument("--momentum-lookback-days", type=int, default=60)
    small_cap.add_argument("--skip-recent-days", type=int, default=5)
    small_cap.add_argument("--volatility-lookback-days", type=int, default=20)
    small_cap.add_argument("--min-liquidity-amount", type=float, default=20_000_000.0)
    small_cap.add_argument("--min-liquidity-percentile", type=float, default=0.10)
    small_cap.add_argument("--min-price", type=float, default=5.0)
    small_cap.add_argument("--min-history-days", type=int, default=120)
    small_cap.add_argument("--include-bj", action="store_true")
    small_cap.add_argument("--exclude-kcb", action="store_true")
    small_cap.set_defaults(func=cmd_demo_small_cap)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
