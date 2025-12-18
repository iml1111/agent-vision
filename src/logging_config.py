"""Application logging configuration using Python standard logging."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure application-wide logging.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to INFO.
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified module.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Configured Logger instance.
    """
    return logging.getLogger(name)
