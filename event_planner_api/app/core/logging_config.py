"""
Basic logging configuration for the application.

The ``setup_logging`` function configures the root logger with a
console and file handler.  Log format includes the timestamp, logger
name, log level and message.  In production, you may wish to adjust
handlers (for example, sending logs to an external system) or rotate
log files.  This module ensures that logging is set up exactly once.
"""

import logging
from pathlib import Path
from typing import Optional


def setup_logging(level: str = "INFO", logfile: Optional[str] = None) -> None:
    """Configure root logger.

    If no handlers are attached to the root logger, attach a
    console handler and optionally a file handler.  The root
    logger's level is set based on the provided ``level``.

    Parameters
    ----------
    level : str
        Logging level name (e.g. ``"DEBUG"``, ``"INFO"``).  Case
        insensitive.
    logfile : Optional[str]
        Path to a file to log messages to.  If omitted, no file
        handler is added.  Paths are resolved relative to the
        current working directory.
    """
    logger = logging.getLogger()
    if logger.handlers:
        # Avoid configuring logging multiple times.  This can happen when
        # running tests or when ``create_app`` is called repeatedly.
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if logfile:
        log_path = Path(logfile).resolve()
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)