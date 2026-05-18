import logging
from typing import Any


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    """Emite un log con campos estructurados para Cloud Logging."""
    logger.log(level, message, extra=fields)
