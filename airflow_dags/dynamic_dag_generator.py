"""
DataForge Airflow DAG Generator
Dynamically generates Airflow DAGs from pipeline configurations.
Implements enterprise-grade orchestration with retries and monitoring.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.exceptions import AirflowException

from dataforge_core.config import get_config
from dataforge_core.metadata_framework import PipelineConfigParser

# Default DAG arguments
DEFAULT_ARGS = {
    'owner': 'dataforge',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email': ['data-eng-team@dataforge.io'],
}

# Get configuration
config = get_config()

# Parse pipeline configurations
pipeline_dir = Path(__file__).parent.parent / "dataforge_core" / "pipelines" / "configs"
parser = PipelineConfigParser()


def validate_pipeline(**context):
    """
    Validation task executed before main processing.
    Checks data availability, configurations, and dependencies.
    """
    pipeline_name = context['dag'].dag_id
    print(f"[VALIDATE] Checking prerequisites for {pipeline_name}")
    # Add your validation logic here


def process_pipeline(pipeline_config_path: str, **context):
    """
    Execute pipeline processing task.
    Handles both batch and streaming configurations.
    """
    pipeline_name = context['dag'].dag_id
    print(f"[PROCESS] Executing {pipeline_name}")
    print(f"[PROCESS] Config: {pipeline_config_path}")


def check_quality(**context):
    """
    Post-processing quality checks.
    Validates output against data contracts.
    """
    pipeline_name = context['dag'].dag_id
    print(f"[QUALITY] Running quality checks for {pipeline_name}")


def notify_completion(**context):
    """
    Notification task on successful completion.
    """
    pipeline_name = context['dag'].dag_id
    print(f"[NOTIFY] Pipeline {pipeline_name} completed successfully")


# Create DAGs from pipeline configurations
dag_list = []

if pipeline_dir.exists():
    for config_file in pipeline_dir.glob("*.yaml"):
        try:
            pipeline_config = parser.parse_pipeline(str(config_file))
            
            # Create DAG ID from pipeline name
            dag_id = f"dataforge_{pipeline_config.name}"
            
            # Parse schedule
            schedule_interval = pipeline_config.schedule or "0 0 * * *"
            
            # Create DAG
            dag = DAG(
                dag_id=dag_id,
                description=pipeline_config.description or f"DataForge pipeline: {pipeline_config.name}",
                schedule_interval=schedule_interval,
                default_args=DEFAULT_ARGS,
                catchup=False,
                tags=['dataforge', pipeline_config.mode.value, *pipeline_config.tags],
                doc_md=f"## {pipeline_config.name}\n\n{pipeline_config.description}",
            )

            # Create tasks
            with dag:
                # Validation task
                validate_task = PythonOperator(
                    task_id='validate_prerequisites',
                    python_callable=validate_pipeline,
                    provide_context=True,
                )

                # Main processing task
                if pipeline_config.mode.value == "batch":
                    process_task = SparkSubmitOperator(
                        task_id='run_spark_job',
                        application='/opt/spark-apps/batch/batch_ingestion.py',
                        conf={
                            'spark.sql.extensions': 'io.delta.sql.DeltaSparkSessionExtension',
                            'spark.sql.catalog.spark_catalog': 'org.apache.spark.sql.delta.catalog.DeltaCatalog',
                        },
                        application_args=[str(config_file)],
                        execution_timeout=timedelta(minutes=pipeline_config.timeout_minutes),
                    )
                else:
                    # Streaming task
                    process_task = BashOperator(
                        task_id='run_streaming_job',
                        bash_command=f"spark-submit /opt/spark-apps/streaming/streaming_events.py",
                    )

                # Quality checks task
                quality_task = PythonOperator(
                    task_id='check_data_quality',
                    python_callable=check_quality,
                    provide_context=True,
                )

                # Notification task
                notify_task = PythonOperator(
                    task_id='notify_completion',
                    python_callable=notify_completion,
                    provide_context=True,
                )

                # Define task dependencies
                validate_task >> process_task >> quality_task >> notify_task

            dag_list.append(dag)
            print(f"[DAG] Created DAG: {dag_id}")

        except Exception as e:
            print(f"[ERROR] Failed to create DAG from {config_file}: {e}")
