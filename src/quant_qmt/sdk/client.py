from __future__ import annotations

from typing import Any

import requests

from quant_qmt.config import ClientConfig


class QmtGatewayError(RuntimeError):
    """Gateway request failure."""


class QmtGatewayClient:
    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        config = ClientConfig.from_env()
        self.base_url = (base_url or config.base_url).rstrip("/")
        self.timeout = int(timeout or config.timeout)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            timeout=timeout or self.timeout,
        )
        try:
            payload = response.json()
        except Exception:
            payload = {"message": response.text}

        if response.status_code >= 400:
            raise QmtGatewayError(f"HTTP {response.status_code}: {payload}")

        if isinstance(payload, dict) and payload.get("code", 0) != 0:
            raise QmtGatewayError(f"Gateway error: {payload}")

        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def reconnect(self) -> dict[str, Any]:
        return self._request("POST", "/api/v1/trader/reconnect")

    def data_health(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/data/health")

    def recent_callbacks(self, limit: int = 100) -> dict[str, Any]:
        return self._request("GET", "/api/v1/callbacks/recent", params={"limit": limit})

    def sector_stocks(self, sector_name: str = "\u6CAA\u6DF1A\u80A1") -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/data/sector/stocks",
            json_body={"sector_name": sector_name},
        )

    def download_history(
        self,
        stock_list: list[str],
        *,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        incrementally: bool | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "stock_list": stock_list,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
        }
        if incrementally is not None:
            body["incrementally"] = bool(incrementally)
        return self._request("POST", "/api/v1/data/download", json_body=body)

    def get_kline_rows(
        self,
        stock_list: list[str],
        *,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
        download: bool = True,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/data/kline_rows",
            json_body={
                "stock_list": stock_list,
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "count": count,
                "dividend_type": dividend_type,
                "fill_data": fill_data,
                "download": download,
            },
        )

    def get_market(
        self,
        stock_list: list[str],
        *,
        field_list: list[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
    ) -> Any:
        return self._request(
            "POST",
            "/api/v1/data/market",
            json_body={
                "stock_list": stock_list,
                "field_list": field_list,
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "count": count,
                "dividend_type": dividend_type,
                "fill_data": fill_data,
            },
        )

    def get_cb_info(self, stock_list: list[str] | None = None, *, refresh: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {"refresh": refresh}
        if stock_list:
            body["stock_list"] = stock_list
        return self._request("POST", "/api/v1/data/cb_info", json_body=body, timeout=30)

    def get_full_tick(self, stock_list: list[str], *, subscribe: bool = True) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/data/full_tick",
            json_body={"stock_list": stock_list, "subscribe": subscribe},
        )

    def get_realtime_cache(
        self,
        stock_list: list[str],
        *,
        subscribe: bool = True,
        fill_missing: bool = True,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/data/realtime/cache",
            json_body={
                "stock_list": stock_list,
                "subscribe": subscribe,
                "fill_missing": fill_missing,
            },
        )

    def subscribe_account(self, account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/account/subscribe",
            json_body={"account_id": account_id, "account_type": account_type},
        )

    def unsubscribe_account(self, account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/account/unsubscribe",
            json_body={"account_id": account_id, "account_type": account_type},
        )

    def account_subscriptions(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/account/subscriptions")

    def order_stock(
        self,
        account_id: str,
        stock_code: str,
        order_type: Any,
        volume: int,
        price: float,
        *,
        account_type: str = "STOCK",
        price_type: Any = "fix",
        strategy_name: str = "",
        order_remark: str = "",
        async_mode: bool = False,
    ) -> dict[str, Any]:
        path = "/api/v1/order/stock/async" if async_mode else "/api/v1/order/stock"
        return self._request(
            "POST",
            path,
            json_body={
                "account_id": account_id,
                "account_type": account_type,
                "stock_code": stock_code,
                "order_type": order_type,
                "volume": int(volume),
                "price_type": price_type,
                "price": float(price),
                "strategy_name": strategy_name,
                "order_remark": order_remark,
            },
        )

    def cancel_order(
        self,
        account_id: str,
        *,
        order_id: int | None = None,
        order_sysid: str | None = None,
        market: Any | None = None,
        account_type: str = "STOCK",
        async_mode: bool = False,
    ) -> dict[str, Any]:
        path = "/api/v1/order/cancel/async" if async_mode else "/api/v1/order/cancel"
        body: dict[str, Any] = {"account_id": account_id, "account_type": account_type}
        if order_id is not None:
            body["order_id"] = int(order_id)
        if order_sysid is not None:
            body["order_sysid"] = str(order_sysid)
        if market is not None:
            body["market"] = market
        return self._request("POST", path, json_body=body)

    def query_asset(self, account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/query/asset",
            params={"account_id": account_id, "account_type": account_type},
        )

    def query_positions(self, account_id: str, account_type: str = "STOCK") -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/api/v1/query/positions",
            params={"account_id": account_id, "account_type": account_type},
        )

    def query_position(self, account_id: str, stock_code: str, account_type: str = "STOCK") -> dict[str, Any] | None:
        return self._request(
            "GET",
            "/api/v1/query/position",
            params={
                "account_id": account_id,
                "account_type": account_type,
                "stock_code": stock_code,
            },
        )

    def query_orders(
        self,
        account_id: str,
        account_type: str = "STOCK",
        cancelable_only: bool = False,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/api/v1/query/orders",
            params={
                "account_id": account_id,
                "account_type": account_type,
                "cancelable_only": str(bool(cancelable_only)).lower(),
            },
        )

    def query_order(self, account_id: str, order_id: int, account_type: str = "STOCK") -> dict[str, Any] | None:
        return self._request(
            "GET",
            "/api/v1/query/order",
            params={"account_id": account_id, "account_type": account_type, "order_id": int(order_id)},
        )

    def query_trades(self, account_id: str, account_type: str = "STOCK") -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/api/v1/query/trades",
            params={"account_id": account_id, "account_type": account_type},
        )

    def query_account_infos(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/query/account_infos")
