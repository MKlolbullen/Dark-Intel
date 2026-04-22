"""Centralized stdlib logging config.

Called once from `create_app()` (web) and the Qt entry point. Idempotent
so repeated calls during test imports don't stack handlers.
"""

from __future__ import annotations

import logging
import os

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"


def configure() -> None:
    level_name = os.getenv("DARK_INTEL_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if getattr(root, "_dark_intel_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    root.handlers = [handler]
    root.setLevel(level)
    # Quiet down the noisier libs so our logs actually stand out.
    for noisy in ("httpx", "httpcore", "urllib3", "openai", "anthropic"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))
    root._dark_intel_configured = True  # type: ignore[attr-defined]
