from __future__ import annotations

"""Application logging kept independent of Qt so startup failures are recorded."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


_LOGGER_NAME = "elplan"


def configure_logging(log_dir: str | Path) -> Path:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "elplan.log"
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not any(isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == path.resolve() for handler in logger.handlers):
        handler = RotatingFileHandler(path, maxBytes=1_500_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    return path


def install_exception_hook() -> None:
    """Log otherwise-unhandled Python exceptions before normal handling."""
    previous = sys.excepthook

    def _hook(exc_type, exc_value, exc_traceback):
        logging.getLogger(_LOGGER_NAME).critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback)
        )
        previous(exc_type, exc_value, exc_traceback)

    sys.excepthook = _hook
