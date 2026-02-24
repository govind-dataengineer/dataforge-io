"""
Stock Data Ingestion
Downloads historical stock data from Yahoo Finance and ingests into Bronze layer.
Partitioned by date and symbol for efficient querying.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, to_date, lit
from core import logger, Schemas


class StockDataIngestor:
    """Ingest historical stock data from Yahoo Finance."""
    
    def __init__(self, spark: SparkSession):
        self.spark = spark
    
    def download_stock_data(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Download stock data using yfinance."""
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"Downloading stock data", symbols=symbols, start_date=start_date, end_date=end_date)
        
        all_data = []
        for symbol in symbols:
            try:
                data = yf.download(symbol, start=start_date, end=end_date, progress=False)
                data['Symbol'] = symbol
                data = data.reset_index()
                all_data.append(data)
                logger.info(f"Downloaded {len(data)} records", symbol=symbol)
            except Exception as e:
                logger.warning(f"Failed to download data", symbol=symbol, error=str(e))
        
        if not all_data:
            raise ValueError("No data downloaded for any symbols")
        
        combined = pd.concat(all_data, ignore_index=True)
        return combined
    
    def ingest_to_bronze(
        self,
        symbols: List[str],
        bronze_path: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataFrame:
        """Download stock data and write to Bronze layer."""
        
        # Download data
        pdf = self.download_stock_data(symbols, start_date, end_date)
        
        # Convert to Spark DataFrame
        spark_df = self.spark.createDataFrame(pdf, schema=Schemas.stock_ohlc())
        
        # Standardize column names
        spark_df = (
            spark_df
            .withColumnRenamed("Symbol", "symbol")
            .withColumn("date", to_date(col("Date")))
            .drop("Date")
        )
        
        # Write to Bronze with partitioning
        spark_df.write \
            .format("delta") \
            .mode("append") \
            .partitionBy("date", "symbol") \
            .save(bronze_path)
        
        logger.info(f"Ingested to Bronze", path=bronze_path, records=spark_df.count())
        return spark_df
    
    @staticmethod
    def generate_sample_data(num_stocks: int = 10, num_days: int = 365) -> pd.DataFrame:
        """Generate sample stock data for testing."""
        import numpy as np
        
        symbols = [f"STOCK_{i:03d}.NS" for i in range(num_stocks)]
        dates = pd.date_range(end=datetime.now(), periods=num_days, freq='D')
        
        data = []
        for symbol in symbols:
            for date in dates:
                close_price = np.random.normal(100, 20)
                data.append({
                    'date': date,
                    'symbol': symbol,
                    'open': close_price * 0.99,
                    'high': close_price * 1.05,
                    'low': close_price * 0.95,
                    'close': close_price,
                    'adjusted_close': close_price,
                    'volume': np.random.randint(1000000, 10000000),
                })
        
        return pd.DataFrame(data)
