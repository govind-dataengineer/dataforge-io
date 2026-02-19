"""
Unit tests for DataForge ingestion module
"""

import pytest
from pyspark.sql import SparkSession
from dataforge_core.metadata_framework import PipelineConfig, SourceConfig, TargetConfig


@pytest.fixture(scope="session")
def spark_session():
    """Create Spark session for tests."""
    return SparkSession.builder \
        .master("local[*]") \
        .appName("DataForge-Tests") \
        .getOrCreate()


class TestSparkIngestor:
    """Tests for Spark-based ingestion."""

    def test_read_csv_source(self, spark_session):
        """Test reading CSV files."""
        # Create test CSV
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("id,name,value\n")
            f.write("1,test1,100\n")
            f.write("2,test2,200\n")
            temp_file = f.name
        
        try:
            df = spark_session.read \
                .option("header", "true") \
                .csv(temp_file)
            
            assert df.count() == 2
            assert len(df.columns) == 3
        finally:
            os.unlink(temp_file)

    def test_dataframe_transformations(self, spark_session):
        """Test PySpark transformations."""
        from pyspark.sql.functions import col, upper
        
        # Create test data
        data = [
            ("john", 25),
            ("jane", 30),
        ]
        df = spark_session.createDataFrame(data, ["name", "age"])
        
        # Transform
        df_transformed = df.select(
            upper(col("name")).alias("name_upper"),
            col("age")
        )
        
        assert df_transformed.count() == 2
        results = df_transformed.collect()
        assert results[0]['name_upper'] == 'JOHN'


class TestPipelineMetadata:
    """Tests for pipeline metadata framework."""

    def test_create_pipeline_config(self):
        """Test creating pipeline configuration."""
        source = SourceConfig(type="csv", path="/data/orders.csv")
        target = TargetConfig(layer="bronze", table_name="orders_raw")
        
        config = PipelineConfig(
            name="test_pipeline",
            version="1.0.0",
            source=source,
            target=target
        )
        
        assert config.name == "test_pipeline"
        assert config.source.type == "csv"
        assert config.target.table_name == "orders_raw"

    def test_pipeline_with_transformations(self):
        """Test pipeline with transformation steps."""
        from dataforge_core.metadata_framework import TransformationConfig, TransformationType
        
        source = SourceConfig(type="csv", path="/data/orders.csv")
        target = TargetConfig(layer="bronze", table_name="orders_raw")
        
        transform = TransformationConfig(
            name="normalize",
            type=TransformationType.SQL,
            sql_query="SELECT * FROM source WHERE id IS NOT NULL",
            output_table="normalized"
        )
        
        config = PipelineConfig(
            name="test_pipeline",
            source=source,
            target=target,
            transformations=[transform]
        )
        
        assert len(config.transformations) == 1
        assert config.transformations[0].name == "normalize"
