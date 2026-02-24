"""
Unit and Integration Tests for DataForge
Tests for pipelines, data quality, and API endpoints.
"""

import pytest
import os
from datetime import datetime, timedelta
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, DateType

# Import modules (adjust paths as needed)
from dataforge.core import ConfigManager, SparkSessionManager, Schemas, StorageHelper
from dataforge.ingestion import StockDataIngestor
from dataforge.pipelines import BronzePipeline
from dataforge.pipelines.silver_pipeline import SilverPipeline
from dataforge.pipelines.gold_pipeline import GoldPipeline


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture(scope="session")
def spark():
    """Create Spark session for testing."""
    spark_session = SparkSession.builder \
        .appName("DataForge-Tests") \
        .master("local[2]") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()
    
    yield spark_session
    spark_session.stop()


@pytest.fixture
def config():
    """Load configuration."""
    return ConfigManager()


@pytest.fixture
def storage_helper(config):
    """Create storage helper."""
    return StorageHelper(config)


@pytest.fixture
def sample_stock_data():
    """Generate sample stock data."""
    return StockDataIngestor.generate_sample_data(num_stocks=5, num_days=30)


# ============================================================================
# Config Tests
# ============================================================================
class TestConfiguration:
    
    def test_config_load(self, config):
        """Test configuration loading."""
        assert config.get('environment') is not None
        assert config.get('storage.type') is not None
    
    def test_config_get_nested(self, config):
        """Test nested config access."""
        spark_master = config.get('spark.master')
        assert spark_master is not None
    
    def test_config_default(self, config):
        """Test default values."""
        value = config.get('nonexistent.key', 'default')
        assert value == 'default'


# ============================================================================
# Schema Tests
# ============================================================================
class TestSchemas:
    
    def test_stock_ohlc_schema(self):
        """Test OHLC schema structure."""
        schema = Schemas.stock_ohlc()
        assert len(schema.fields) == 8
        field_names = [f.name for f in schema.fields]
        assert 'symbol' in field_names
        assert 'close' in field_names


# ============================================================================
# Ingestion Tests
# ============================================================================
class TestIngestion:
    
    def test_sample_data_generation(self):
        """Test sample data generation."""
        df = StockDataIngestor.generate_sample_data(num_stocks=5, num_days=20)
        assert len(df) == 100  # 5 stocks * 20 days
        assert 'symbol' in df.columns
        assert 'close' in df.columns
    
    def test_dataframe_conversion(self, spark, sample_stock_data):
        """Test conversion of pandas to Spark DataFrame."""
        spark_df = spark.createDataFrame(sample_stock_data, schema=Schemas.stock_ohlc())
        assert spark_df.count() == len(sample_stock_data)


# ============================================================================
# Bronze Pipeline Tests
# ============================================================================
class TestBronzePipeline:
    
    def test_write_bronze(self, spark, sample_stock_data, tmp_path):
        """Test writing data to Bronze."""
        bronze_path = str(tmp_path / "bronze")
        
        # Convert to Spark DataFrame
        spark_df = spark.createDataFrame(sample_stock_data, schema=Schemas.stock_ohlc())
        
        # Write to bronze
        bronze = BronzePipeline(spark, bronze_path)
        bronze.write_raw_data(spark_df)
        
        # Verify
        df_read = bronze.read_bronze()
        assert df_read.count() > 0
    
    def test_get_symbols(self, spark, tmp_path):
        """Test retrieving symbols from Bronze."""
        bronze_path = str(tmp_path / "bronze")
        
        data = StockDataIngestor.generate_sample_data(num_stocks=3, num_days=5)
        spark_df = spark.createDataFrame(data, schema=Schemas.stock_ohlc())
        
        bronze = BronzePipeline(spark, bronze_path)
        bronze.write_raw_data(spark_df)
        
        symbols = bronze.get_symbols()
        assert len(symbols) == 3


# ============================================================================
# Silver Pipeline Tests
# ============================================================================
class TestSilverPipeline:
    
    def test_deduplication(self, spark, tmp_path):
        """Test deduplication logic."""
        bronze_path = str(tmp_path / "bronze")
        silver_path = str(tmp_path / "silver")
        
        # Create duplicate data
        data = StockDataIngestor.generate_sample_data(num_stocks=2, num_days=5)
        # Add duplicates
        data_dup = pd.concat([data, data.iloc[:5]], ignore_index=True)
        
        spark_df = spark.createDataFrame(data_dup, schema=Schemas.stock_ohlc())
        spark_df.write.format("delta").mode("overwrite").save(bronze_path)
        
        # Transform to silver
        silver = SilverPipeline(spark, silver_path, bronze_path)
        df_silver = silver.transform_bronze_to_silver()
        
        # Verify deduplication
        unique_count = df_silver.groupBy("symbol", "date").count().count()
        assert unique_count == 10  # 2 stocks * 5 days


# ============================================================================
# Gold Pipeline Tests
# ============================================================================
class TestGoldPipeline:
    
    def test_daily_returns_calculation(self, spark):
        """Test daily returns calculation."""
        data = {
            'date': pd.date_range('2024-01-01', periods=5),
            'symbol': ['TEST'] * 5,
            'close': [100, 102, 101, 103, 105],
            'open': [100, 102, 101, 103, 105],
            'high': [101, 103, 102, 104, 106],
            'low': [99, 101, 100, 102, 104],
            'adjusted_close': [100, 102, 101, 103, 105],
            'volume': [1000000] * 5,
        }
        
        df = spark.createDataFrame(pd.DataFrame(data), schema=Schemas.stock_ohlc())
        
        gold = GoldPipeline(spark, "", "")
        df_returns = gold.calculate_daily_returns(df)
        
        # Check that returns are calculated
        assert df_returns.filter(df_returns.daily_return_pct.isNotNull()).count() == 4  # First row is null


# ============================================================================
# Integration Tests
# ============================================================================
class TestIntegration:
    
    def test_bronze_to_silver_to_gold_flow(self, spark, tmp_path):
        """Test full pipeline flow: Bronze -> Silver -> Gold."""
        bronze_path = str(tmp_path / "bronze")
        silver_path = str(tmp_path / "silver")
        gold_path = str(tmp_path / "gold")
        
        # Step 1: Ingest to Bronze
        data = StockDataIngestor.generate_sample_data(num_stocks=2, num_days=10)
        spark_df = spark.createDataFrame(data, schema=Schemas.stock_ohlc())
        
        bronze = BronzePipeline(spark, bronze_path)
        bronze.write_raw_data(spark_df)
        
        assert bronze.read_bronze().count() == 20
        
        # Step 2: Transform to Silver
        silver = SilverPipeline(spark, silver_path, bronze_path)
        silver.run_transformation()
        
        df_silver = silver.read_silver()
        assert df_silver.count() <= 20  # After dedup
        
        # Step 3: Transform to Gold
        gold = GoldPipeline(spark, gold_path, silver_path)
        gold.run_transformation()
        
        df_gold = gold.read_gold()
        assert df_gold.count() > 0


# ============================================================================
# Data Quality Tests
# ============================================================================
class TestDataQuality:
    
    def test_null_check(self, spark):
        """Test null value detection."""
        data = {
            'date': [datetime(2024, 1, 1)] * 3,
            'symbol': ['TEST', 'TEST', None],
            'close': [100.0, None, 102.0],
            'open': [99, 100, 101],
            'high': [101, 102, 103],
            'low': [98, 99, 100],
            'adjusted_close': [100.0, 101.0, 102.0],
            'volume': [1000000, 1000000, 1000000],
        }
        
        df = spark.createDataFrame(pd.DataFrame(data), schema=Schemas.stock_ohlc())
        
        # Count nulls
        from pyspark.sql.functions import col, isnan
        null_count = df.filter(col("symbol").isNull() | col("close").isNull()).count()
        
        assert null_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
