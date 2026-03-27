from __future__ import annotations

import logging

from flask import Flask

from quant_qmt.gateway import state
from quant_qmt.gateway.helpers import failure, parse_bool, parse_int, parse_json_payload, success


logger = logging.getLogger(__name__)


def _order_stock_impl(force_async: bool | None = None):
    payload = parse_json_payload()
    account_id = str(payload.get("account_id") or "").strip()
    account_type = payload.get("account_type")
    stock_code = str(payload.get("stock_code") or "").strip()
    order_type = payload.get("order_type")
    volume = payload.get("volume")
    price_type = payload.get("price_type", "fix")
    price = float(payload.get("price", 0))
    strategy_name = payload.get("strategy_name", "")
    order_remark = payload.get("order_remark", "")

    async_mode = parse_bool(payload.get("async"), False)
    if force_async is not None:
        async_mode = force_async

    if not account_id or not stock_code or volume is None or order_type is None:
        return failure("account_id, stock_code, order_type and volume are required", status=400)
    try:
        parsed_volume = parse_int(volume, "volume", min_value=1)
        xt_order_type = state.resolve_order_type(order_type)
        xt_price_type = state.resolve_price_type(price_type, stock_code=stock_code)
        xtconstant = state.get_xtconstant()
        if xt_price_type == xtconstant.FIX_PRICE and price <= 0:
            return failure("price must be > 0 for limit orders", status=400)

        account = state.get_account(account_id, account_type or "STOCK", auto_subscribe=True)
        if async_mode:
            if not hasattr(state.xt_trader, "order_stock_async"):
                return failure("xtquant order_stock_async is not available in this build", status=400)
            result_id = state.xt_trader.order_stock_async(
                account,
                stock_code,
                xt_order_type,
                parsed_volume,
                xt_price_type,
                price,
                strategy_name,
                order_remark,
            )
            if result_id > 0:
                return success({"seq": result_id})
            return failure("async order request failed", status=500, extra={"result": result_id})

        order_id = state.xt_trader.order_stock(
            account,
            stock_code,
            xt_order_type,
            parsed_volume,
            xt_price_type,
            price,
            strategy_name,
            order_remark,
        )
        if order_id > 0:
            return success({"order_id": order_id})
        return failure("order failed", status=500, extra={"result": order_id})
    except ValueError as exc:
        return failure(str(exc), status=400)
    except Exception as exc:
        logger.error("order failed: %s", exc)
        return failure(str(exc), status=500)


def _cancel_order_impl(force_async: bool | None = None):
    payload = parse_json_payload()
    account_id = str(payload.get("account_id") or "").strip()
    account_type = payload.get("account_type")
    order_id = payload.get("order_id")
    order_sysid = payload.get("order_sysid")
    market = payload.get("market")
    async_mode = parse_bool(payload.get("async"), False)
    if force_async is not None:
        async_mode = force_async

    if not account_id:
        return failure("account_id is required", status=400)
    try:
        account = state.get_account(account_id, account_type or "STOCK", auto_subscribe=True)
        if order_id is not None:
            parsed_order_id = parse_int(order_id, "order_id", min_value=1)
            if async_mode:
                if not hasattr(state.xt_trader, "cancel_order_stock_async"):
                    return failure("xtquant cancel_order_stock_async is not available in this build", status=400)
                result = state.xt_trader.cancel_order_stock_async(account, parsed_order_id)
                if result > 0:
                    return success({"seq": result}, message="async cancel request submitted")
                return failure("async cancel failed", status=500, extra={"result": result})
            result = state.xt_trader.cancel_order_stock(account, parsed_order_id)
            if result == 0:
                return success({"result": result}, message="cancel succeeded")
            return failure("cancel failed", status=500, extra={"result": result})

        if order_sysid:
            market_id = state.resolve_market(market)
            normalized_sysid = str(order_sysid).strip()
            if not normalized_sysid:
                return failure("order_sysid must not be empty", status=400)
            if async_mode:
                if not hasattr(state.xt_trader, "cancel_order_stock_sysid_async"):
                    return failure("xtquant cancel_order_stock_sysid_async is not available in this build", status=400)
                result = state.xt_trader.cancel_order_stock_sysid_async(account, market_id, normalized_sysid)
                if result > 0:
                    return success({"seq": result}, message="async cancel request submitted")
                return failure("async cancel failed", status=500, extra={"result": result})
            if not hasattr(state.xt_trader, "cancel_order_stock_sysid"):
                return failure("xtquant cancel_order_stock_sysid is not available in this build", status=400)
            result = state.xt_trader.cancel_order_stock_sysid(account, market_id, normalized_sysid)
            if result == 0:
                return success({"result": result}, message="cancel succeeded")
            return failure("cancel failed", status=500, extra={"result": result})

        return failure("either order_id or order_sysid is required", status=400)
    except ValueError as exc:
        return failure(str(exc), status=400)
    except Exception as exc:
        logger.error("cancel failed: %s", exc)
        return failure(str(exc), status=500)


def register_trade_routes(app: Flask) -> None:
    @app.route("/api/v1/order/stock", methods=["POST"])
    def order_stock():
        return _order_stock_impl(force_async=None)

    @app.route("/api/v1/order/stock/async", methods=["POST"])
    def order_stock_async():
        return _order_stock_impl(force_async=True)

    @app.route("/api/v1/order/cancel", methods=["POST"])
    def cancel_order():
        return _cancel_order_impl(force_async=None)

    @app.route("/api/v1/order/cancel/async", methods=["POST"])
    def cancel_order_async():
        return _cancel_order_impl(force_async=True)
