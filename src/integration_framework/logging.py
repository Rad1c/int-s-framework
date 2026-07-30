"""
Logging setup with optional daily file rotation and retention cleanup.
Port of the betbox LogManager, applied to the root logger so that all
module-level loggers (framework and service code alike) share the config.
"""

import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging(level: str = "INFO", log_file: str = "", retention_days: int = 7) -> None:
    """Configure the root logger with a console handler and, when log_file is
    set, a daily-rotating file handler. Old rotated files past retention_days
    are removed at startup. Safe to call more than once (handlers are reset)."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = TimedRotatingFileHandler(
            log_file, when="midnight", backupCount=retention_days, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        _cleanup_old_logs(log_file, retention_days)


def _cleanup_old_logs(log_file: str, retention_days: int) -> None:
    """Remove rotated log files older than retention_days (rotated files are
    named <log_file>.<suffix> in the same directory)."""
    path = Path(log_file)
    directory = path.parent if str(path.parent) else Path(".")
    if not directory.exists():
        return

    cutoff = time.time() - retention_days * 86400
    for candidate in directory.glob(f"{path.name}.*"):
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink()
        except OSError:  # pragma: no cover - best-effort cleanup
            pass
