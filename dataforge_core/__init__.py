"""
DataForge Core Module Initialization
Exports main framework components and utilities.
"""

from dataforge_core.config import (
    ConfigurationManager,
    get_config,
    DataForgeConfig,
    EnvironmentType
)

from dataforge_core.logging_config import setup_logging, get_logger
from dataforge_core.metadata import MetadataManager
from dataforge_core.observability import MetricsCollector

__version__ = "0.1.0"
__author__ = "DataForge Engineering Team"

__all__ = [
    'ConfigurationManager',
    'get_config',
    'DataForgeConfig',
    'EnvironmentType',
    'setup_logging',
    'get_logger',
    'MetadataManager',
    'MetricsCollector',
]
