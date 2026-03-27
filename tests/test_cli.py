from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from quant_qmt import cli
from quant_qmt.cli import _write_output, build_parser


def test_build_parser_accepts_new_subcommands() -> None:
    parser = build_parser()

    args = parser.parse_args(["data", "cb-info"])
    assert args.data_command == "cb-info"

    args = parser.parse_args(["data", "full-tick", "--stock-list", "600000.SH"])
    assert args.data_command == "full-tick"

    args = parser.parse_args(["trade", "order-info", "--account-id", "1", "--order-id", "2"])
    assert args.trade_command == "order-info"

    args = parser.parse_args(["trade", "order", "--account-id", "1", "--stock-code", "600000.SH", "--volume", "100", "--output", "out.json"])
    assert args.output == "out.json"

    args = parser.parse_args(["trade", "cancel", "--account-id", "1", "--order-id", "2", "--output", "cancel.json"])
    assert args.output == "cancel.json"


def test_write_output_writes_json_and_csv(tmp_path: Path) -> None:
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"

    _write_output({"hello": "world"}, str(json_path))
    _write_output([{"ts_code": "600000.SH", "close": 10.2}], str(csv_path))

    assert json.loads(json_path.read_text(encoding="utf-8"))["hello"] == "world"
    assert "600000.SH" in csv_path.read_text(encoding="utf-8-sig")


class _DummyClient:
    def order_stock(self, **kwargs):
        return {"order_id": 1, "payload": kwargs}

    def cancel_order(self, **kwargs):
        return {"ok": True, "payload": kwargs}


def test_cmd_trade_order_requires_positive_limit_price(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_client_from_args", lambda args: _DummyClient())
    args = argparse.Namespace(
        account_id="1",
        account_type="STOCK",
        stock_code="600000.SH",
        order_type="buy",
        volume=100,
        price_type="fix",
        price=None,
        strategy_name="demo",
        order_remark="",
        async_mode=False,
        output="",
    )

    with pytest.raises(ValueError, match="price must be > 0"):
        cli.cmd_trade_order(args)


def test_cmd_trade_cancel_requires_identifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_client_from_args", lambda args: _DummyClient())
    args = argparse.Namespace(
        account_id="1",
        account_type="STOCK",
        order_id=None,
        order_sysid="",
        market="",
        async_mode=False,
        output="",
    )

    with pytest.raises(ValueError, match="either order_id or order_sysid"):
        cli.cmd_trade_cancel(args)
