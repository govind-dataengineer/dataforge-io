"""
DataForge Metadata-Driven Ingestion Framework
Enables declarative pipeline definition via YAML/JSON configurations.
Supports dynamic DAG generation and reusable templates.
"""

import yaml
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field, validator
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TransformationType(str, Enum):
    SQL = "sql"
    PYSPARK = "pyspark"
    DBT = "dbt"
    CUSTOM = "custom"


class ProcessingMode(str, Enum):
    BATCH = "batch"
    STREAMING = "streaming"
    INCREMENTAL = "incremental"


class TargetLayer(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class SourceConfig(BaseModel):
    """Source configuration for data ingestion."""
    type: str  # csv, json, parquet, database, kafka, api
    path: Optional[str] = None
    database: Optional[str] = None
    table: Optional[str] = None
    query: Optional[str] = None
    kafka_topic: Optional[str] = None
    format: str = "parquet"
    options: Dict[str, Any] = {}


class TransformationConfig(BaseModel):
    """Transformation step configuration."""
    name: str
    type: TransformationType
    sql_query: Optional[str] = None
    pyspark_code: Optional[str] = None
    dbt_model: Optional[str] = None
    input_tables: List[str] = []
    output_table: str = ""


class TargetConfig(BaseModel):
    """Target configuration for data output."""
    layer: TargetLayer
    path: Optional[str] = None
    table_name: str
    format: str = "delta"
    mode: str = "overwrite"  # overwrite, append, ignore, error
    partition_by: Optional[List[str]] = None
    file_compaction: bool = True
    retention_days: Optional[int] = None


class QualityRule(BaseModel):
    """Data quality validation rule."""
    name: str
    type: str  # schema, duplicate, null, custom, statistical
    sql_check: Optional[str] = None
    threshold: Optional[float] = None  # For statistical rules
    enabled: bool = True


class PipelineConfig(BaseModel):
    """Complete pipeline configuration."""
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    owner: Optional[str] = None
    enabled: bool = True
    
    # Execution
    mode: ProcessingMode = ProcessingMode.BATCH
    schedule: Optional[str] = None  # Cron expression
    timeout_minutes: int = 60
    retry_count: int = 1
    retry_delay_minutes: int = 5
    
    # Data
    source: SourceConfig
    transformations: List[TransformationConfig] = []
    target: TargetConfig
    
    # Quality
    quality_rules: List[QualityRule] = []
    quality_threshold: float = 0.95
    
    # Metadata
    tags: List[str] = []
    documentation_url: Optional[str] = None
    

    class Config:
        use_enum_values = True

    @validator('name')
    def validate_name(cls, v):
        if not v or not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Pipeline name must be alphanumeric')
        return v


class PipelineTemplate:
    """Reusable pipeline template for common patterns."""

    def __init__(self, template_name: str, template_dict: Dict[str, Any]):
        self.name = template_name
        self.template = template_dict

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'PipelineTemplate':
        """Load template from YAML file."""
        with open(yaml_path, 'r') as f:
            template_dict = yaml.safe_load(f)
        return cls(Path(yaml_path).stem, template_dict)

    def apply(self, **variables) -> Dict[str, Any]:
        """Apply variables to template."""
        result = self._substitute_variables(self.template, variables)
        return result

    @staticmethod
    def _substitute_variables(obj: Any, variables: Dict[str, Any]) -> Any:
        """Recursively substitute ${VAR} with provided variables."""
        if isinstance(obj, dict):
            return {k: PipelineTemplate._substitute_variables(v, variables) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [PipelineTemplate._substitute_variables(item, variables) for item in obj]
        elif isinstance(obj, str):
            import re
            pattern = r'\$\{(\w+)}'
            def replace_var(match):
                var_name = match.group(1)
                return str(variables.get(var_name, match.group(0)))
            return re.sub(pattern, replace_var, obj)
        else:
            return obj


class PipelineConfigParser:
    """
    Parse and validate pipeline configurations.
    Supports templates, variable interpolation, and schema validation.
    """

    def __init__(self, config_dir: str = "./pipelines"):
        self.config_dir = Path(config_dir)
        self.templates: Dict[str, PipelineTemplate] = {}
        self._load_templates()

    def _load_templates(self):
        """Load all available templates."""
        templates_dir = self.config_dir / "templates"
        if templates_dir.exists():
            for template_file in templates_dir.glob("*.yaml"):
                template = PipelineTemplate.from_yaml(str(template_file))
                self.templates[template.name] = template
                logger.info(f"Loaded template: {template.name}")

    def parse_pipeline(
        self,
        config_path: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> PipelineConfig:
        """
        Parse and validate pipeline configuration.
        
        Args:
            config_path: Path to pipeline config file
            variables: Variables for template substitution
            
        Returns:
            Validated PipelineConfig object
        """
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)

        # Check if config uses a template
        if 'template' in config_dict:
            template_name = config_dict.pop('template')
            if template_name not in self.templates:
                raise ValueError(f"Template not found: {template_name}")
            
            template = self.templates[template_name]
            template_config = template.apply(**(variables or {}))
            
            # Merge template with overrides
            config_dict = {**template_config, **config_dict}

        # Validate configuration
        try:
            pipeline_config = PipelineConfig(**config_dict)
            logger.info(f"Pipeline configuration parsed: {pipeline_config.name}")
            return pipeline_config
        except Exception as e:
            logger.error(f"Failed to parse pipeline configuration: {e}")
            raise

    def parse_directory(self, pipeline_dir: str) -> List[PipelineConfig]:
        """Parse all pipeline configs in a directory."""
        pipelines = []
        config_directory = Path(pipeline_dir)
        
        for config_file in config_directory.glob("*.yaml"):
            try:
                config = self.parse_pipeline(str(config_file))
                pipelines.append(config)
            except Exception as e:
                logger.warning(f"Failed to parse {config_file}: {e}")

        logger.info(f"Loaded {len(pipelines)} pipeline configurations")
        return pipelines


class PipelineRegistry:
    """Registry for managing pipeline configurations."""

    def __init__(self):
        self.pipelines: Dict[str, PipelineConfig] = {}
        self.parser = PipelineConfigParser()

    def register(self, config: PipelineConfig):
        """Register a pipeline configuration."""
        self.pipelines[config.name] = config
        logger.info(f"Pipeline registered: {config.name}")

    def register_from_yaml(self, yaml_path: str, variables: Optional[Dict[str, Any]] = None):
        """Register pipeline from YAML file."""
        config = self.parser.parse_pipeline(yaml_path, variables)
        self.register(config)

    def get(self, pipeline_name: str) -> Optional[PipelineConfig]:
        """Get pipeline by name."""
        return self.pipelines.get(pipeline_name)

    def list_all(self) -> Dict[str, PipelineConfig]:
        """List all registered pipelines."""
        return self.pipelines.copy()

    def export_to_json(self, pipeline_name: str) -> str:
        """Export pipeline config to JSON."""
        config = self.get(pipeline_name)
        if not config:
            raise ValueError(f"Pipeline not found: {pipeline_name}")
        return json.dumps(config.dict(exclude_none=True), indent=2)


# Global registry
pipeline_registry = PipelineRegistry()
