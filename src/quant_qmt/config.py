from __future__ import annotations

import os
import site
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _split_paths(raw: str) -> list[str]:
    if not raw:
        return []
    parts: list[str] = []
    for item in raw.split(os.pathsep):
        value = item.strip().strip('"')
        if value:
            parts.append(value)
    return parts


def _is_xtquant_site_packages(path: Path) -> bool:
    return (path / "xtquant").exists() or (path / "xtquant.py").exists()


def _discover_xtquant_paths_from_qmt_path() -> list[str]:
    qmt_path = os.getenv("QMT_PATH", "").strip()
    if not qmt_path:
        return []

    qmt_dir = Path(qmt_path).expanduser()
    roots: list[Path] = []
    if qmt_dir.parent != qmt_dir:
        roots.append(qmt_dir.parent)
    if len(qmt_dir.parents) > 1:
        roots.append(qmt_dir.parents[1])

    candidates: list[str] = []
    seen: set[str] = set()
    for root in roots:
        site_packages = root / "bin.x64" / "Lib" / "site-packages"
        if not site_packages.exists() or not _is_xtquant_site_packages(site_packages):
            continue
        text = str(site_packages.resolve())
        if text in seen:
            continue
        seen.add(text)
        candidates.append(text)
    return candidates


def configure_import_paths() -> list[str]:
    added: list[str] = []
    candidates: list[str] = []
    for env_name in ("QMT_XTQUANT_PATH", "QMT_PYTHONPATH"):
        candidates.extend(_split_paths(os.getenv(env_name, "")))
    candidates.extend(_discover_xtquant_paths_from_qmt_path())

    for raw_path in candidates:
        path = Path(raw_path).expanduser()
        if not path.exists():
            continue
        text = str(path.resolve())
        if text in sys.path:
            continue
        site.addsitedir(text)
        added.append(text)
    return added


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    text = value.strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def env_text(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def gateway_base_url(default: str = "http://127.0.0.1:9527") -> str:
    return env_text("QMT_GATEWAY_URL", default) or default


@dataclass(frozen=True)
class GatewayServerConfig:
    host: str
    port: int
    qmt_path: str
    session_id: int
    reconnect_interval: int
    callback_buffer_size: int
    callback_log_file: str
    default_account_id: str

    @classmethod
    def from_env(cls) -> "GatewayServerConfig":
        return cls(
            host=env_text("QMT_GATEWAY_HOST", "127.0.0.1"),
            port=env_int("QMT_GATEWAY_PORT", 9527),
            qmt_path=env_text("QMT_PATH", ""),
            session_id=env_int("QMT_SESSION_ID", 123456),
            reconnect_interval=env_int("QMT_RECONNECT_INTERVAL", 10),
            callback_buffer_size=max(env_int("QMT_CALLBACK_BUFFER_SIZE", 1000), 100),
            callback_log_file=env_text("QMT_CALLBACK_LOG_FILE", r"var\callbacks\callbacks.jsonl"),
            default_account_id=env_text("QMT_DEFAULT_ACCOUNT_ID", ""),
        )


@dataclass(frozen=True)
class ClientConfig:
    base_url: str
    timeout: int

    @classmethod
    def from_env(cls) -> "ClientConfig":
        return cls(
            base_url=gateway_base_url(),
            timeout=env_int("QMT_CLIENT_TIMEOUT_SEC", 15),
        )


def public_env_snapshot() -> dict[str, Any]:
    return {
        "QMT_PATH": env_text("QMT_PATH", ""),
        "QMT_SESSION_ID": env_text("QMT_SESSION_ID", ""),
        "QMT_GATEWAY_HOST": env_text("QMT_GATEWAY_HOST", ""),
        "QMT_GATEWAY_PORT": env_text("QMT_GATEWAY_PORT", ""),
        "QMT_GATEWAY_URL": env_text("QMT_GATEWAY_URL", ""),
        "QMT_CALLBACK_LOG_FILE": env_text("QMT_CALLBACK_LOG_FILE", ""),
        "QMT_XTQUANT_PATH": env_text("QMT_XTQUANT_PATH", ""),
        "QMT_PYTHONPATH": env_text("QMT_PYTHONPATH", ""),
    }
