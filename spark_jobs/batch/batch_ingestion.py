"""
DataForge Spark Job: Batch Ingestion Example
Demonstrates Bronze -> Silver transformation patterns.
Enterprise-grade with error handling and metrics.
"""

import sys
import logging
from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip

from dataforge_core.config import get_config
from dataforge_core.metadata_framework import PipelineConfigParser
from dataforge_core.ingestion.spark_ingestor import SparkDataIngestor
from dataforge_core.metadata import MetadataManager
from dataforge_core.observability import MetricsCollector
from dataforge_core.logging_config import setup_logging

# Setup logging
logger = setup_logging(name="spark_batch_job", level="INFO")

# Configure Spark with Delta Lake
builder = SparkSession.builder \
    .appName("DataForge-Batch-Job") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true")

spark = configure_spark_with_delta_pip(builder).getOrCreate()

def main(pipeline_config_path: str):
    """
    Execute batch ingestion job.
    
    Args:
        pipeline_config_path: Path to pipeline configuration YAML
    """
    try:
        # Load configuration
        config = get_config()
        logger.info(f"Environment: {config.environment.value}")

        # Initialize components
        metadata_manager = MetadataManager({
            'host': config.database.host,
            'port': config.database.port,
            'username': config.database.username,
            'password': config.database.password,
            'databases': config.database.databases
        })

        metrics_collector = MetricsCollector()

        # Parse pipeline configuration
        parser = PipelineConfigParser()
        pipeline_config = parser.parse_pipeline(pipeline_config_path)

        logger.info(f"Starting pipeline: {pipeline_config.name}")

        # Create ingestor
        ingestor = SparkDataIngestor(spark, metadata_manager, metrics_collector)

        # Execute pipeline
        result_df = ingestor.ingest_batch(pipeline_config)

        # Show sample results
        logger.info(f"Pipeline completed successfully")
        result_df.show(5)

        # Print metrics
        logger.info("Metrics summary:")
        logger.info(metrics_collector.get_metrics())

    except Exception as e:
        logger.error(f"Job failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: spark-submit batch_job.py <pipeline_config_path>")
        sys.exit(1)

    main(sys.argv[1])
