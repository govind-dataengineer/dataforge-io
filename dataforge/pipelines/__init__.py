"""
Bronze Pipeline
Raw data ingestion layer - immutable, long-term storage.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, current_timestamp, lit
from core import logger


class BronzePipeline:
    """
    Bronze Layer: Raw, immutable data storage.
    - Partitioned by date and symbol
    - Append-only (no overwrites)
    - Long-term retention
    """
    
    def __init__(self, spark: SparkSession, bronze_path: str):
        self.spark = spark
        self.bronze_path = bronze_path
    
    def write_raw_data(
        self,
        df: DataFrame,
        partition_columns: List[str] = ["date", "symbol"]
    ) -> None:
        """Write raw data to Bronze layer with partitioning."""
        
        # Add metadata columns
        df_with_meta = df.withColumn(
            "_ingestion_timestamp", current_timestamp()
        ).withColumn(
            "_ingestion_date", lit(datetime.now().date())
        )
        
        # Write with partitioning
        df_with_meta.write \
            .format("delta") \
            .mode("append") \
            .partitionBy(*partition_columns) \
            .option("mergeSchema", "true") \
            .save(self.bronze_path)
        
        record_count = df.count()
        logger.info(f"Wrote to Bronze", path=self.bronze_path, records=record_count)
    
    def read_bronze(self, filters: Optional[dict] = None) -> DataFrame:
        """Read from Bronze layer with optional filters."""
        try:
            df = self.spark.read.format("delta").load(self.bronze_path)
            
            if filters:
                for col_name, value in filters.items():
                    df = df.filter(col(col_name) == value)
            
            logger.info(f"Read from Bronze", records=df.count())
            return df
        except Exception as e:
            logger.error(f"Error reading Bronze", error=str(e))
            raise
    
    def get_latest_date(self) -> datetime:
        """Get the latest date available in Bronze."""
        try:
            df = self.spark.read.format("delta").load(self.bronze_path)
            latest = df.agg({"date": "max"}).collect()[0][0]
            logger.info(f"Latest Bronze date", date=latest)
            return latest
        except Exception as e:
            logger.warning(f"Error getting latest date", error=str(e))
            return None
    
    def get_symbols(self) -> List[str]:
        """Get all unique symbols in Bronze."""
        try:
            df = self.spark.read.format("delta").load(self.bronze_path)
            symbols = [row[0] for row in df.select("symbol").distinct().collect()]
            logger.info(f"Found symbols", count=len(symbols))
            return symbols
        except Exception as e:
            logger.warning(f"Error getting symbols", error=str(e))
            return []
    
    def vacuum(self, retention_hours: int = 24) -> None:
        """Remove old versions of Delta table beyond retention."""
        try:
            self.spark.sql(
                f"VACUUM delta.`{self.bronze_path}` RETAIN {retention_hours} HOURS"
            )
            logger.info(f"Vacuumed Bronze", retention_hours=retention_hours)
        except Exception as e:
            logger.warning(f"Vacuum failed", error=str(e))
