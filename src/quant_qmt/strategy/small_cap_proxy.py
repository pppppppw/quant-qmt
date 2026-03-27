from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from quant_qmt.sdk import QmtGatewayClient


DEFAULT_A_STOCK_SECTOR = "\u6CAA\u6DF1A\u80A1"


def _normalize_cross_section(df: pd.DataFrame) -> pd.DataFrame:
    mean = df.mean(axis=1)
    std = df.std(axis=1).replace(0, np.nan)
    centered = df.sub(mean, axis=0)
    normalized = centered.div(std, axis=0)
    fallback_rows = std.isna()
    if fallback_rows.any():
        normalized.loc[fallback_rows] = centered.loc[fallback_rows]
    return normalized


@dataclass
class SmallCapEnhancedProxyConfig:
    size_lookback_days: int = 20
    liquidity_lookback_days: int = 20
    momentum_lookback_days: int = 60
    skip_recent_days: int = 5
    volatility_lookback_days: int = 20
    min_liquidity_amount: float = 20_000_000.0
    min_liquidity_percentile: float = 0.10
    min_price: float = 5.0
    min_history_days: int = 120
    exclude_bj: bool = True
    exclude_kcb: bool = False
    size_weight: float = 0.55
    momentum_weight: float = 0.30
    liquidity_weight: float = 0.15
    volatility_penalty: float = 0.15
    liquidity_cv_penalty: float = 0.10
    regime_ma_days: int = 60
    regime_lookback_days: int = 20
    regime_min_return: float = -0.02
    regime_min_breadth: float = 0.45
    top_k: int = 10

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SmallCapEnhancedProxyStrategy:
    """QMT-only proxy version of small-cap enhanced ranking.

    This implementation explicitly uses turnover amount and liquidity as a proxy
    for size when real historical circ_mv or total_mv are not available.
    """

    def __init__(self, config: SmallCapEnhancedProxyConfig | None = None):
        self.config = config or SmallCapEnhancedProxyConfig()

    def build_signal(self, market_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        close = self._require_field(market_data, "close").copy()
        amount = market_data.get("amount")
        if amount is None or amount.empty:
            amount = close * self._require_field(market_data, "volume")
        amount = amount.reindex_like(close)

        allowed_columns = self._allowed_columns(
            close.columns,
            exclude_bj=self.config.exclude_bj,
            exclude_kcb=self.config.exclude_kcb,
        )
        close = close.loc[:, allowed_columns]
        amount = amount.loc[:, allowed_columns]

        size_metric = np.log1p(amount.clip(lower=0.0)).rolling(self.config.size_lookback_days).mean()
        liquidity = amount.rolling(self.config.liquidity_lookback_days).mean().replace([np.inf, -np.inf], np.nan)

        shifted_recent = close.shift(self.config.skip_recent_days)
        shifted_base = close.shift(self.config.skip_recent_days + self.config.momentum_lookback_days)
        momentum = shifted_recent.div(shifted_base).replace([np.inf, -np.inf], np.nan) - 1.0

        returns = close.pct_change(fill_method=None)
        volatility = returns.rolling(self.config.volatility_lookback_days).std() * np.sqrt(252.0)

        liquidity_cv = amount.rolling(self.config.liquidity_lookback_days).std().div(liquidity).replace([np.inf, -np.inf], np.nan)

        z_small = -_normalize_cross_section(size_metric)
        z_momentum = _normalize_cross_section(momentum)
        z_liquidity = _normalize_cross_section(np.log1p(liquidity.clip(lower=0.0)))
        z_volatility = _normalize_cross_section(volatility)
        z_liquidity_cv = _normalize_cross_section(liquidity_cv)

        score = z_small * self.config.size_weight
        score = score.add(z_momentum * self.config.momentum_weight, fill_value=0.0)
        score = score.add(z_liquidity * self.config.liquidity_weight, fill_value=0.0)
        score = score.sub(z_volatility * self.config.volatility_penalty, fill_value=0.0)
        score = score.sub(z_liquidity_cv * self.config.liquidity_cv_penalty, fill_value=0.0)

        history_ready = close.notna().cumsum() >= self.config.min_history_days
        liquidity_percentile = liquidity.rank(axis=1, pct=True, ascending=True)
        tradeable_mask = history_ready & (liquidity >= self.config.min_liquidity_amount)
        tradeable_mask = tradeable_mask & (liquidity_percentile >= self.config.min_liquidity_percentile)
        if self.config.min_price > 0:
            tradeable_mask = tradeable_mask & (close >= self.config.min_price)

        regime_on = self._build_regime_mask(close)

        filtered = score.where(tradeable_mask)
        filtered = filtered.where(regime_on, np.nan)
        filtered = filtered.replace([np.inf, -np.inf], np.nan).dropna(how="all")
        stacked = filtered.stack().dropna()
        stacked.index.names = ["datetime", "instrument"]
        return stacked.to_frame("score")

    @staticmethod
    def _allowed_columns(columns, *, exclude_bj: bool, exclude_kcb: bool) -> list[str]:
        allowed: list[str] = []
        for code in columns:
            instrument = str(code).strip().upper()
            if exclude_bj and instrument.endswith(".BJ"):
                continue
            if exclude_kcb and instrument.endswith(".SH") and instrument.split(".", 1)[0].startswith(("688", "689")):
                continue
            allowed.append(instrument)
        return allowed

    def _build_regime_mask(self, close: pd.DataFrame) -> pd.Series:
        returns = close.pct_change(fill_method=None)
        market_curve = (1.0 + returns.mean(axis=1).fillna(0.0)).cumprod()
        market_ma = market_curve.rolling(self.config.regime_ma_days).mean()
        market_return = market_curve.pct_change(self.config.regime_lookback_days)
        breadth = (close > close.rolling(self.config.regime_ma_days).mean()).mean(axis=1)
        regime_on = (
            (market_curve >= market_ma)
            & (market_return >= self.config.regime_min_return)
            & (breadth >= self.config.regime_min_breadth)
        )
        regime_on = regime_on.fillna(False)
        return pd.Series(np.where(regime_on, True, False), index=close.index)

    @staticmethod
    def _require_field(market_data: dict[str, pd.DataFrame], field: str) -> pd.DataFrame:
        if field not in market_data or market_data[field] is None or market_data[field].empty:
            raise ValueError(f"market_data missing required field `{field}`")
        return market_data[field]


def rows_to_market_data(rows: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    if df.empty:
        return {}
    if "trade_date" not in df.columns:
        raise ValueError("rows missing trade_date")

    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["trade_date", "ts_code"])
    df["ts_code"] = df["ts_code"].astype(str).str.upper()

    fields = [name for name in ["open", "high", "low", "close", "volume", "amount"] if name in df.columns]
    market_data: dict[str, pd.DataFrame] = {}
    for field in fields:
        df[field] = pd.to_numeric(df[field], errors="coerce")
        pivot = df.pivot_table(index="trade_date", columns="ts_code", values=field, aggfunc="last")
        pivot = pivot.sort_index().sort_index(axis=1)
        market_data[field] = pivot
    return market_data


def fetch_daily_rows(
    client: QmtGatewayClient,
    stock_list: list[str],
    *,
    start_date: str,
    end_date: str,
    batch_size: int = 200,
    dividend_type: str = "none",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(0, len(stock_list), max(1, batch_size)):
        batch = [code for code in stock_list[idx : idx + max(1, batch_size)] if code]
        if not batch:
            continue
        payload = client.get_kline_rows(
            batch,
            period="1d",
            start_time=start_date,
            end_time=end_date,
            count=-1,
            dividend_type=dividend_type,
            fill_data=True,
            download=True,
        )
        items = payload.get("rows", []) if isinstance(payload, dict) else []
        if isinstance(items, list):
            rows.extend([item for item in items if isinstance(item, dict)])
    return rows


def _calc_submit_price(latest_close: float, order_type: str, price_type: str, offset_bps: float) -> float:
    if price_type != "fix":
        return 0.0
    ratio = abs(float(offset_bps)) / 10000.0
    if order_type == "sell":
        return round(max(0.01, latest_close * (1.0 - ratio)), 3)
    return round(max(0.01, latest_close * (1.0 + ratio)), 3)


def _calc_order_volume(
    *,
    latest_close: float,
    submit_price: float,
    price_type: str,
    lot_size: int,
    budget_per_order: float,
) -> int:
    volume_price = submit_price if price_type == "fix" else latest_close
    if volume_price <= 0:
        return 0
    volume = int(float(budget_per_order) // volume_price)
    if lot_size > 1:
        volume = (volume // lot_size) * lot_size
    return max(volume, 0)


def run_small_cap_enhanced_proxy_demo(
    client: QmtGatewayClient,
    *,
    sector_name: str = DEFAULT_A_STOCK_SECTOR,
    stock_limit: int = 300,
    lookback_days: int = 220,
    top_n: int = 10,
    order_type: str = "buy",
    price_type: str = "market",
    price_offset_bps: float = 20.0,
    budget_per_order: float = 20_000.0,
    lot_size: int = 100,
    account_id: str = "",
    account_type: str = "STOCK",
    submit: bool = False,
    dedupe: bool = True,
    strategy_name: str = "small_cap_enhanced_qmt_proxy_demo",
    order_remark_prefix: str = "small-cap-proxy",
    config: SmallCapEnhancedProxyConfig | None = None,
) -> dict[str, Any]:
    strategy_config = config or SmallCapEnhancedProxyConfig()
    sector_payload = client.sector_stocks(sector_name)
    universe = list(sector_payload.get("items", []))
    if stock_limit > 0:
        universe = universe[:stock_limit]
    if not universe:
        raise RuntimeError("selected universe is empty")

    end_day = date.today()
    start_day = end_day - timedelta(days=max(lookback_days * 2, lookback_days + 120))
    start_date = start_day.strftime("%Y%m%d")
    end_date = end_day.strftime("%Y%m%d")

    rows = fetch_daily_rows(client, universe, start_date=start_date, end_date=end_date)
    market_data = rows_to_market_data(rows)
    signal = SmallCapEnhancedProxyStrategy(strategy_config).build_signal(market_data)
    if signal.empty:
        raise RuntimeError("strategy returned empty signal")

    signal_rows = signal.reset_index().rename(columns={"datetime": "datetime", "instrument": "instrument"})
    latest_signal_dt = pd.to_datetime(signal_rows["datetime"]).max()
    latest_signals = signal_rows[pd.to_datetime(signal_rows["datetime"]) == latest_signal_dt].copy()
    latest_signals = latest_signals.sort_values("score", ascending=False)

    close = market_data["close"]
    latest_close_dt = pd.to_datetime(close.index).max()
    latest_close_row = close.loc[latest_close_dt]

    planned_orders: list[dict[str, Any]] = []
    for _, item in latest_signals.head(top_n).iterrows():
        ts_code = str(item["instrument"]).strip().upper()
        if ts_code not in latest_close_row.index:
            continue
        latest_close = latest_close_row.get(ts_code)
        if latest_close is None or pd.isna(latest_close):
            continue
        latest_close = float(latest_close)
        submit_price = _calc_submit_price(latest_close, order_type, price_type, price_offset_bps)
        volume = _calc_order_volume(
            latest_close=latest_close,
            submit_price=submit_price,
            price_type=price_type,
            lot_size=lot_size,
            budget_per_order=budget_per_order,
        )
        if volume <= 0:
            continue
        amount_estimate = (submit_price if price_type == "fix" else latest_close) * volume
        planned_orders.append(
            {
                "ts_code": ts_code,
                "score": float(item["score"]),
                "latest_close": latest_close,
                "submit_price": submit_price,
                "volume": volume,
                "amount_estimate": float(amount_estimate),
                "signal_date": pd.Timestamp(latest_signal_dt).strftime("%Y-%m-%d"),
            }
        )

    submitted_orders: list[dict[str, Any]] = []
    existing_remarks: set[str] = set()
    if submit:
        if not account_id.strip():
            raise ValueError("account_id is required when submit=True")
        if dedupe:
            try:
                existing_orders = client.query_orders(account_id=account_id, account_type=account_type)
                for item in existing_orders:
                    remark = str(item.get("order_remark") or "").strip()
                    if remark:
                        existing_remarks.add(remark)
            except Exception:
                existing_remarks = set()

        for plan in planned_orders:
            order_remark = f"{order_remark_prefix}:{plan['ts_code']}:{plan['signal_date']}:{order_type}:{strategy_name}"
            if dedupe and order_remark in existing_remarks:
                submitted_orders.append(
                    {
                        "ts_code": plan["ts_code"],
                        "success": False,
                        "submitted": False,
                        "duplicate_skipped": True,
                        "error": "duplicate_skipped",
                        "order_remark": order_remark,
                    }
                )
                continue
            request_payload = {
                "account_id": account_id,
                "account_type": account_type,
                "stock_code": plan["ts_code"],
                "order_type": order_type,
                "volume": plan["volume"],
                "price_type": price_type,
                "price": plan["submit_price"] if price_type == "fix" else 0.0,
                "strategy_name": strategy_name,
                "order_remark": order_remark,
            }
            try:
                response = client.order_stock(**request_payload)
                submitted_orders.append(
                    {
                        "ts_code": plan["ts_code"],
                        "success": True,
                        "submitted": True,
                        "duplicate_skipped": False,
                        "request": request_payload,
                        "response": response,
                    }
                )
                existing_remarks.add(order_remark)
            except Exception as exc:
                submitted_orders.append(
                    {
                        "ts_code": plan["ts_code"],
                        "success": False,
                        "submitted": True,
                        "duplicate_skipped": False,
                        "request": request_payload,
                        "error": str(exc),
                    }
                )

    return {
        "strategy_key": "small_cap_enhanced.qmt_proxy.v1",
        "proxy_mode": "QMT-only amount/liquidity proxy",
        "proxy_notice": (
            "This demo does not use real historical circ_mv or total_mv. "
            "It uses turnover amount and liquidity as a small-cap proxy and must not be described as a strict historical market-cap strategy."
        ),
        "sector_name": sector_name,
        "universe_count": len(sector_payload.get("items", [])),
        "selected_universe_count": len(universe),
        "start_date": start_date,
        "end_date": end_date,
        "latest_signal_date": pd.Timestamp(latest_signal_dt).strftime("%Y-%m-%d"),
        "latest_close_date": pd.Timestamp(latest_close_dt).strftime("%Y-%m-%d"),
        "params": strategy_config.to_dict(),
        "planned_orders": planned_orders,
        "submitted_orders": submitted_orders,
        "submit_enabled": bool(submit),
        "account_id": account_id if submit else "",
        "account_type": account_type if submit else "",
        "order_type": order_type,
        "price_type": price_type,
        "budget_per_order": budget_per_order,
        "lot_size": lot_size,
        "strategy_name": strategy_name,
    }
