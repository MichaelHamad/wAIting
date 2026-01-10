"""Logging configuration for the Waiting system."""

import logging
from pathlib import Path


def setup_logging() -> logging.Logger:
    """
    Configure logging to ~/.waiting.log

    Returns:
        logging.Logger: Configured logger instance
    """
    log_path = Path.home() / ".waiting.log"

    # Create logger
    logger = logging.getLogger("waiting")
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # Create file handler
    try:
        handler = logging.FileHandler(log_path)
        handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
    except OSError as e:
        # If log file can't be created, log to console as fallback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        logger.addHandler(console_handler)
        logger.warning(f"Could not create log file at {log_path}: {e}")

    return logger
