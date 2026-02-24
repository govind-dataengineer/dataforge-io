"""
DataForge Core Module
Handles configuration, logging, storage, and Spark session management.
"""

import os
import yaml
import logging
import structlog
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, DateType, LongType


# ============================================================================
# Logging Setup
# ============================================================================
def setup_logging(name: str, level: str = "INFO") -> logging.Logger:
    """Configure structured logging with structlog."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger(name)
    return logger


logger = setup_logging(__name__)


# ============================================================================
# Configuration Management
# ============================================================================
@dataclass
class StorageConfig:
    type: str
    endpoint: str
    access_key: str
    secret_key: str
    bucket_base: str
    bronze_path: str
    silver_path: str
    gold_path: str
    silver_retention_days: int
    gold_retention_days: int


@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    schema: str


@dataclass
class SparkConfig:
    master: str
    app_name: str
    executor_cores: int
    executor_memory: str
    driver_memory: str
    partitions: int


class ConfigManager:
    """Load and manage application configuration."""
    
    def __init__(self, config_path: str = "configs/config.yaml", env_override: Optional[str] = None):
        self.config_path = Path(config_path)
        self.env_override = env_override
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load base config and apply environment override."""
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if self.env_override and Path(self.env_override).exists():
            with open(self.env_override, 'r') as f:
                env_config = yaml.safe_load(f) or {}
                self._deep_merge(config, env_config)
        
        return config
    
    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> None:
        """Deep merge override into base config."""
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot notation (e.g., 'storage.endpoint')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def to_dict(self) -> Dict[str, Any]:
        """Return full config as dictionary."""
        return self.config


# ============================================================================
# Spark Session Management
# ============================================================================
class SparkSessionManager:
    """Centralized Spark session factory."""
    
    _instance: Optional[SparkSession] = None
    
    @classmethod
    def get_or_create(cls, config: ConfigManager) -> SparkSession:
        """Get or create Spark session."""
        if cls._instance is None or not cls._instance.sparkContext._jsc.sc().isStopped():
            spark_config = config.get('spark', {})
            
            builder = (
                SparkSession.builder
                .appName(spark_config.get('app_name', 'DataForge'))
                .master(spark_config.get('master', 'local[4]'))
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
                .config("spark.hadoop.fs.s3a.endpoint", config.get('storage.endpoint'))
                .config("spark.hadoop.fs.s3a.access.key", config.get('storage.access_key'))
                .config("spark.hadoop.fs.s3a.secret.key", config.get('storage.secret_key'))
                .config("spark.hadoop.fs.s3a.path.style.access", "true")
                .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            )
            
            cls._instance = builder.getOrCreate()
            logger.info("Spark session created", app_name=spark_config.get('app_name'))
        
        return cls._instance
    
    @classmethod
    def stop(cls):
        """Stop Spark session."""
        if cls._instance:
            cls._instance.stop()
            cls._instance = None
            logger.info("Spark session stopped")


# ============================================================================
# Schema Definitions
# ============================================================================
class Schemas:
    """Standard schemas for financial data."""
    
    @staticmethod
    def stock_ohlc() -> StructType:
        """Historical OHLC stock data schema."""
        return StructType([
            StructField("date", DateType(), False),
            StructField("symbol", StringType(), False),
            StructField("open", DoubleType(), True),
            StructField("high", DoubleType(), True),
            StructField("low", DoubleType(), True),
            StructField("close", DoubleType(), True),
            StructField("adjusted_close", DoubleType(), True),
            StructField("volume", LongType(), True),
        ])
    
    @staticmethod
    def stock_metadata() -> StructType:
        """Stock metadata schema."""
        return StructType([
            StructField("symbol", StringType(), False),
            StructField("company_name", StringType(), True),
            StructField("sector", StringType(), True),
            StructField("market_cap", StringType(), True),
            StructField("updated_at", StringType(), True),
        ])


# ============================================================================
# Storage Utilities
# ============================================================================
class StorageHelper:
    """Utilities for storage operations."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def get_path(self, layer: str) -> str:
        """Get storage path for a layer (bronze/silver/gold)."""
        return self.config.get(f'storage.{layer}_path')
    
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        db = self.config.get('database', {})
        return (
            f"postgresql://{db.get('user')}:{db.get('password')}"
            f"@{db.get('host')}:{db.get('port')}/{db.get('database')}"
        )
    
    def get_s3a_options(self) -> Dict[str, str]:
        """Get S3A options for Spark."""
        return {
            "fs.s3a.endpoint": self.config.get('storage.endpoint'),
            "fs.s3a.access.key": self.config.get('storage.access_key'),
            "fs.s3a.secret.key": self.config.get('storage.secret_key'),
            "fs.s3a.path.style.access": "true",
        }


# ============================================================================
# Global Initialization
# ============================================================================
def initialize_dataforge(config_path: str = "configs/config.yaml", env_override: Optional[str] = None):
    """Initialize DataForge platform."""
    config = ConfigManager(config_path=config_path, env_override=env_override)
    spark = SparkSessionManager.get_or_create(config)
    
    logger.info(
        "DataForge initialized",
        environment=config.get('environment'),
        version=config.get('version'),
        spark_master=config.get('spark.master')
    )
    
    return config, spark
