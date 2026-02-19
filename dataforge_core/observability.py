"""
DataForge Observability & Monitoring
Metrics collection, monitoring integration, and alerting.
Prometheus-compatible metrics for enterprise observability.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Enterprise-grade metrics collector for DataForge pipelines.
    Prometheus-compatible for easy integration with monitoring stacks.
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()

        # Pipeline execution metrics
        self.pipeline_executions = Counter(
            'dataforge_pipeline_executions_total',
            'Total number of pipeline executions',
            ['pipeline_name', 'status'],
            registry=self.registry
        )

        self.pipeline_duration = Histogram(
            'dataforge_pipeline_duration_seconds',
            'Pipeline execution duration in seconds',
            ['pipeline_name'],
            registry=self.registry,
            buckets=(10, 30, 60, 300, 600, 1800, 3600)
        )

        # Data processing metrics
        self.records_processed = Counter(
            'dataforge_records_processed_total',
            'Total records processed',
            ['pipeline_name', 'stage'],
            registry=self.registry
        )

        self.records_failed = Counter(
            'dataforge_records_failed_total',
            'Total records that failed processing',
            ['pipeline_name', 'stage', 'error_type'],
            registry=self.registry
        )

        self.data_volume_bytes = Counter(
            'dataforge_data_volume_bytes_total',
            'Total data volume processed in bytes',
            ['pipeline_name'],
            registry=self.registry
        )

        # Quality metrics
        self.quality_checks = Counter(
            'dataforge_quality_checks_total',
            'Total quality checks performed',
            ['dataset_name', 'check_type', 'status'],
            registry=self.registry
        )

        self.schema_violations = Counter(
            'dataforge_schema_violations_total',
            'Total schema violations detected',
            ['dataset_name'],
            registry=self.registry
        )

        # Storage metrics
        self.storage_utilization_bytes = Gauge(
            'dataforge_storage_utilization_bytes',
            'Current storage utilization in bytes',
            ['layer'],  # bronze, silver, gold
            registry=self.registry
        )

        # Spark metrics
        self.spark_job_duration = Histogram(
            'dataforge_spark_job_duration_seconds',
            'Spark job execution duration',
            ['job_name'],
            registry=self.registry
        )

        self.spark_task_failures = Counter(
            'dataforge_spark_task_failures_total',
            'Total Spark task failures',
            ['job_name'],
            registry=self.registry
        )

    def record_pipeline_start(self, pipeline_name: str):
        """Record pipeline start."""
        self._start_times[pipeline_name] = time.time()
        logger.info(f"Pipeline started: {pipeline_name}")

    def record_pipeline_completion(
        self,
        pipeline_name: str,
        status: str,  # success, failed, skipped
        records_processed: int = 0,
        data_volume_bytes: int = 0
    ):
        """Record pipeline completion with metrics."""
        # Record execution count
        self.pipeline_executions.labels(
            pipeline_name=pipeline_name,
            status=status
        ).inc()

        # Record duration
        if pipeline_name in self._start_times:
            duration = time.time() - self._start_times[pipeline_name]
            self.pipeline_duration.labels(pipeline_name=pipeline_name).observe(duration)
            del self._start_times[pipeline_name]

        # Record processed records
        if records_processed > 0:
            self.records_processed.labels(
                pipeline_name=pipeline_name,
                stage='overall'
            ).inc(records_processed)

        # Record data volume
        if data_volume_bytes > 0:
            self.data_volume_bytes.labels(pipeline_name=pipeline_name).inc(data_volume_bytes)

        logger.info(
            f"Pipeline completed: {pipeline_name} ({status}) - "
            f"{records_processed} records, {data_volume_bytes} bytes"
        )

    def record_quality_check(
        self,
        dataset_name: str,
        check_type: str,  # schema, duplicate, null, custom
        passed: bool
    ):
        """Record quality check result."""
        status = 'passed' if passed else 'failed'
        self.quality_checks.labels(
            dataset_name=dataset_name,
            check_type=check_type,
            status=status
        ).inc()

    def record_schema_violation(self, dataset_name: str):
        """Record schema violation."""
        self.schema_violations.labels(dataset_name=dataset_name).inc()

    def record_storage_utilization(self, layer: str, bytes_used: int):
        """Record storage utilization by layer."""
        self.storage_utilization_bytes.labels(layer=layer).set(bytes_used)

    def record_spark_job(self, job_name: str, duration_seconds: float, failed: bool = False):
        """Record Spark job metrics."""
        self.spark_job_duration.labels(job_name=job_name).observe(duration_seconds)
        if failed:
            self.spark_task_failures.labels(job_name=job_name).inc()

    def get_metrics(self) -> str:
        """Get Prometheus-format metrics."""
        return generate_latest(self.registry).decode('utf-8')

    # Helper for tracking start times
    _start_times: Dict[str, float] = {}


class PipelineMetrics:
    """Context manager for tracking pipeline metrics."""

    def __init__(self, metrics_collector: MetricsCollector, pipeline_name: str):
        self.metrics = metrics_collector
        self.pipeline_name = pipeline_name
        self.start_time = None
        self.records_processed = 0
        self.data_volume_bytes = 0

    def __enter__(self):
        self.start_time = time.time()
        self.metrics.record_pipeline_start(self.pipeline_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        status = 'failed' if exc_type is not None else 'success'
        self.metrics.record_pipeline_completion(
            self.pipeline_name,
            status,
            self.records_processed,
            self.data_volume_bytes
        )
        if exc_type is not None:
            logger.error(f"Pipeline failed: {self.pipeline_name} - {exc_val}")


class AlertingConfig:
    """Configuration for pipeline alerts."""

    def __init__(self):
        self.alert_rules = []

    def add_alert_rule(self, name: str, condition: str, severity: str = 'warning'):
        """Add alert rule."""
        self.alert_rules.append({
            'name': name,
            'condition': condition,
            'severity': severity,
            'created_at': datetime.utcnow().isoformat()
        })

    def to_prometheus_response(self) -> str:
        """Generate Prometheus alert rule format."""
        rules = []
        for rule in self.alert_rules:
            rules.append(f"""
  - alert: {rule['name']}
    expr: {rule['condition']}
    for: 5m
    labels:
      severity: {rule['severity']}
    annotations:
      summary: "Alert: {rule['name']}"
            """)
        return f"groups:\n  - name: dataforge_alerts\n    rules:{rules}"
