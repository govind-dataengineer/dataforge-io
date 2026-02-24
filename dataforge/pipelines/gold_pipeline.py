"""
Gold Pipeline
Analytics-ready aggregations: daily returns, moving averages, sector analytics.
Ephemeral (30-day retention for cost optimization).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, lag, row_number, current_timestamp, lit, 
    avg, max, min, sum, count, window
)
from pyspark.sql.window import Window
from core import logger


class GoldPipeline:
    """
    Gold Layer: Analytics-ready aggregations.
    - Daily returns calculation
    - Moving averages (50/200 day)
    - Sector-wise analytics
    - 30-day retention
    """
    
    def __init__(self, spark: SparkSession, gold_path: str, silver_path: str):
        self.spark = spark
        self.gold_path = gold_path
        self.silver_path = silver_path
    
    def calculate_daily_returns(self, df: DataFrame) -> DataFrame:
        """Calculate daily returns for each stock."""
        
        window_spec = Window.partitionBy("symbol").orderBy("date")
        
        df_returns = (
            df
            .withColumn("prev_close", lag("close").over(window_spec))
            .withColumn(
                "daily_return_pct",
                ((col("close") - col("prev_close")) / col("prev_close") * 100)
            )
            .drop("prev_close")
        )
        
        logger.info("Calculated daily returns")
        return df_returns
    
    def calculate_moving_averages(self, df: DataFrame) -> DataFrame:
        """Calculate 50-day and 200-day moving averages."""
        
        window_50 = Window.partitionBy("symbol").orderBy("date").rangeBetween(-49 * 86400, 0)
        window_200 = Window.partitionBy("symbol").orderBy("date").rangeBetween(-199 * 86400, 0)
        
        df_ma = (
            df
            .withColumn("ma_50", avg("close").over(window_50))
            .withColumn("ma_200", avg("close").over(window_200))
        )
        
        logger.info("Calculated moving averages")
        return df_ma
    
    def calculate_volatility(self, df: DataFrame) -> DataFrame:
        """Calculate 30-day rolling volatility."""
        from pyspark.sql.functions import stddev
        
        window_30 = Window.partitionBy("symbol").orderBy("date").rangeBetween(-29 * 86400, 0)
        
        df_vol = df.withColumn("volatility_30d", stddev("daily_return_pct").over(window_30))
        
        logger.info("Calculated volatility")
        return df_vol
    
    def aggregate_daily_summary(self, df: DataFrame) -> DataFrame:
        """Create daily aggregate summary per symbol."""
        
        df_agg = (
            df
            .groupBy("date", "symbol")
            .agg(
                col("open").first().alias("daily_open"),
                col("high").max().alias("daily_high"),
                col("low").min().alias("daily_low"),
                col("close").last().alias("daily_close"),
                col("volume").sum().alias("daily_volume"),
                col("daily_return_pct").first().alias("daily_return_pct"),
                col("ma_50").last().alias("ma_50_day"),
                col("ma_200").last().alias("ma_200_day"),
                col("volatility_30d").last().alias("volatility_30d"),
            )
            .withColumn("_gold_timestamp", current_timestamp())
        )
        
        logger.info("Created daily summary")
        return df_agg
    
    def generate_gold_layer(self) -> DataFrame:
        """Generate full Gold layer: returns + moving averages + aggregations."""
        
        logger.info("Starting Silver -> Gold transformation")
        
        # Read Silver
        df_silver = self.spark.read.format("delta").load(self.silver_path)
        
        # Calculate metrics
        df = self.calculate_daily_returns(df_silver)
        df = self.calculate_moving_averages(df)
        df = self.calculate_volatility(df)
        
        # Create summary
        df_gold = self.aggregate_daily_summary(df)
        
        logger.info(f"Generated Gold data", records=df_gold.count())
        return df_gold
    
    def write_gold(self, df: DataFrame) -> None:
        """Write Gold layer data."""
        
        df.write \
            .format("delta") \
            .mode("append") \
            .partitionBy("date", "symbol") \
            .save(self.gold_path)
        
        logger.info(f"Wrote to Gold", path=self.gold_path, records=df.count())
    
    def read_gold(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> DataFrame:
        """Read from Gold layer."""
        try:
            df = self.spark.read.format("delta").load(self.gold_path)
            
            if start_date:
                df = df.filter(col("date") >= start_date)
            if end_date:
                df = df.filter(col("date") <= end_date)
            
            logger.info(f"Read from Gold", records=df.count())
            return df
        except Exception as e:
            logger.error(f"Error reading Gold", error=str(e))
            raise
    
    def cleanup_old_data(self, retention_days: int = 30) -> None:
        """Delete aggregates older than retention."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
            
            self.spark.sql(
                f"""DELETE FROM delta.`{self.gold_path}`
                   WHERE date < '{cutoff_date}'"""
            )
            
            logger.info(f"Cleaned Gold data", retention_days=retention_days)
        except Exception as e:
            logger.warning(f"Cleanup failed", error=str(e))
    
    def run_transformation(self) -> None:
        """Run full Silver -> Gold transformation."""
        df_gold = self.generate_gold_layer()
        self.write_gold(df_gold)
