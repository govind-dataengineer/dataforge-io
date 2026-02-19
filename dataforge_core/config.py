"""
DataForge Configuration Management Module
Handles environment-specific configurations with validation and defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EnvironmentType(str, Enum):
    DEV = "dev"
    QA = "qa"
    PROD = "prod"


class StorageType(str, Enum):
    MINIO = "minio"
    ADLS2 = "adls2"
    S3 = "s3"


class CloudConfig(BaseModel):
    storage_type: StorageType
    endpoint: str
    access_key: str = Field(..., exclude=True)
    secret_key: str = Field(..., exclude=True)
    use_ssl: bool = True

    class Config:
        use_enum_values = True


class LakehouseConfig(BaseModel):
    bronze_path: str
    silver_path: str
    gold_path: str
    delta_enable_cdc: bool = False
    delta_enable_deletion_vectors: bool = True
    auto_compact_interval: int = 86400


class SparkConfig(BaseModel):
    master_url: str
    app_name: str
    configs: Dict[str, Any] = {}


class DatabaseConfig(BaseModel):
    type: str
    host: str
    port: int
    username: str = Field(..., exclude=True)
    password: str = Field(..., exclude=True)
    ssl_enabled: bool = False
    databases: Dict[str, str] = {}


class KafkaConfig(BaseModel):
    bootstrap_servers: str
    schema_registry_url: Optional[str] = None
    consumer_group: str = "dataforge"
    auto_offset_reset: str = "earliest"


class DataQualityConfig(BaseModel):
    enable_schema_validation: bool = True
    enable_data_profiling: bool = False
    enable_duplicate_check: bool = True
    enable_null_check: bool = True
    quality_threshold: float = 0.95

    @validator('quality_threshold')
    def validate_threshold(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('quality_threshold must be between 0 and 1')
        return v


class ObservabilityConfig(BaseModel):
    log_level: str = "INFO"
    enable_structured_logging: bool = True
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_lineage_tracking: bool = True


class CostOptimizationConfig(BaseModel):
    enable_partition_pruning: bool = True
    enable_file_compaction: bool = True
    file_compaction_interval_hours: int = 24
    auto_scaling_enabled: bool = False
    compression_codec: str = "snappy"


class DataForgeConfig(BaseModel):
    environment: EnvironmentType
    cloud: CloudConfig
    lakehouse: LakehouseConfig
    spark: SparkConfig
    database: DatabaseConfig
    kafka: KafkaConfig
    data_quality: DataQualityConfig = DataQualityConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    cost_optimization: CostOptimizationConfig = CostOptimizationConfig()

    class Config:
        use_enum_values = True


class ConfigurationManager:
    """
    Enterprise-grade configuration manager with environment variable substitution.
    Implements singleton pattern for thread-safe config access.
    """

    _instance = None
    _config = None
    _config_path = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigurationManager, cls).__new__(cls)
        return cls._instance

    def load_config(self, environment: Optional[str] = None, config_path: Optional[str] = None) -> DataForgeConfig:
        """
        Load configuration from YAML file with environment variable substitution.

        Args:
            environment: Environment name (dev, qa, prod). Defaults to DATAFORGE_ENV env var.
            config_path: Path to configs directory. Defaults to './configs'

        Returns:
            DataForgeConfig object with validated configuration
        """
        if self._config is not None:
            return self._config

        env = environment or os.getenv('DATAFORGE_ENV', 'dev').lower()
        config_dir = Path(config_path or os.getenv('DATAFORGE_CONFIG_PATH', './configs'))

        config_file = config_dir / f"{env}.yaml"

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        logger.info(f"Loading configuration from: {config_file}")

        with open(config_file, 'r') as f:
            raw_config = yaml.safe_load(f)

        # Substitute environment variables
        raw_config = self._substitute_env_vars(raw_config)

        # Validate configuration
        try:
            self._config = DataForgeConfig(**raw_config)
            logger.info(f"Configuration loaded successfully for environment: {env}")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

        return self._config

    @staticmethod
    def _substitute_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively substitute ${VAR_NAME} with environment variables.
        """
        if isinstance(config, dict):
            return {k: ConfigurationManager._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [ConfigurationManager._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Replace ${VAR_NAME} pattern
            import re
            pattern = r'\$\{(\w+)(?::([^}]*))?}'
            
            def replace_var(match):
                var_name = match.group(1)
                default_value = match.group(2)
                return os.getenv(var_name, default_value or match.group(0))
            
            return re.sub(pattern, replace_var, config)
        else:
            return config

    def get_config(self) -> DataForgeConfig:
        """Get loaded configuration."""
        if self._config is None:
            self.load_config()
        return self._config

    def reset(self):
        """Reset configuration (useful for testing)."""
        self._config = None

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary (excluding secrets)."""
        if self._config is None:
            raise RuntimeError("Configuration not loaded")
        return self._config.dict(exclude_none=True)


# Global config instance
config_manager = ConfigurationManager()


def get_config() -> DataForgeConfig:
    """Convenience function to get global config."""
    return config_manager.get_config()
