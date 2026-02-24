"""
Airflow DAGs for DataForge
Production-grade DAG definitions with retries, monitoring, and config-driven execution.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
import sys
import os

# Add dataforge to path
sys.path.insert(0, '/opt/dataforge')

from core import initialize_dataforge, logger
from ingestion import StockDataIngestor
from pipelines import BronzePipeline
from pipelines.silver_pipeline import SilverPipeline
from pipelines.gold_pipeline import GoldPipeline


# ============================================================================
# Default DAG Arguments
# ============================================================================
default_args = {
    'owner': 'dataforge',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
}

# ============================================================================
# DAG 1: Bronze Ingestion
# ============================================================================
dag_bronze = DAG(
    'dag_bronze_ingestion',
    default_args=default_args,
    description='Daily ingestion of stock data into Bronze layer',
    schedule_interval='0 6 * * 1-5',  # 6 AM on weekdays
    catchup=False,
    tags=['bronze', 'ingestion', 'daily']
)


def ingest_stock_data(**context):
    """Ingest stock data from Yahoo Finance."""
    try:
        config, spark = initialize_dataforge(
            config_path="/opt/dataforge/configs/config.yaml",
            env_override="/opt/dataforge/configs/env.local.yaml"
        )
        
        ingestor = StockDataIngestor(spark)
        storage_path = config.get('storage.bronze_path')
        symbols = config.get('ingestion.sources')[0]['symbols']
        
        df = ingestor.ingest_to_bronze(
            symbols=symbols,
            bronze_path=storage_path
        )
        
        logger.info(f"Ingestion complete", records=df.count())
        context['task_instance'].xcom_push(key='records_ingested', value=df.count())
        
        spark.stop()
    except Exception as e:
        logger.error(f"Ingestion failed", error=str(e))
        raise


task_ingest = PythonOperator(
    task_id='ingest_stock_data',
    python_callable=ingest_stock_data,
    dag=dag_bronze,
    provide_context=True
)

task_ingest


# ============================================================================
# DAG 2: Silver Transformation
# ============================================================================
dag_silver = DAG(
    'dag_silver_transform',
    default_args=default_args,
    description='Transform Bronze data into Silver layer (cleanup & deduplication)',
    schedule_interval='0 8 * * 1-5',  # 8 AM on weekdays
    catchup=False,
    tags=['silver', 'transformation', 'daily'],
)


def transform_to_silver(**context):
    """Transform Bronze to Silver."""
    try:
        config, spark = initialize_dataforge(
            config_path="/opt/dataforge/configs/config.yaml",
            env_override="/opt/dataforge/configs/env.local.yaml"
        )
        
        bronze_path = config.get('storage.bronze_path')
        silver_path = config.get('storage.silver_path')
        
        pipeline = SilverPipeline(spark, silver_path, bronze_path)
        pipeline.run_transformation()
        
        # Cleanup old data
        pipeline.cleanup_old_data(retention_days=config.get('storage.silver_retention_days', 90))
        
        logger.info("Silver transformation complete")
        spark.stop()
    except Exception as e:
        logger.error(f"Silver transformation failed", error=str(e))
        raise


task_silver = PythonOperator(
    task_id='transform_to_silver',
    python_callable=transform_to_silver,
    dag=dag_silver,
    provide_context=True
)

task_silver


# ============================================================================
# DAG 3: Gold Analytics
# ============================================================================
dag_gold = DAG(
    'dag_gold_analytics',
    default_args=default_args,
    description='Generate Gold layer analytics: returns, moving averages, aggregations',
    schedule_interval='0 10 * * 1-5',  # 10 AM on weekdays
    catchup=False,
    tags=['gold', 'analytics', 'daily'],
)


def generate_gold_analytics(**context):
    """Generate Gold layer analytics."""
    try:
        config, spark = initialize_dataforge(
            config_path="/opt/dataforge/configs/config.yaml",
            env_override="/opt/dataforge/configs/env.local.yaml"
        )
        
        silver_path = config.get('storage.silver_path')
        gold_path = config.get('storage.gold_path')
        
        pipeline = GoldPipeline(spark, gold_path, silver_path)
        pipeline.run_transformation()
        
        # Cleanup old aggregates
        pipeline.cleanup_old_data(retention_days=config.get('storage.gold_retention_days', 30))
        
        logger.info("Gold analytics complete")
        spark.stop()
    except Exception as e:
        logger.error(f"Gold generation failed", error=str(e))
        raise


task_gold = PythonOperator(
    task_id='generate_gold_analytics',
    python_callable=generate_gold_analytics,
    dag=dag_gold,
    provide_context=True
)

task_gold


# ============================================================================
# DAG 4: Full Pipeline (Orchestration)
# ============================================================================
dag_full_pipeline = DAG(
    'dag_full_pipeline_orchestration',
    default_args=default_args,
    description='Full end-to-end pipeline: Bronze -> Silver -> Gold',
    schedule_interval='0 6 * * 1-5',
    catchup=False,
    tags=['orchestration', 'e2e', 'daily'],
)


task_ingest_full = PythonOperator(
    task_id='ingest_bronze',
    python_callable=ingest_stock_data,
    dag=dag_full_pipeline,
    provide_context=True
)

task_silver_full = PythonOperator(
    task_id='transform_silver',
    python_callable=transform_to_silver,
    dag=dag_full_pipeline,
    provide_context=True
)

task_gold_full = PythonOperator(
    task_id='generate_gold',
    python_callable=generate_gold_analytics,
    dag=dag_full_pipeline,
    provide_context=True
)

# Set dependencies
task_ingest_full >> task_silver_full >> task_gold_full
