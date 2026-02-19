"""
Configuration validation script for DataForge
Validates all pipeline configs against schema
"""

import sys
from pathlib import Path
from dataforge_core.metadata_framework import PipelineConfigParser
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_all_configs():
    """Validate all pipeline configurations."""
    config_dir = Path("./dataforge_core/pipelines/configs")
    
    if not config_dir.exists():
        logger.warning(f"Config directory not found: {config_dir}")
        return True
    
    parser = PipelineConfigParser()
    
    config_files = list(config_dir.glob("*.yaml"))
    if not config_files:
        logger.warning("No pipeline configs found")
        return True
    
    errors = []
    for config_file in config_files:
        try:
            config = parser.parse_pipeline(str(config_file))
            logger.info(f"✅ {config_file.name}: {config.name} (v{config.version})")
        except Exception as e:
            error_msg = f"❌ {config_file.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    if errors:
        logger.error(f"\n{len(errors)} validation errors found")
        return False
    
    logger.info(f"\n✅ All {len(config_files)} configs valid")
    return True


if __name__ == "__main__":
    success = validate_all_configs()
    sys.exit(0 if success else 1)
