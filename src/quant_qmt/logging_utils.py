from __future__ import annotations

import logging
import os


def configure_logging(level: str | None = None) -> None:
    resolved = (level or os.getenv("QUANT_QMT_LOG_LEVEL", "INFO")).upper()
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(resolved)
        return

    logging.basicConfig(
        level=resolved,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

