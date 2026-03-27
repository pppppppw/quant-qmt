from __future__ import annotations

import pandas as pd

from quant_qmt.strategy.small_cap_proxy import (
    SmallCapEnhancedProxyConfig,
    SmallCapEnhancedProxyStrategy,
    rows_to_market_data,
)


def test_rows_to_market_data_builds_expected_fields() -> None:
    rows = [
        {"ts_code": "600000.SH", "trade_date": "20260326", "close": 10.0, "volume": 100, "amount": 1000.0},
        {"ts_code": "600000.SH", "trade_date": "20260327", "close": 10.2, "volume": 110, "amount": 1122.0},
        {"ts_code": "000001.SZ", "trade_date": "20260326", "close": 8.0, "volume": 200, "amount": 1600.0},
        {"ts_code": "000001.SZ", "trade_date": "20260327", "close": 8.1, "volume": 210, "amount": 1701.0},
    ]

    market_data = rows_to_market_data(rows)

    assert set(market_data.keys()) == {"close", "volume", "amount"}
    assert market_data["close"].shape == (2, 2)


def test_small_cap_strategy_returns_signal_frame() -> None:
    index = pd.date_range("2025-01-01", periods=220, freq="D")
    close = pd.DataFrame(
        {
            "600000.SH": [10 + i * 0.01 for i in range(len(index))],
            "000001.SZ": [8 + i * 0.008 for i in range(len(index))],
            "603006.SH": [12 + i * 0.005 for i in range(len(index))],
        },
        index=index,
    )
    amount = pd.DataFrame(
        {
            "600000.SH": [50_000_000 + i * 1000 for i in range(len(index))],
            "000001.SZ": [35_000_000 + i * 900 for i in range(len(index))],
            "603006.SH": [25_000_000 + i * 800 for i in range(len(index))],
        },
        index=index,
    )
    volume = amount.div(close)

    strategy = SmallCapEnhancedProxyStrategy(
        SmallCapEnhancedProxyConfig(
            min_liquidity_amount=10_000_000.0,
            min_liquidity_percentile=0.0,
            min_history_days=60,
            regime_min_breadth=0.0,
            regime_min_return=-1.0,
            top_k=2,
        )
    )

    signal = strategy.build_signal({"close": close, "amount": amount, "volume": volume})

    assert not signal.empty
    assert list(signal.columns) == ["score"]
