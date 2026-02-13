"""
Centralized logging configuration.
Uses Python's built-in logging (no external services required).

Logs are automatically captured by AWS CloudWatch via ECS awslogs driver.
"""

import logging
import os
import sys
import json
import traceback
from datetime import datetime, timezone


class CloudWatchFormatter(logging.Formatter):
    """JSON formatter for structured CloudWatch logs."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        if hasattr(record, 'extra_data'):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry)


def setup_logger(name: str = "secondbrain") -> logging.Logger:
    """
    Set up structured logger with consistent formatting.

    Logs are captured by AWS CloudWatch via ECS awslogs driver.

    Args:
        name: Logger name (typically module name)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if logger.handlers:
        return logger

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Console handler (captured by CloudWatch)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level, logging.INFO))

    # Use JSON format in production, readable format in dev
    if os.getenv("FLASK_ENV") == "production":
        handler.setFormatter(CloudWatchFormatter())
    else:
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False  # Don't propagate to root logger

    return logger


# Convenience functions for quick logging

def log_info(module: str, message: str, **kwargs):
    """
    Log info with context.

    Example:
        log_info("BoxConnector", "Starting sync", folder_id="12345", tenant_id="abc")
    """
    logger = setup_logger(module)
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.info(f"{message} {extra_info}" if extra_info else message)


def log_error(module: str, message: str, error: Exception = None, **kwargs):
    """
    Log error with context.

    Example:
        log_error("BoxConnector", "Download failed", error=e, file_id="12345")
    """
    logger = setup_logger(module)
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    full_message = f"{message} {extra_info}" if extra_info else message
    if error:
        logger.error(f"{full_message} | Error: {str(error)}", exc_info=True)
    else:
        logger.error(full_message)


def log_warning(module: str, message: str, **kwargs):
    """
    Log warning with context.

    Example:
        log_warning("BoxConnector", "File size exceeds limit", file_size=10000000)
    """
    logger = setup_logger(module)
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.warning(f"{message} {extra_info}" if extra_info else message)


def log_debug(module: str, message: str, **kwargs):
    """
    Log debug information.

    Only visible when log level is set to DEBUG.

    Example:
        log_debug("BoxConnector", "Processing file", file_name="doc.pdf")
    """
    logger = setup_logger(module)
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.debug(f"{message} {extra_info}" if extra_info else message)


# Module-level logger instance for direct use
logger = setup_logger()
