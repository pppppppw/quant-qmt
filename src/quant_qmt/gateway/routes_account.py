from __future__ import annotations

import logging

from flask import Flask

from quant_qmt.gateway import state
from quant_qmt.gateway.helpers import failure, normalize_account_type, parse_json_payload, success


logger = logging.getLogger(__name__)


def register_account_routes(app: Flask) -> None:
    @app.route("/api/v1/account/subscribe", methods=["POST"])
    def account_subscribe():
        payload = parse_json_payload()
        account_id = str(payload.get("account_id") or "").strip()
        account_type = normalize_account_type(payload.get("account_type"))
        if not account_id:
            return failure("account_id is required", status=400)
        try:
            account = state.get_account(account_id, account_type, auto_subscribe=False)
            result = state.xt_trader.subscribe(account)
            key = state.account_key(account_id, account_type)
            state.account_subscribed[key] = result == 0
            if result == 0:
                return success(
                    {
                        "account_id": account_id,
                        "account_type": account_type,
                        "result": result,
                        "subscribed": True,
                    },
                    message="account subscribe succeeded",
                )
            return failure(
                "account subscribe failed",
                status=500,
                extra={"account_id": account_id, "account_type": account_type, "result": result},
            )
        except Exception as exc:
            logger.error("account subscribe failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/account/unsubscribe", methods=["POST"])
    def account_unsubscribe():
        payload = parse_json_payload()
        account_id = str(payload.get("account_id") or "").strip()
        account_type = normalize_account_type(payload.get("account_type"))
        if not account_id:
            return failure("account_id is required", status=400)
        if not hasattr(state.xt_trader, "unsubscribe"):
            return failure("xtquant unsubscribe is not available in this build", status=400)
        try:
            account = state.get_account(account_id, account_type, auto_subscribe=False)
            result = state.xt_trader.unsubscribe(account)
            key = state.account_key(account_id, account_type)
            if result == 0:
                state.account_subscribed[key] = False
                return success(
                    {
                        "account_id": account_id,
                        "account_type": account_type,
                        "result": result,
                        "subscribed": False,
                    },
                    message="account unsubscribe succeeded",
                )
            return failure(
                "account unsubscribe failed",
                status=500,
                extra={"account_id": account_id, "account_type": account_type, "result": result},
            )
        except Exception as exc:
            logger.error("account unsubscribe failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/account/subscriptions", methods=["GET"])
    def account_subscriptions():
        data = []
        for key in sorted(state.accounts.keys()):
            account_id, account_type = key.rsplit("_", 1)
            data.append(
                {
                    "account_id": account_id,
                    "account_type": account_type,
                    "subscribed": state.account_subscribed.get(key, False),
                }
            )
        return success({"accounts": data, "count": len(data)})
