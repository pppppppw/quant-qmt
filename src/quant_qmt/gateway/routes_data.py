from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify

from quant_qmt.gateway import state
from quant_qmt.gateway.helpers import (
    failure,
    market_payload_to_rows,
    normalize_stock_code,
    parse_bool,
    parse_int,
    parse_json_payload,
    parse_list,
    success,
    to_jsonable,
)


logger = logging.getLogger(__name__)

A_STOCK_SECTOR = "\u6CAA\u6DF1A\u80A1"
CB_SECTOR_CANDIDATES = [
    "\u53EF\u8F6C\u503A",
    "\u6CAA\u6DF1\u8F6C\u503A",
    "\u4E0A\u8BC1\u8F6C\u503A",
    "\u6DF1\u8BC1\u8F6C\u503A",
    "\u6DF1\u6CAA\u8F6C\u503A",
]


def _guess_cb_codes_from_xt(xtdata: Any) -> list[str]:
    codes: list[str] = []
    if not hasattr(xtdata, "get_stock_list_in_sector"):
        return codes
    for sector in CB_SECTOR_CANDIDATES:
        try:
            values = xtdata.get_stock_list_in_sector(sector)
        except Exception:
            continue
        for item in values or []:
            code = normalize_stock_code(item)
            if "." not in code:
                continue
            prefix = code.split(".", 1)[0]
            if prefix.startswith(("11", "12", "13", "118", "123", "127")):
                codes.append(code)
    return list(dict.fromkeys(codes))


def register_data_routes(app: Flask) -> None:
    @app.route("/api/v1/data/health", methods=["GET"])
    def data_health_check():
        xtdata, err = state.get_xtdata()
        if err:
            logger.error("xtdata is unavailable: %s", err)
            return jsonify({"status": "unhealthy", "message": str(err), "timestamp": state.now_iso()}), 503
        try:
            xtdata.get_stock_list_in_sector(A_STOCK_SECTOR)
            return jsonify({"status": "ok", "message": "xtdata is available", "timestamp": state.now_iso()})
        except Exception as exc:
            logger.error("xtdata health check failed: %s", exc)
            return jsonify({"status": "unhealthy", "message": str(exc), "timestamp": state.now_iso()}), 503

    @app.route("/api/v1/data/download", methods=["POST"])
    def data_download_history():
        payload = parse_json_payload()
        stock_list = parse_list(payload.get("stock_list") or payload.get("code_list"))
        period = payload.get("period", "1d")
        start_time = payload.get("start_time", "")
        end_time = payload.get("end_time", "")
        incrementally = payload.get("incrementally")
        if not stock_list:
            return failure("stock_list or code_list is required", status=400)

        xtdata, err = state.get_xtdata()
        if err:
            return failure(f"xtdata is unavailable: {err}", status=503)
        try:
            for code in stock_list:
                kwargs = {"period": period, "start_time": start_time, "end_time": end_time}
                if incrementally is not None:
                    kwargs["incrementally"] = parse_bool(incrementally)
                xtdata.download_history_data(code, **kwargs)
            return success(
                {
                    "stock_list": stock_list,
                    "period": period,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
        except Exception as exc:
            logger.error("download_history_data failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/data/sector/stocks", methods=["POST"])
    def data_sector_stocks():
        payload = parse_json_payload()
        sector_name = str(payload.get("sector_name") or A_STOCK_SECTOR).strip()
        if not sector_name:
            return failure("sector_name must not be empty", status=400)

        xtdata, err = state.get_xtdata()
        if err:
            return failure(f"xtdata is unavailable: {err}", status=503)
        if not hasattr(xtdata, "get_stock_list_in_sector"):
            return failure("xtdata.get_stock_list_in_sector is not available in this build", status=501)
        try:
            items = [normalize_stock_code(x) for x in (xtdata.get_stock_list_in_sector(sector_name) or [])]
            items = [x for x in items if x]
            items = list(dict.fromkeys(items))
            return success({"sector_name": sector_name, "items": items, "count": len(items)})
        except Exception as exc:
            logger.error("sector stock query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/data/kline_rows", methods=["POST"])
    def data_get_kline_rows():
        payload = parse_json_payload()
        stock_list = parse_list(payload.get("stock_list") or payload.get("code_list"))
        period = payload.get("period", "1d")
        start_time = payload.get("start_time", "")
        end_time = payload.get("end_time", "")
        count = parse_int(payload.get("count", -1), "count")
        dividend_type = payload.get("dividend_type", "none")
        fill_data = parse_bool(payload.get("fill_data", True), True)
        download = parse_bool(payload.get("download", True), True)
        if not stock_list:
            return failure("stock_list or code_list is required", status=400)

        xtdata, err = state.get_xtdata()
        if err:
            return failure(f"xtdata is unavailable: {err}", status=503)
        try:
            if download:
                for code in stock_list:
                    xtdata.download_history_data(code, period=period, start_time=start_time, end_time=end_time)

            if hasattr(xtdata, "get_market_data_ex"):
                raw = xtdata.get_market_data_ex(
                    ["open", "high", "low", "close", "volume", "amount"],
                    stock_list,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    count=count,
                    dividend_type=dividend_type,
                    fill_data=fill_data,
                )
            else:
                raw = xtdata.get_market_data(
                    field_list=["open", "high", "low", "close", "volume", "amount"],
                    stock_list=stock_list,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    count=count,
                    dividend_type=dividend_type,
                    fill_data=fill_data,
                )

            rows = market_payload_to_rows(raw)
            return success({"rows": rows, "count": len(rows), "period": period})
        except Exception as exc:
            logger.error("kline_rows query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/data/cb_info", methods=["POST"])
    def data_get_cb_info():
        payload = parse_json_payload()
        stock_list = parse_list(payload.get("stock_list") or payload.get("code_list"))
        refresh = parse_bool(payload.get("refresh", True), True)

        xtdata, err = state.get_xtdata()
        if err:
            return failure(f"xtdata is unavailable: {err}", status=503)
        try:
            if refresh and hasattr(xtdata, "download_cb_data"):
                xtdata.download_cb_data()
            if not stock_list:
                stock_list = _guess_cb_codes_from_xt(xtdata)
            if not stock_list:
                return failure("no convertible bond codes were discovered; please pass stock_list explicitly", status=400)

            rows: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            has_get_cb_info = hasattr(xtdata, "get_cb_info")
            has_get_instrument_detail = hasattr(xtdata, "get_instrument_detail")
            if not has_get_cb_info and not has_get_instrument_detail:
                return failure("xtdata build does not support get_cb_info or get_instrument_detail", status=400)

            for code in stock_list:
                record: dict[str, Any] | None = None
                if has_get_cb_info:
                    try:
                        info = xtdata.get_cb_info(code)
                    except Exception as exc:
                        errors.append({"ts_code": code, "error": f"get_cb_info: {exc}"})
                        info = None
                    if info:
                        candidate = to_jsonable(info)
                        if isinstance(candidate, dict) and candidate:
                            record = candidate

                if record is None and has_get_instrument_detail:
                    detail = None
                    try:
                        detail = xtdata.get_instrument_detail(code, True)
                    except TypeError:
                        try:
                            detail = xtdata.get_instrument_detail(code)
                        except Exception as exc:
                            errors.append({"ts_code": code, "error": f"get_instrument_detail: {exc}"})
                    except Exception as exc:
                        errors.append({"ts_code": code, "error": f"get_instrument_detail: {exc}"})
                    if detail:
                        candidate = to_jsonable(detail)
                        if isinstance(candidate, dict) and candidate:
                            record = candidate
                            record.setdefault("bondCode", code)
                            if record.get("InstrumentName") and not record.get("bondName"):
                                record["bondName"] = record.get("InstrumentName")
                            if record.get("OptUndlCode") and not record.get("stockCode"):
                                record["stockCode"] = record.get("OptUndlCode")
                            if record.get("OptUndlName") and not record.get("stockName"):
                                record["stockName"] = record.get("OptUndlName")
                            if record.get("OptExercisePrice") is not None and record.get("bondConvPrice") is None:
                                record["bondConvPrice"] = record.get("OptExercisePrice")
                            record.setdefault("_fallback_source", "instrument_detail")
                if record is not None:
                    record.setdefault("bondCode", code)
                    rows.append(record)

            return success(
                {
                    "items": rows,
                    "count": len(rows),
                    "request_count": len(stock_list),
                    "errors": errors[:100],
                }
            )
        except Exception as exc:
            logger.error("cb_info query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/data/market", methods=["POST"])
    def data_get_market():
        payload = parse_json_payload()
        stock_list = parse_list(payload.get("stock_list") or payload.get("code_list"))
        field_list = parse_list(payload.get("field_list") or payload.get("fields"))
        period = payload.get("period", "1d")
        start_time = payload.get("start_time", "")
        end_time = payload.get("end_time", "")
        count = parse_int(payload.get("count", -1), "count")
        dividend_type = payload.get("dividend_type", "none")
        fill_data = parse_bool(payload.get("fill_data", True), True)
        if not stock_list:
            return failure("stock_list or code_list is required", status=400)

        xtdata, err = state.get_xtdata()
        if err:
            return failure(f"xtdata is unavailable: {err}", status=503)
        try:
            if hasattr(xtdata, "get_market_data_ex"):
                data = xtdata.get_market_data_ex(
                    field_list,
                    stock_list,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    count=count,
                    dividend_type=dividend_type,
                    fill_data=fill_data,
                )
            else:
                data = xtdata.get_market_data(
                    field_list=field_list,
                    stock_list=stock_list,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    count=count,
                    dividend_type=dividend_type,
                    fill_data=fill_data,
                )
            return success(to_jsonable(data))
        except Exception as exc:
            logger.error("market query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/data/full_tick", methods=["POST"])
    def data_get_full_tick():
        payload = parse_json_payload()
        stock_list = parse_list(payload.get("stock_list") or payload.get("code_list"))
        auto_subscribe = parse_bool(payload.get("subscribe"), True)
        if not stock_list:
            return failure("stock_list or code_list is required", status=400)

        xtdata, err = state.get_xtdata()
        if err:
            return failure(f"xtdata is unavailable: {err}", status=503)
        try:
            seq = None
            if auto_subscribe:
                seq = state.ensure_whole_quote_subscription(xtdata, stock_list)
            if not hasattr(xtdata, "get_full_tick"):
                return failure("xtdata.get_full_tick is not available in this build", status=501)
            data = xtdata.get_full_tick(stock_list)
            if isinstance(data, dict):
                state.update_realtime_quote_cache(data)
            result: dict[str, Any] = {"items": to_jsonable(data), "count": len(stock_list)}
            if seq is not None:
                result["subscription_seq"] = seq
            return success(result)
        except Exception as exc:
            logger.error("full_tick query failed: %s", exc)
            return failure(str(exc), status=500)

    @app.route("/api/v1/data/realtime/cache", methods=["POST"])
    def data_get_realtime_cache():
        payload = parse_json_payload()
        stock_list = parse_list(payload.get("stock_list") or payload.get("code_list"))
        auto_subscribe = parse_bool(payload.get("subscribe"), True)
        fill_missing = parse_bool(payload.get("fill_missing"), True)
        if not stock_list:
            return failure("stock_list or code_list is required", status=400)

        xtdata, err = state.get_xtdata()
        if err:
            return failure(f"xtdata is unavailable: {err}", status=503)
        try:
            seq = None
            if auto_subscribe:
                seq = state.ensure_whole_quote_subscription(xtdata, stock_list)

            items = state.get_cached_realtime_quotes(stock_list)
            missing_codes = [
                normalize_stock_code(code)
                for code in stock_list
                if normalize_stock_code(code) and normalize_stock_code(code) not in items
            ]
            if fill_missing and missing_codes and hasattr(xtdata, "get_full_tick"):
                pulled = xtdata.get_full_tick(missing_codes)
                if isinstance(pulled, dict):
                    state.update_realtime_quote_cache(pulled)
                    items = state.get_cached_realtime_quotes(stock_list)
                    missing_codes = [
                        normalize_stock_code(code)
                        for code in stock_list
                        if normalize_stock_code(code) and normalize_stock_code(code) not in items
                    ]

            data: dict[str, Any] = {
                "items": items,
                "request_count": len(stock_list),
                "cached_count": len(items),
                "missing_codes": missing_codes,
                "as_of": state.now_iso(),
            }
            if seq is not None:
                data["subscription_seq"] = seq
            return success(data)
        except Exception as exc:
            logger.error("realtime cache query failed: %s", exc)
            return failure(str(exc), status=500)
