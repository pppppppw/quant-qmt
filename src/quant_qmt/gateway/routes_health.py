from __future__ import annotations

from flask import Flask, jsonify, request

from quant_qmt.gateway import state
from quant_qmt.gateway.helpers import now_iso, parse_int, success


def register_health_routes(app: Flask) -> None:
    @app.route("/health", methods=["GET"])
    def health_check():
        if not state.is_connected():
            state.try_reconnect(force=True)
        connected = state.is_connected()
        payload = {
            "status": "ok" if connected else "unhealthy",
            "qmt_connected": connected,
            "timestamp": now_iso(),
        }
        if not connected:
            payload["message"] = "QMT is not connected."
            return jsonify(payload), 503
        return jsonify(payload)

    @app.route("/api/v1/trader/reconnect", methods=["POST"])
    def trader_reconnect():
        connected = state.try_reconnect(force=True)
        if connected:
            return success({"qmt_connected": True, "timestamp": now_iso()}, message="QMT reconnect succeeded")
        return (
            jsonify(
                {
                    "code": -1,
                    "message": "QMT reconnect failed",
                    "qmt_connected": False,
                    "timestamp": now_iso(),
                }
            ),
            503,
        )

    @app.route("/api/v1/callbacks/recent", methods=["GET"])
    def query_recent_callbacks():
        limit = min(parse_int(request.args.get("limit", 100), "limit", min_value=1), 1000)
        with state.callback_events_lock:
            data = list(state.callback_events)[-limit:]
        return success({"events": data, "count": len(data)})
