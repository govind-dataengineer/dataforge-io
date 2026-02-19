"""
DataForge Metadata Framework
Manages pipeline metadata, lineage, audit trails, and data contracts.
Enterprise-grade tracking for compliance and governance.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceType(str, Enum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    DELTA = "delta"
    DATABASE = "database"
    API = "api"
    KAFKA = "kafka"


class PipelineAuditRecord:
    """Immutable audit record for pipeline execution."""

    def __init__(
        self,
        pipeline_name: str,
        pipeline_version: str,
        source_type: SourceType,
        source_path: str,
        target_path: str,
        status: PipelineStatus,
        record_count: int,
        processing_time_seconds: float,
        **metadata
    ):
        self.pipeline_id = str(uuid.uuid4())
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.source_type = source_type.value
        self.source_path = source_path
        self.target_path = target_path
        self.status = status.value
        self.record_count = record_count
        self.processing_time_seconds = processing_time_seconds
        self.timestamp = datetime.utcnow().isoformat()
        self.checksum = self._generate_checksum()
        self.metadata = metadata

    def _generate_checksum(self) -> str:
        """Generate checksum for audit trail verification."""
        data = f"{self.pipeline_id}{self.source_path}{self.record_count}{self.timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'pipeline_id': self.pipeline_id,
            'pipeline_name': self.pipeline_name,
            'pipeline_version': self.pipeline_version,
            'source_type': self.source_type,
            'source_path': self.source_path,
            'target_path': self.target_path,
            'status': self.status,
            'record_count': self.record_count,
            'processing_time_seconds': self.processing_time_seconds,
            'timestamp': self.timestamp,
            'checksum': self.checksum,
            'metadata': json.dumps(self.metadata)
        }


class MetadataManager:
    """
    Manages all DataForge metadata including lineage, audit trails, and data contracts.
    Integrates with PostgreSQL for persistence.
    """

    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self._initialize_database()

    def _initialize_database(self):
        """Initialize metadata tables."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create audit table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_audit (
                    pipeline_id UUID PRIMARY KEY,
                    pipeline_name VARCHAR(256) NOT NULL,
                    pipeline_version VARCHAR(50),
                    source_type VARCHAR(50),
                    source_path TEXT,
                    target_path TEXT,
                    status VARCHAR(50) NOT NULL,
                    record_count BIGINT,
                    processing_time_seconds FLOAT,
                    timestamp TIMESTAMP NOT NULL,
                    checksum VARCHAR(256),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_pipeline_name (pipeline_name)
                );
            """)

            # Create lineage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_lineage (
                    lineage_id UUID PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    transformation_logic TEXT,
                    pipeline_id UUID REFERENCES pipeline_audit(pipeline_id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create data contracts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_contracts (
                    contract_id UUID PRIMARY KEY,
                    dataset_name VARCHAR(256) NOT NULL UNIQUE,
                    schema JSONB NOT NULL,
                    quality_rules JSONB,
                    sla_metrics JSONB,
                    owner VARCHAR(256),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.commit()
            cursor.close()
            conn.close()
            logger.info("Metadata tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize metadata tables: {e}")
            raise

    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            host=self.db_config.get('host'),
            port=self.db_config.get('port'),
            user=self.db_config.get('username'),
            password=self.db_config.get('password'),
            database=self.db_config.get('databases', {}).get('metadata', 'dataforge_metadata')
        )

    def record_audit(self, audit_record: PipelineAuditRecord) -> str:
        """
        Record pipeline execution audit trail.
        
        Returns:
            Pipeline ID for tracking
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            data = audit_record.to_dict()
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))

            query = f"INSERT INTO pipeline_audit ({columns}) VALUES ({placeholders})"
            cursor.execute(query, list(data.values()))
            conn.commit()

            logger.info(f"Audit record saved: {audit_record.pipeline_id}")
            cursor.close()
            conn.close()

            return audit_record.pipeline_id
        except Exception as e:
            logger.error(f"Failed to record audit: {e}")
            raise

    def track_lineage(
        self,
        source_path: str,
        target_path: str,
        pipeline_id: str,
        transformation_logic: Optional[str] = None
    ):
        """Track data lineage from source to target."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            lineage_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO data_lineage (lineage_id, source_path, target_path, transformation_logic, pipeline_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (lineage_id, source_path, target_path, transformation_logic, pipeline_id))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Lineage tracked: {source_path} -> {target_path}")
        except Exception as e:
            logger.error(f"Failed to track lineage: {e}")
            raise

    def register_data_contract(
        self,
        dataset_name: str,
        schema: Dict[str, Any],
        quality_rules: Optional[Dict[str, Any]] = None,
        sla_metrics: Optional[Dict[str, Any]] = None,
        owner: Optional[str] = None
    ) -> str:
        """
        Register a data contract for a dataset.
        Defines expected schema, quality rules, and SLAs.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            contract_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO data_contracts (contract_id, dataset_name, schema, quality_rules, sla_metrics, owner)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                contract_id,
                dataset_name,
                json.dumps(schema),
                json.dumps(quality_rules or {}),
                json.dumps(sla_metrics or {}),
                owner
            ))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Data contract registered: {dataset_name}")
            return contract_id
        except Exception as e:
            logger.error(f"Failed to register data contract: {e}")
            raise

    def get_audit_history(
        self,
        pipeline_name: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve audit history for a pipeline."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT * FROM pipeline_audit
                WHERE pipeline_name = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (pipeline_name, limit))

            results = cursor.fetchall()
            cursor.close()
            conn.close()

            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to retrieve audit history: {e}")
            return []
