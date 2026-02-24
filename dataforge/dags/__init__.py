"""
Airflow DAGs Initialization
"""

import sys
import os

# Add dataforge to Python path for Airflow
sys.path.insert(0, '/opt/dataforge')

# Import all DAGs to register them with Airflow
try:
    from dataforge.orchestration import dag_bronze, dag_silver, dag_gold, dag_full_pipeline
except ImportError as e:
    print(f"Warning: Could not load DataForge DAGs: {e}")
