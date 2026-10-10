"""Logging configuration for the Tokenly backend."""

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Give the root logger one console handler at the given level; safe to call again."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    if root_logger.handlers:
        return
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console_handler)
