"""
Structured Logging Configuration for DataForge Platform.
Implements enterprise-grade logging with structured output support.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pythonjsonlogger import jsonlogger


class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['logger_name'] = record.name
        log_record['log_level'] = record.levelname
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line_number'] = record.lineno
        
        # Add custom fields if present
        if hasattr(record, 'pipeline_id'):
            log_record['pipeline_id'] = record.pipeline_id
        if hasattr(record, 'stage_name'):
            log_record['stage_name'] = record.stage_name
        if hasattr(record, 'record_count'):
            log_record['record_count'] = record.record_count


def setup_logging(
    name: str = "dataforge",
    level: str = "INFO",
    use_json: bool = True
) -> logging.Logger:
    """
    Setup structured logging for DataForge components.

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Use JSON format for structured logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if use_json:
        formatter = StructuredFormatter(
            '%(timestamp)s %(logger_name)s %(log_level)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger for the given name."""
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding temporary fields to logs."""

    def __init__(self, pipeline_id: Optional[str] = None, stage_name: Optional[str] = None):
        self.pipeline_id = pipeline_id
        self.stage_name = stage_name
        self._original_pipeline_id = None
        self._original_stage_name = None

    def __enter__(self):
        for handler in logging.root.handlers:
            if self.pipeline_id:
                self._original_pipeline_id = getattr(handler, 'pipeline_id', None)
                handler.pipeline_id = self.pipeline_id
            if self.stage_name:
                self._original_stage_name = getattr(handler, 'stage_name', None)
                handler.stage_name = self.stage_name
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for handler in logging.root.handlers:
            if self._original_pipeline_id is not None:
                handler.pipeline_id = self._original_pipeline_id
            if self._original_stage_name is not None:
                handler.stage_name = self._original_stage_name
