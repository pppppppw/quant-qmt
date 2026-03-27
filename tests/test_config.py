from __future__ import annotations

import sys

from quant_qmt.config import GatewayServerConfig, configure_import_paths


def test_gateway_server_config_requires_explicit_qmt_path(monkeypatch) -> None:
    monkeypatch.delenv("QMT_PATH", raising=False)

    config = GatewayServerConfig.from_env()

    assert config.qmt_path == ""


def test_configure_import_paths_auto_discovers_xtquant_from_qmt_path(monkeypatch, tmp_path) -> None:
    qmt_root = tmp_path / "MiniQMT"
    userdata_dir = qmt_root / "userdata_mini"
    site_packages = qmt_root / "bin.x64" / "Lib" / "site-packages" / "xtquant"
    site_packages.mkdir(parents=True)
    (site_packages / "__init__.py").write_text("", encoding="utf-8")
    userdata_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("QMT_PATH", str(userdata_dir))
    monkeypatch.delenv("QMT_XTQUANT_PATH", raising=False)
    monkeypatch.delenv("QMT_PYTHONPATH", raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))

    added = configure_import_paths()

    assert str((qmt_root / "bin.x64" / "Lib" / "site-packages").resolve()) in added
