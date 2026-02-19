"""
Unit tests for DataForge metadata and audit trails
"""

import pytest
from dataforge_core.metadata import MetadataManager, PipelineAuditRecord, PipelineStatus, SourceType


class TestMetadataManager:
    """Tests for metadata management and audit trails."""

    @pytest.fixture
    def metadata_manager(self):
        """Create test metadata manager."""
        # Use test database config
        config = {
            'host': 'localhost',
            'port': 5432,
            'username': 'postgres',
            'password': 'postgres',
            'databases': {
                'metadata': 'test_dataforge_metadata'
            }
        }
        try:
            manager = MetadataManager(config)
            yield manager
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")

    def test_audit_record_creation(self):
        """Test creating audit records."""
        record = PipelineAuditRecord(
            pipeline_name="test_pipeline",
            pipeline_version="1.0.0",
            source_type=SourceType.CSV,
            source_path="/test/data.csv",
            target_path="/target/data",
            status=PipelineStatus.SUCCESS,
            record_count=1000,
            processing_time_seconds=10.5
        )
        
        assert record.pipeline_name == "test_pipeline"
        assert record.record_count == 1000
        assert record.source_type == "csv"
        assert record.status == "success"
        assert len(record.checksum) == 64  # SHA256

    def test_audit_record_to_dict(self):
        """Test converting audit record to dictionary."""
        record = PipelineAuditRecord(
            pipeline_name="test",
            pipeline_version="1.0.0",
            source_type=SourceType.JSON,
            source_path="/test",
            target_path="/target",
            status=PipelineStatus.FAILED,
            record_count=100,
            processing_time_seconds=5.0
        )
        
        record_dict = record.to_dict()
        assert record_dict['pipeline_name'] == "test"
        assert record_dict['status'] == "failed"
        assert 'timestamp' in record_dict
        assert 'checksum' in record_dict


class TestObservability:
    """Tests for metrics and observability."""

    def test_metrics_collector(self):
        """Test metrics collection."""
        from dataforge_core.observability import MetricsCollector
        
        metrics = MetricsCollector()
        
        # Record events
        metrics.record_pipeline_start("test_pipeline")
        metrics.record_pipeline_completion(
            "test_pipeline",
            "success",
            records_processed=1000,
            data_volume_bytes=10_000_000
        )
        
        # That should not raise exceptions
        assert True

    def test_quality_checks(self):
        """Test quality check recording."""
        from dataforge_core.observability import MetricsCollector
        
        metrics = MetricsCollector()
        
        # Record quality checks
        metrics.record_quality_check("orders", "schema", True)
        metrics.record_quality_check("orders", "null", False)
        metrics.record_schema_violation("customers")
        
        # Should not raise
        assert True
