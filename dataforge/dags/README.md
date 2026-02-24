"""
Airflow DAGs Directory
This directory is mapped to Airflow's DAG folder.
DAGs are automatically discovered and loaded by Airflow.
"""

# DAG definitions are in dataforge/orchestration.py
# Symlink or copy orchestration.py here, or:
# In Airflow container:
#   cd /opt/airflow/dags
#   ln -s /opt/dataforge/orchestration.py .

# IMPORTANT: Keep this as is for Airflow auto-discovery
