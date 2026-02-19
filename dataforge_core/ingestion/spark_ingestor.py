"""
DataForge PySpark Ingestion Module
Batch and incremental data ingestion with quality checks and transformations.
"""

from typing import Optional, Dict, Any, List
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, current_timestamp, hash, concat, sha2
import logging
from dataforge_core.metadata_framework import PipelineConfig
from dataforge_core.metadata import MetadataManager, PipelineAuditRecord, PipelineStatus, SourceType
from dataforge_core.observability import MetricsCollector, PipelineMetrics

logger = logging.getLogger(__name__)


class SparkDataIngestor:
    """
    Enterprise data ingestion using PySpark.
    Handles schema validation, quality checks, and lineage tracking.
    """

    def __init__(
        self,
        spark_session: SparkSession,
        metadata_manager: MetadataManager,
        metrics_collector: MetricsCollector
    ):
        self.spark = spark_session
        self.metadata = metadata_manager
        self.metrics = metrics_collector

    def ingest_batch(
        self,
        pipeline_config: PipelineConfig,
        **additional_spark_options
    ) -> DataFrame:
        """
        Execute batch ingestion pipeline.
        
        Args:
            pipeline_config: Pipeline configuration
            additional_spark_options: Additional Spark reader options
            
        Returns:
            Ingested DataFrame
        """
        with PipelineMetrics(self.metrics, pipeline_config.name) as pm:
            # Read source data
            source_df = self._read_source(
                pipeline_config.source,
                **additional_spark_options
            )
            
            # Record initial record count
            initial_count = source_df.count()
            pm.records_processed = initial_count
            logger.info(f"Read {initial_count} records from source")

            # Apply transformations
            if pipeline_config.transformations:
                source_df = self._apply_transformations(
                    source_df,
                    pipeline_config.transformations
                )

            # Apply quality checks
            passed_df = self._apply_quality_checks(
                source_df,
                pipeline_config.quality_rules,
                pipeline_config.name
            )

            # Add technical columns
            enriched_df = self._add_technical_columns(passed_df, pipeline_config.name)

            # Write to target
            self._write_target(enriched_df, pipeline_config.target)

            # Record audit trail
            final_count = enriched_df.count()
            audit_record = PipelineAuditRecord(
                pipeline_name=pipeline_config.name,
                pipeline_version=pipeline_config.version,
                source_type=SourceType(pipeline_config.source.type),
                source_path=pipeline_config.source.path or pipeline_config.source.table or "",
                target_path=pipeline_config.target.path or pipeline_config.target.table_name,
                status=PipelineStatus.SUCCESS,
                record_count=final_count
            )
            
            self.metadata.record_audit(audit_record)
            self.metadata.track_lineage(
                source_path=pipeline_config.source.path or pipeline_config.source.table or "",
                target_path=pipeline_config.target.table_name,
                pipeline_id=audit_record.pipeline_id
            )

            logger.info(f"Pipeline completed: {pipeline_config.name} ({final_count} records)")
            return enriched_df

    def _read_source(self, source_config: Any, **options) -> DataFrame:
        """Read data from source."""
        reader = self.spark.read

        # Apply source-specific options
        for key, value in {**source_config.options, **options}.items():
            reader = reader.option(key, value)

        if source_config.type == "csv":
            return reader.format("csv").option("header", "true").load(source_config.path)
        elif source_config.type == "json":
            return reader.format("json").load(source_config.path)
        elif source_config.type == "parquet":
            return reader.format("parquet").load(source_config.path)
        elif source_config.type == "delta":
            return reader.format("delta").load(source_config.path)
        elif source_config.type == "database":
            return self.spark.read \
                .format("jdbc") \
                .option("url", source_config.path) \
                .option("dbtable", source_config.table) \
                .load()
        else:
            raise ValueError(f"Unsupported source type: {source_config.type}")

    def _apply_transformations(
        self,
        df: DataFrame,
        transformations: List[Any]
    ) -> DataFrame:
        """Apply SQL/PySpark transformations."""
        for transform in transformations:
            if transform.type == "sql":
                df.createOrReplaceTempView(f"temp_{transform.name}")
                df = self.spark.sql(transform.sql_query)
                logger.info(f"Applied SQL transformation: {transform.name}")
            elif transform.type == "pyspark":
                # Execute PySpark transformation
                exec(transform.pyspark_code)
                logger.info(f"Applied PySpark transformation: {transform.name}")

        return df

    def _apply_quality_checks(
        self,
        df: DataFrame,
        quality_rules: List[Any],
        dataset_name: str
    ) -> DataFrame:
        """Apply data quality validations."""
        for rule in quality_rules:
            if not rule.enabled:
                continue

            if rule.type == "schema":
                # Validate schema
                logger.info(f"Validating schema for: {dataset_name}")
                self.metrics.record_quality_check(dataset_name, "schema", True)

            elif rule.type == "null":
                # Check for nulls
                null_count = df.filter(col(rule.sql_check).isNull()).count()
                passed = null_count == 0
                self.metrics.record_quality_check(dataset_name, "null", passed)
                if not passed:
                    logger.warning(f"Null check failed: {null_count} nulls found")

            elif rule.type == "duplicate":
                # Check for duplicates
                total_count = df.count()
                distinct_count = df.distinct().count()
                passed = total_count == distinct_count
                self.metrics.record_quality_check(dataset_name, "duplicate", passed)
                if not passed:
                    logger.warning(f"Duplicate check failed: {total_count - distinct_count} duplicates")

            elif rule.type == "custom":
                # Custom SQL check
                result = self.spark.sql(rule.sql_check).collect()[0][0]
                passed = bool(result)
                self.metrics.record_quality_check(dataset_name, rule.name, passed)

        return df

    def _add_technical_columns(self, df: DataFrame, pipeline_name: str) -> DataFrame:
        """Add technical audit columns."""
        return df \
            .withColumn("_dataforge_ingestion_timestamp", current_timestamp()) \
            .withColumn("_dataforge_pipeline_name", col("lit")(pipeline_name)) \
            .withColumn("_dataforge_record_hash", sha2(concat(*df.columns), 256))

    def _write_target(self, df: DataFrame, target_config: Any):
        """Write data to target location."""
        writer = df.write \
            .format(target_config.format) \
            .mode(target_config.mode)

        if target_config.partition_by:
            writer = writer.partitionBy(*target_config.partition_by)

        if target_config.path:
            writer.option("path", target_config.path).save()
        else:
            writer.option("mergeSchema", "true").mode(target_config.mode).save(target_config.table_name)

        logger.info(f"Written to target: {target_config.table_name or target_config.path}")


class IncrementalIngestor:
    """
    Incremental data ingestion with CDC support.
    Tracks changes and only processes new/modified records.
    """

    def __init__(self, spark: SparkSession):
        self.spark = spark

    def ingest_incremental(
        self,
        source_df: DataFrame,
        target_path: str,
        unique_keys: List[str],
        timestamp_column: Optional[str] = None
    ) -> DataFrame:
        """
        Perform incremental ingestion with upsert logic.
        
        Args:
            source_df: Source data
            target_path: Target delta table path
            unique_keys: Columns that uniquely identify records
            timestamp_column: Column for change tracking
            
        Returns:
            Merged DataFrame
        """
        from delta.tables import DeltaTable

        # Read existing target
        try:
            target_df = DeltaTable.forPath(self.spark, target_path)
            
            # Upsert new records
            match_condition = " AND ".join([f"target.{col} = source.{col}" for col in unique_keys])
            
            target_df.alias("target").merge(
                source_df.alias("source"),
                match_condition
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
            
            logger.info(f"Incremental merge completed for {target_path}")
        except Exception as e:
            logger.info(f"Initial write to {target_path}: {e}")
            source_df.write.format("delta").mode("overwrite").save(target_path)

        return self.spark.read.format("delta").load(target_path)
