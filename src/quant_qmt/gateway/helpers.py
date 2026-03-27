from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from flask import jsonify, request


def _is_special_float(value: Any) -> bool:
    return isinstance(value, float) and (math.isnan(value) or math.isinf(value))


def success(data: Any = None, message: str | None = None, status: int = 200):
    payload: dict[str, Any] = {"code": 0}
    if message is not None:
        payload["message"] = message
    if data is not None:
        payload["data"] = to_jsonable(data)
    return jsonify(payload), status


def failure(message: str, status: int = 400, code: int = -1, extra: dict[str, Any] | None = None):
    payload: dict[str, Any] = {"code": code, "message": message}
    if extra:
        payload.update(to_jsonable(extra))
    return jsonify(payload), status


def to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if _is_special_float(obj):
        return None
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, float):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "isoformat") and callable(getattr(obj, "isoformat")):
        try:
            return obj.isoformat()
        except Exception:
            pass
    if hasattr(obj, "to_dict"):
        try:
            return to_jsonable(obj.to_dict())
        except Exception:
            pass
    if hasattr(obj, "tolist"):
        try:
            return to_jsonable(obj.tolist())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return {str(k): to_jsonable(v) for k, v in vars(obj).items() if not str(k).startswith("_")}
        except Exception:
            pass
    return str(obj)


def extract_public_attrs(obj: Any, candidate_fields: list[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if candidate_fields:
        for field in candidate_fields:
            try:
                value = getattr(obj, field)
            except Exception:
                continue
            if callable(value):
                continue
            if value is not None:
                payload[field] = to_jsonable(value)
        if payload:
            return payload

    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            continue
        if value is None or isinstance(value, (str, int, float, bool)):
            payload[name] = to_jsonable(value)
    return payload


def normalize_account_type(value: Any) -> str:
    if value is None:
        return "STOCK"
    text = str(value).strip().upper()
    if not text:
        return "STOCK"
    return {"2": "STOCK"}.get(text, text)


def build_account_info_payload(info: Any) -> dict[str, Any]:
    payload = extract_public_attrs(
        info,
        candidate_fields=[
            "account_id",
            "account_type",
            "account_name",
            "status",
            "broker_name",
            "branch_name",
            "client_id",
            "fund_account",
            "secu_account",
        ],
    )
    if "account_id" not in payload:
        for field in ("m_strAccountID", "m_strAccountId", "m_strFundAccount", "fund_account"):
            value = getattr(info, field, None)
            if value:
                payload["account_id"] = str(value)
                break
    payload["account_type"] = normalize_account_type(payload.get("account_type"))
    if not payload:
        payload = {"raw": str(info), "account_type": "STOCK"}
    elif "raw" not in payload:
        payload["raw"] = str(info)
    return payload


def parse_json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()]


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def parse_int(value: Any, field_name: str, min_value: int | None = None) -> int:
    try:
        parsed = int(value)
    except Exception as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if min_value is not None and parsed < min_value:
        raise ValueError(f"{field_name} must be >= {min_value}")
    return parsed


def normalize_stock_code(value: Any) -> str:
    return str(value or "").strip().upper()


def now_iso() -> str:
    return datetime.now().isoformat()


def is_symbol_code(value: Any) -> bool:
    if value is None:
        return False
    text = normalize_stock_code(value)
    return bool(text) and "." in text and len(text.split(".", 1)[0]) >= 3


def normalize_trade_date_key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        if len(text) == 8:
            try:
                return datetime.strptime(text, "%Y%m%d").strftime("%Y%m%d")
            except Exception:
                pass
        try:
            ts = int(text)
            if ts > 10**12:
                ts = ts // 1000
            if ts > 10**9:
                return datetime.fromtimestamp(ts).strftime("%Y%m%d")
        except Exception:
            pass
    for fmt in (
        "%Y%m%d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d%H%M%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y%m%d")
    except Exception:
        return None


def market_payload_to_rows(raw_data: Any) -> list[dict[str, Any]]:
    fields = ["open", "high", "low", "close", "volume", "amount"]
    if isinstance(raw_data, dict) and raw_data:
        dataframe_like = True
        for value in raw_data.values():
            if not hasattr(value, "iterrows") or not hasattr(value, "columns"):
                dataframe_like = False
                break
        if dataframe_like:
            rows: list[dict[str, Any]] = []
            for ts_code, frame in raw_data.items():
                normalized_code = normalize_stock_code(ts_code)
                for trade_key, row in frame.iterrows():
                    trade_date = normalize_trade_date_key(trade_key)
                    if not trade_date:
                        continue
                    item: dict[str, Any] = {"ts_code": normalized_code, "trade_date": trade_date}
                    for field in fields:
                        if field not in frame.columns:
                            continue
                        value = row.get(field)
                        if hasattr(value, "item"):
                            try:
                                value = value.item()
                            except Exception:
                                pass
                        item[field] = to_jsonable(value)
                    rows.append(item)
            rows.sort(key=lambda item: (item.get("trade_date", ""), item.get("ts_code", "")))
            return rows

    if not isinstance(raw_data, dict):
        return []

    rows_map: dict[tuple[str, str], dict[str, Any]] = {}

    def upsert(ts_code: str, trade_date: str, field_name: str, value: Any) -> None:
        key = (ts_code, trade_date)
        row = rows_map.setdefault(key, {"ts_code": ts_code, "trade_date": trade_date})
        row[field_name] = value

    for field in fields:
        field_data = raw_data.get(field)
        if not isinstance(field_data, dict):
            continue
        for outer_key, inner in field_data.items():
            if not isinstance(inner, dict):
                continue
            if is_symbol_code(outer_key):
                ts_code = normalize_stock_code(outer_key)
                for dt_key, value in inner.items():
                    trade_date = normalize_trade_date_key(dt_key)
                    if trade_date:
                        upsert(ts_code, trade_date, field, value)
                continue
            trade_date = normalize_trade_date_key(outer_key)
            if not trade_date:
                continue
            for maybe_symbol, value in inner.items():
                if is_symbol_code(maybe_symbol):
                    upsert(normalize_stock_code(maybe_symbol), trade_date, field, value)

    rows = list(rows_map.values())
    rows.sort(key=lambda item: (item.get("trade_date", ""), item.get("ts_code", "")))
    return rows
