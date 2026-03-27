from __future__ import annotations

import logging

from flask import Flask, request

from quant_qmt.gateway import state
from quant_qmt.gateway.helpers import build_account_info_payload, failure, normalize_account_type, parse_bool, parse_int, success


logger = logging.getLogger(__name__)


def _query_account_params() -> tuple[str, str]:
    account_id = str(request.args.get("account_id") or "").strip()
    account_type = normalize_account_type(request.args.get("account_type"))
    if not account_id:
        account_id = state.resolve_default_account_id(account_type)
    if not account_id:
        raise ValueError("account_id is required and no default account could be detected")
    return account_id, account_type


def register_query_routes(app: Flask) -> None:
    @app.route("/api/v1/query/asset", methods=["GET"])
    def query_asset():
        try:
            account_id, account_type = _query_account_params()
            account = state.get_account(account_id, account_type)
            asset = state.xt_trader.query_stock_asset(account)
            if not asset:
                return failure("asset query failed", status=500)
            return success(
                {
                    "account_id": getattr(asset, "account_id", account_id),
                    "cash": getattr(asset, "cash", None),
                    "frozen_cash": getattr(asset, "frozen_cash", None),
                    "market_value": getattr(asset, "market_value", None),
                    "total_asset": getattr(asset, "total_asset", None),
                    "fetch_balance": getattr(asset, "fetch_balance", None),
                }
            )
        except ValueError as exc:
            return failure(str(exc), status=400)
        except Exception as exc:
            logger.error("asset query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/query/positions", methods=["GET"])
    def query_positions():
        try:
            account_id, account_type = _query_account_params()
            account = state.get_account(account_id, account_type)
            positions = state.xt_trader.query_stock_positions(account)
            if not positions:
                return success([])
            return success([state.build_position_payload(pos) for pos in positions])
        except ValueError as exc:
            return failure(str(exc), status=400)
        except Exception as exc:
            logger.error("positions query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/query/position", methods=["GET"])
    def query_position():
        if not hasattr(state.xt_trader, "query_stock_position"):
            return failure("xtquant query_stock_position is not available in this build", status=400)
        try:
            account_id, account_type = _query_account_params()
            stock_code = str(request.args.get("stock_code") or "").strip()
            if not stock_code:
                return failure("stock_code is required", status=400)
            account = state.get_account(account_id, account_type)
            position = state.xt_trader.query_stock_position(account, stock_code)
            if not position:
                return success(None)
            return success(state.build_position_payload(position))
        except ValueError as exc:
            return failure(str(exc), status=400)
        except Exception as exc:
            logger.error("single position query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/query/orders", methods=["GET"])
    def query_orders():
        try:
            account_id, account_type = _query_account_params()
            cancelable_only = parse_bool(request.args.get("cancelable_only"), False)
            account = state.get_account(account_id, account_type)
            try:
                orders = state.xt_trader.query_stock_orders(account, cancelable_only)
            except TypeError:
                orders = state.xt_trader.query_stock_orders(account)
            if not orders:
                return success([])
            return success([state.build_order_payload(order) for order in orders])
        except ValueError as exc:
            return failure(str(exc), status=400)
        except Exception as exc:
            logger.error("orders query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/query/order", methods=["GET"])
    def query_order():
        if not hasattr(state.xt_trader, "query_stock_order"):
            return failure("xtquant query_stock_order is not available in this build", status=400)
        try:
            account_id, account_type = _query_account_params()
            order_id = parse_int(request.args.get("order_id"), "order_id", min_value=1)
            account = state.get_account(account_id, account_type)
            order = state.xt_trader.query_stock_order(account, order_id)
            if not order:
                return success(None)
            return success(state.build_order_payload(order))
        except ValueError as exc:
            return failure(str(exc), status=400)
        except Exception as exc:
            logger.error("single order query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/query/trades", methods=["GET"])
    def query_trades():
        try:
            account_id, account_type = _query_account_params()
            account = state.get_account(account_id, account_type)
            trades = state.xt_trader.query_stock_trades(account)
            if not trades:
                return success([])
            return success([state.build_trade_payload(trade) for trade in trades])
        except ValueError as exc:
            return failure(str(exc), status=400)
        except Exception as exc:
            logger.error("trades query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/query/account_infos", methods=["GET"])
    def query_account_infos():
        try:
            result: list[dict[str, object]] = []
            if state.xt_trader is not None and hasattr(state.xt_trader, "query_account_infos"):
                infos = state.xt_trader.query_account_infos() or []
                result.extend([build_account_info_payload(info) for info in infos])
            if not result:
                for key in sorted(state.accounts.keys()):
                    account_id, account_type = key.rsplit("_", 1)
                    result.append({"account_id": account_id, "account_type": account_type, "raw": account_id})
            if state.settings.default_account_id and not any(
                str(item.get("account_id") or "") == state.settings.default_account_id for item in result
            ):
                result.append(
                    {
                        "account_id": state.settings.default_account_id,
                        "account_type": "STOCK",
                        "raw": state.settings.default_account_id,
                    }
                )
            return success(result)
        except Exception as exc:
            logger.error("account infos query failed: %s", exc)
            return failure(str(exc), status=500)
