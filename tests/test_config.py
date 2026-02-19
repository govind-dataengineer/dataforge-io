"""
Unit tests for DataForge configuration management
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from dataforge_core.config import ConfigurationManager, DataForgeConfig, EnvironmentType, StorageType


class TestConfigurationManager:
    """Tests for configuration loading and validation."""

    def test_load_dev_config(self):
        """Test loading development configuration."""
        manager = ConfigurationManager()
        manager.reset()
        config = manager.load_config(environment="dev", config_path="./configs")
        
        assert config.environment == EnvironmentType.DEV
        assert config.cloud.storage_type == StorageType.MINIO
        assert config.spark.app_name == "DataForge"

    def test_config_validation(self):
        """Test configuration validation."""
        manager = ConfigurationManager()
        manager.reset()
        
        # Test invalid quality threshold
        with pytest.raises(ValueError):
            config_dict = {
                'environment': 'dev',
                'cloud': {
                    'storage_type': 'minio',
                    'endpoint': 'http://minio:9000',
                    'access_key': 'test',
                    'secret_key': 'test'
                },
                'data_quality': {
                    'quality_threshold': 1.5  # Invalid: must be 0-1
                }
            }
            DataForgeConfig(**config_dict)

    def test_environment_variable_substitution(self):
        """Test ${VAR} substitution in configs."""
        import os
        os.environ['TEST_ENDPOINT'] = 'https://test.endpoint.com'
        
        manager = ConfigurationManager()
        config_dict = {
            'endpoint': '${TEST_ENDPOINT}'
        }
        
        substituted = manager._substitute_env_vars(config_dict)
        assert substituted['endpoint'] == 'https://test.endpoint.com'

    def test_config_export(self):
        """Test configuration export to dictionary."""
        manager = ConfigurationManager()
        manager.reset()
        config = manager.load_config(environment="dev", config_path="./configs")
        
        config_dict = manager.to_dict()
        assert 'environment' in config_dict
        assert 'cloud' in config_dict
        assert 'spark' in config_dict


class TestPipelineConfig:
    """Tests for pipeline configuration parsing."""

    def test_parse_valid_pipeline(self):
        """Test parsing valid pipeline configuration."""
        from dataforge_core.metadata_framework import PipelineConfigParser
        
        parser = PipelineConfigParser()
        # This assumes ecommerce_orders_bronze.yaml exists
        config = parser.parse_pipeline(
            "./dataforge_core/pipelines/configs/ecommerce_orders_bronze.yaml"
        )
        
        assert config.name == "ecommerce_orders_bronze"
        assert config.mode.value == "batch"
        assert len(config.quality_rules) > 0

    def test_invalid_pipeline_name(self):
        """Test pipeline name validation."""
        from dataforge_core.metadata_framework import PipelineConfig, SourceConfig, TargetConfig
        
        with pytest.raises(ValueError):
            PipelineConfig(
                name="invalid-name!@#",  # Invalid characters
                source=SourceConfig(type="csv", path="/test"),
                target=TargetConfig(layer="bronze", table_name="test")
            )
