from __future__ import annotations

import pandas as pd

from quant_qmt.gateway.helpers import market_payload_to_rows, normalize_trade_date_key


def test_normalize_trade_date_key_handles_multiple_formats() -> None:
    assert normalize_trade_date_key("20260327") == "20260327"
    assert normalize_trade_date_key("2026-03-27") == "20260327"
    assert normalize_trade_date_key("2026/03/27 09:30:00") == "20260327"


def test_market_payload_to_rows_supports_symbol_to_dataframe_shape() -> None:
    raw = {
        "600000.SH": pd.DataFrame(
            {
                "open": [10.0, 10.1],
                "high": [10.2, 10.3],
                "low": [9.9, 10.0],
                "close": [10.1, 10.2],
                "volume": [1000, 1200],
                "amount": [10000.0, 12240.0],
            },
            index=["20260326", "20260327"],
        )
    }

    rows = market_payload_to_rows(raw)

    assert len(rows) == 2
    assert rows[0]["ts_code"] == "600000.SH"
    assert rows[0]["trade_date"] == "20260326"
    assert rows[1]["close"] == 10.2
