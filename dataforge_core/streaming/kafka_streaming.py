"""
DataForge Streaming Ingestion Module
Real-time data ingestion using Spark Structured Streaming.
Kafka integration with checkpoint management and fault tolerance.
"""

from typing import Optional, Dict, Any
from pyspark.sql import SparkSession, DataFrame, StreamingQuery
from pyspark.sql.functions import from_json, schema_of_json, col, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, TimestampType
import json
import logging
from dataforge_core.metadata import MetadataManager

logger = logging.getLogger(__name__)


class StreamingIngestor:
    """
    Kafka-based streaming ingestion with Delta Lake sinks.
    Provides exactly-once semantics and state management.
    """

    def __init__(
        self,
        spark_session: SparkSession,
        metadata_manager: MetadataManager
    ):
        self.spark = spark_session
        self.metadata = metadata_manager
        self.active_streams: Dict[str, StreamingQuery] = {}

    def ingest_from_kafka(
        self,
        kafka_brokers: str,
        topic: str,
        schema: StructType,
        target_path: str,
        checkpoint_path: str,
        processing_time: str = "10 seconds",
        **kafka_options
    ) -> StreamingQuery:
        """
        Stream data from Kafka topic to Delta Lake.
        
        Args:
            kafka_brokers: Kafka bootstrap servers (comma-separated)
            topic: Kafka topic name
            schema: Expected schema for the data
            target_path: Target Delta table path
            checkpoint_path: Checkpoint directory for recovery
            processing_time: Micro-batch interval
            kafka_options: Additional Kafka options
            
        Returns:
            StreamingQuery object
        """
        # Read from Kafka
        df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_brokers) \
            .option("subscribe", topic) \
            .option("startingOffsets", "latest") \
            .option("failOnDataLoss", "false") \
            .options(**kafka_options) \
            .load()

        # Parse JSON payload
        parsed_df = df.select(
            from_json(col("value").cast("string"), schema).alias("data")
        ).select("data.*")

        # Add technical columns
        enhanced_df = parsed_df \
            .withColumn("_stream_timestamp", current_timestamp()) \
            .withColumn("_kafka_timestamp", col("timestamp")) \
            .withColumn("_kafka_partition", col("partition")) \
            .withColumn("_kafka_offset", col("offset"))

        # Write to Delta Lake
        query = enhanced_df \
            .writeStream \
            .outputMode("append") \
            .format("delta") \
            .option("checkpointLocation", checkpoint_path) \
            .option("mergeSchema", "true") \
            .start(target_path)

        self.active_streams[topic] = query
        logger.info(f"Streaming query started: {topic} -> {target_path}")

        return query

    def stop_stream(self, topic: str, timeout_ms: int = 30000):
        """Stop active streaming query."""
        if topic in self.active_streams:
            query = self.active_streams[topic]
            query.stop(timeoutMs=timeout_ms)
            logger.info(f"Stream stopped: {topic}")
            del self.active_streams[topic]

    def stop_all_streams(self, timeout_ms: int = 30000):
        """Stop all active streams."""
        for topic in list(self.active_streams.keys()):
            self.stop_stream(topic, timeout_ms)

    def get_stream_status(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get status of streaming query."""
        if topic not in self.active_streams:
            return None

        query = self.active_streams[topic]
        return {
            'topic': topic,
            'is_active': query.isActive,
            'status': query.status if hasattr(query, 'status') else 'unknown',
            'processed_records': query.processedRowsPerSecond if hasattr(query, 'processedRowsPerSecond') else 0
        }

    def list_active_streams(self) -> Dict[str, Dict[str, Any]]:
        """List all active streaming queries."""
        return {
            topic: self.get_stream_status(topic)
            for topic in self.active_streams.keys()
        }

    def ingest_with_transformations(
        self,
        kafka_brokers: str,
        topic: str,
        schema: StructType,
        transformations: Optional[Dict[str, Any]] = None,
        target_path: Optional[str] = None,
        checkpoint_path: Optional[str] = None
    ) -> StreamingQuery:
        """
        Stream ingestion with transformation logic.
        
        Args:
            kafka_brokers: Kafka bootstrap servers
            topic: Topic name
            schema: Input schema
            transformations: SQL/PySpark transformations to apply
            target_path: Target table path
            checkpoint_path: Checkpoint directory
            
        Returns:
            StreamingQuery
        """
        # Read and parse
        df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_brokers) \
            .option("subscribe", topic) \
            .load()

        parsed_df = df.select(
            from_json(col("value").cast("string"), schema).alias("data")
        ).select("data.*")

        # Apply transformations
        if transformations:
            parsed_df.createOrReplaceTempView("source_stream")
            
            if 'sql' in transformations:
                parsed_df = self.spark.sql(transformations['sql'])

        # Write to Delta
        query = parsed_df \
            .writeStream \
            .outputMode("append") \
            .format("delta") \
            .option("checkpointLocation", checkpoint_path) \
            .start(target_path)

        logger.info(f"Streaming with transformations started: {topic}")
        return query


class StreamingAggregator:
    """
    Streaming aggregations and windowing operations.
    For real-time analytics and metrics computation.
    """

    @staticmethod
    def window_aggregation(
        df: DataFrame,
        window_duration: str,
        slide_duration: str,
        timestamp_column: str,
        aggregate_exprs: Dict[str, str],
        group_by_cols: Optional[list] = None
    ) -> DataFrame:
        """
        Perform windowed aggregation.
        
        Args:
            df: Input stream
            window_duration: Window size (e.g., "5 minutes")
            slide_duration: Slide interval (e.g., "1 minute")
            timestamp_column: Column to use for windowing
            aggregate_exprs: Aggregation expressions (e.g., {"total": "sum(amount)"})
            group_by_cols: Additional columns to group by
            
        Returns:
            Aggregated DataFrame
        """
        from pyspark.sql.functions import window

        agg_dict = {col_name: expr for col_name, expr in aggregate_exprs.items()}

        result = df \
            .withWatermark(timestamp_column, "1 minute") \
            .groupBy(
                window(col(timestamp_column), window_duration, slide_duration),
                *group_by_cols if group_by_cols else []
            ) \
            .agg(agg_dict)

        return result
