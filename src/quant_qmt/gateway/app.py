from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS

from quant_qmt.gateway import state
from quant_qmt.gateway.routes_account import register_account_routes
from quant_qmt.gateway.routes_data import register_data_routes
from quant_qmt.gateway.routes_health import register_health_routes
from quant_qmt.gateway.routes_query import register_query_routes
from quant_qmt.gateway.routes_trade import register_trade_routes
from quant_qmt.logging_utils import configure_logging


logger = logging.getLogger(__name__)


def create_app() -> Flask:
    configure_logging()
    state.reload_settings()

    app = Flask(__name__)
    app.json.ensure_ascii = False
    CORS(app)

    @app.before_request
    def ensure_qmt_connection():
        bypass_paths = {"/health", "/api/v1/trader/reconnect"}
        if request.path in bypass_paths:
            return None
        if request.path.startswith("/api/v1/data/") or request.path.startswith("/api/v1/callbacks/"):
            return None
        if not state.is_connected():
            state.try_reconnect()
        if state.is_connected():
            return None
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "message": "QMT is not connected. Please confirm the broker client is running.",
                }
            ),
            503,
        )

    register_health_routes(app)
    register_data_routes(app)
    register_trade_routes(app)
    register_account_routes(app)
    register_query_routes(app)
    return app


def run_gateway(host: str | None = None, port: int | None = None) -> None:
    if host:
        os.environ["QMT_GATEWAY_HOST"] = host
    if port is not None:
        os.environ["QMT_GATEWAY_PORT"] = str(port)

    app = create_app()
    if not state.init_qmt():
        logger.error("Initial QMT connection failed. The gateway will stay alive for later reconnects.")

    callback_file = state.current_callback_log_file()
    if callback_file:
        logger.info("Callback persistence enabled: %s", callback_file)
    logger.info("Starting quant-qmt gateway on %s:%s", state.settings.host, state.settings.port)
    app.run(host=state.settings.host, port=state.settings.port, debug=False)
