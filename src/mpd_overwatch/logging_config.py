"""Logging configuration for MPD Overwatch."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application.

    Args:
        level: One of DEBUG, INFO, WARNING, ERROR.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.setLevel(numeric_level)

    root = logging.getLogger("mpd_overwatch")
    root.setLevel(numeric_level)
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("dash").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
