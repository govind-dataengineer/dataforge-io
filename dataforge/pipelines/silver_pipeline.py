"""
Silver Pipeline
Cleaned, deduplicated, standardized data - ephemeral (90-day retention).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, row_number, current_timestamp, lit
from pyspark.sql.window import Window
from core import logger


class SilverPipeline:
    """
    Silver Layer: Cleaned, deduplicated data.
    - Deduplication logic
    - Schema standardization
    - 90-day retention (auto-cleanup)
    """
    
    def __init__(self, spark: SparkSession, silver_path: str, bronze_path: str):
        self.spark = spark
        self.silver_path = silver_path
        self.bronze_path = bronze_path
    
    def transform_bronze_to_silver(self) -> DataFrame:
        """Transform Bronze data: deduplicate, standardize, validate."""
        
        logger.info("Starting Bronze -> Silver transformation")
        
        # Read from Bronze
        df = self.spark.read.format("delta").load(self.bronze_path)
        
        # Deduplication: keep latest record per symbol-date
        window_spec = Window.partitionBy("symbol", "date").orderBy(col("_ingestion_timestamp").desc())
        df_dedup = df.withColumn("rn", row_number().over(window_spec)) \
            .filter(col("rn") == 1) \
            .drop("rn")
        
        # Schema standardization and casting
        df_clean = (
            df_dedup
            .withColumn("open", col("open").cast("double"))
            .withColumn("high", col("high").cast("double"))
            .withColumn("low", col("low").cast("double"))
            .withColumn("close", col("close").cast("double"))
            .withColumn("adjusted_close", col("adjusted_close").cast("double"))
            .withColumn("volume", col("volume").cast("long"))
        )
        
        # Remove nulls in critical columns
        df_clean = df_clean.filter(
            col("date").isNotNull() & 
            col("symbol").isNotNull() & 
            col("close").isNotNull()
        )
        
        # Add quality flags
        df_with_flags = (
            df_clean
            .withColumn("_quality_check_passed", lit(True))
            .withColumn("_silver_transformation_timestamp", current_timestamp())
        )
        
        logger.info(f"Transformed", records=df_with_flags.count())
        return df_with_flags
    
    def write_silver(self, df: DataFrame) -> None:
        """Write cleaned data to Silver layer."""
        
        df.write \
            .format("delta") \
            .mode("overwrite") \
            .partitionBy("date", "symbol") \
            .save(self.silver_path)
        
        logger.info(f"Wrote to Silver", path=self.silver_path, records=df.count())
    
    def read_silver(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> DataFrame:
        """Read from Silver with optional date range."""
        try:
            df = self.spark.read.format("delta").load(self.silver_path)
            
            if start_date:
                df = df.filter(col("date") >= start_date)
            if end_date:
                df = df.filter(col("date") <= end_date)
            
            logger.info(f"Read from Silver", records=df.count())
            return df
        except Exception as e:
            logger.error(f"Error reading Silver", error=str(e))
            raise
    
    def cleanup_old_data(self, retention_days: int = 90) -> None:
        """Delete data older than retention period."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
            
            df = self.spark.read.format("delta").load(self.silver_path)
            
            # Delete old partitions
            self.spark.sql(
                f"""
                DELETE FROM delta.`{self.silver_path}`
                WHERE date < '{cutoff_date}'
                """
            )
            
            logger.info(f"Cleaned Silver data", retention_days=retention_days, cutoff_date=cutoff_date)
        except Exception as e:
            logger.warning(f"Cleanup failed", error=str(e))
    
    def run_transformation(self) -> None:
        """Run full Bronze -> Silver transformation."""
        df_silver = self.transform_bronze_to_silver()
        self.write_silver(df_silver)
