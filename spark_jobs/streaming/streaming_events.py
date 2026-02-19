"""
DataForge Spark Streaming Job: Real-time Events
Demonstrates Kafka -> Delta Lake streaming patterns.
Includes windowing and state management.
"""

import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, LongType, TimestampType, DoubleType
from delta import configure_spark_with_delta_pip

from dataforge_core.config import get_config
from dataforge_core.streaming.kafka_streaming import StreamingIngestor
from dataforge_core.metadata import MetadataManager
from dataforge_core.logging_config import setup_logging

logger = setup_logging(name="spark_streaming_job", level="INFO")

# Configure Spark with Delta Lake
builder = SparkSession.builder \
    .appName("DataForge-Streaming-Job") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .config("spark.sql.streaming.checkpointLocation", "/tmp/dataforge_checkpoints")

spark = configure_spark_with_delta_pip(builder).getOrCreate()


def main():
    """Execute streaming job."""
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

        # Define event schema
        schema = StructType([
            StructField("event_id", StringType(), False),
            StructField("user_id", StringType(), False),
            StructField("event_type", StringType(), False),
            StructField("event_timestamp", TimestampType(), False),
            StructField("amount", DoubleType(), True),
            StructField("properties", StringType(), True)
        ])

        # Create streaming ingestor
        ingestor = StreamingIngestor(spark, metadata_manager)

        # Start streaming job
        query = ingestor.ingest_from_kafka(
            kafka_brokers=config.kafka.bootstrap_servers,
            topic="events",
            schema=schema,
            target_path="s3://dataforge-bronze/events/",
            checkpoint_path="/tmp/dataforge_checkpoints/events"
        )

        logger.info("Streaming job started. Press Ctrl+C to stop...")

        # Keep job running
        query.awaitTermination()

    except Exception as e:
        logger.error(f"Streaming job failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
