# DataForge Architecture & Design Patterns

> Deep-dive into the architecture, design decisions, and cloud-readiness of DataForge.

## Table of Contents

1. [Core Design Principles](#core-design-principles)
2. [Data Architecture](#data-architecture)
3. [Lakehouse Pattern](#lakehouse-pattern)
4. [Cost Optimization](#cost-optimization)
5. [Cloud Portability](#cloud-portability)
6. [Extensibility](#extensibility)

---

## Core Design Principles

### 1. Bronze/Silver/Gold Layered Architecture

**Why Three Layers?**

- **Bronze (Raw)**: Single source of truth. Immutable append-only storage. Never delete raw data.
- **Silver (Cleaned)**: Conformed, deduplicated, quality-validated. Ephemeral (90 days).
- **Gold (Analytics)**: Pre-aggregated, business-ready. Highly ephemeral (30 days).

**Benefits**:
- ✅ On-demand reprocessing: Can always re-derive Silver/Gold from Bronze
- ✅ Cost-effective: Keep cheap long-term storage (Bronze), ephemeral compute layers (Silver/Gold)
- ✅ Audit trail: Full history in Bronze for compliance
- ✅ Flexible schema: Silver/Gold can evolve without losing Bronze data

### 2. Immutability & Retention

| Layer | Format | Retention | Writemode | Partitioning |
|-------|--------|-----------|-----------|--------------|
| Bronze | Delta | Unlimited (years) | APPEND | date, symbol |
| Silver | Delta | 90 days (auto-cleanup) | OVERWRITE | date, symbol |
| Gold | Delta | 30 days (auto-cleanup) | APPEND | date, symbol |

**Key insight**: Bronze grows indefinitely but cheaply (S3/MinIO archive). Silver/Gold are re-creatable.

### 3. Event-Driven, Orchestrated Pipeline

```
00:00  ┌─────────────────────────────────────────────────────────┐
       │  Overnight batch: Yahoo Finance updates                 │
       │  (New trading day data available)                        │
       └─────────────────────────────────────────────────────────┘
         │
06:00   ▼  DAG: dag_bronze_ingestion
       ┌─────────────────────────────────────────────────────────┐
       │  Download OHLC → Spark Ingestion → Bronze Write         │
       │  • Partition by date + symbol                           │
       │  • Deduplication logic at source (latest record)         │
       │  • Add _ingestion_timestamp metadata                     │
       └─────────────────────────────────────────────────────────┘
         │
08:00   ▼  DAG: dag_silver_transform (depends on Bronze)
       ┌─────────────────────────────────────────────────────────┐
       │  Read Bronze → Dedup → Quality Checks → Silver Write     │
       │  • Remove duplicates (latest per symbol/date)            │
       │  • Null filtering on critical columns                    │
       │  • Type standardization                                  │
       │  • Add _quality_check_passed flag                        │
       └─────────────────────────────────────────────────────────┘
         │
10:00   ▼  DAG: dag_gold_analytics (depends on Silver)
       ┌─────────────────────────────────────────────────────────┐
       │  Read Silver → Calculate Metrics → Gold Write            │
       │  • Daily returns calculation                             │
       │  • 50/200 MA + volatility window functions               │
       │  • Daily aggregates (OHLC summary, volume)               │
       │  • Analytical metrics for BI/investment                  │
       └─────────────────────────────────────────────────────────┘
         │
       ▼  Services online
       ┌─────────────────────────────────────────────────────────┐
       │  API + Analytics: Query Gold layer for results           │
       │  • /stocks/history/{symbol}                              │
       │  • /stocks/performance                                   │
       │  • /stocks/top-gainers                                   │
       └─────────────────────────────────────────────────────────┘
```

---

## Data Architecture

### Schema Evolution Strategy

**Delta Lake enables schema-on-read**:

```python
# Bronze write
df.write.format("delta") \
    .mode("append") \
    .option("mergeSchema", "true")  # Allow new columns
    .save(bronze_path)

# Future: if new data has 'pe_ratio' column, it's added to schema
```

### Partitioning Strategy

**Chosen**: `date` + `symbol`
- ✅ Query filter 1: "Give me RELIANCE data for 2024" → Single partition
- ✅ Query filter 2: "Give me all stocks for 2024-09-20" → Single partition
- ✅ Scalability: File count = days × symbols (reasonable)

**Alternative rejected** (flat):
```
bronze/part-0001.snappy.parquet (bad: full scan needed)
```

### Deduplication Logic

**Silver layer deduplication**:

```python
window_spec = Window.partitionBy("symbol", "date").orderBy(col("_ingestion_timestamp").desc())
df_dedup = df.withColumn("rn", row_number().over(window_spec)) \
    .filter(col("rn") == 1) \
    .drop("rn")
```

Why:
- Late-arriving records happen (data arrives late, retransmitted)
- Keep latest version per symbol/date
- Automatically handles duplicates without manual intervention

---

## Lakehouse Pattern

### Key Lakehouse Characteristics

DataForge implements a **medallion architecture** (Bronze/Silver/Gold = lakehouse pattern):

1. **ACID Transactions** (Delta Lake)
   ```python
   # Transactional writes with ACID guarantees
   df.write.format("delta").mode("append").save(path)
   ```

2. **Schema Enforcement & Evolution**
   ```python
   # Enforce schema on read
   spark.read.format("delta").schema(expected_schema).load(path)
   ```

3. **Time Travel** (version history)
   ```python
   # Query specific version
   spark.read.format("delta").option("versionAsOf", 5).load(path)
   ```

4. **Unified Batch + Stream**
   ```python
   # Batch
   df.write.format("delta").mode("append").save(path)
   
   # Stream (future enhancement)
   stream.writeStream.format("delta").option("checkpointLocation", checkpoint).start(path)
   ```

### Local ↔ Cloud Equivalences

| Local | Azure | AWS |
|-------|-------|-----|
| MinIO | ADLS Gen2 (abfss://) | S3 (s3://), S3A (s3a://) |
| Spark Local | Databricks | EMR / Glue |
| SQLite/PG | SQL Server / ADLS | RDS / Glue Catalog |
| Airflow | ADF / Managed Airflow | MWAA |

---

## Cost Optimization

### Storage Tier Strategy

**Local**:
- All data in single MinIO instance (no tiering)

**Production (Cloud)**:

```
Bronze (Raw, Long-term):
  ├─ Hot (< 3 months):  S3 Standard / Premium ADLS
  ├─ Warm (3-12 mo):    S3 Standard-IA / Cool ADLS
  └─ Cold (1+ years):   S3 Glacier / Archive ADLS
  Retention: UNLIMITED

Silver (Cleaned, Medium-term):
  ├─ Active (< 90 days): S3 Standard
  └─ Auto-deleted after 90 days
  Retention: 90 DAYS (auto-cleanup)

Gold (Analytics, Short-term):
  ├─ Active (< 30 days): S3 Standard
  └─ Auto-deleted after 30 days
  Retention: 30 DAYS (auto-cleanup)
```

### Compute Cost Optimization

**Development** (local machine):
```
Cost per day: $0 (your laptop)

Benefit: Infinite iteration, fast feedback, no cloud bills
```

**Production** (Databricks):
```
# Job cluster (auto-shutdown)
cluster_config = {
    "spark_version": "13.3.x-scala2.12",
    "node_type_id": "i3.xlarge",
    "num_workers": 2,
    "aws_attributes": {
        "availability": "SPOT"  # 70% cheaper
    }
}

# Estimated: $0.50-1.00 per dag run
Run costs = 3 DAGs/day × $0.75 × 30 days = ~$68/month compute
Storage costs = 3-5GB/month bronze growth × $0.025 = ~$0.08/month
Total: ~$70/month production
```

---

## Cloud Portability

### Configuration-Based Storage Abstraction

**Local (Docker)**:
```yaml
storage:
  type: s3
  endpoint: "http://minio:9000"
  bucket_base: "s3a://dataforge"
  bronze_path: "s3a://dataforge/bronze"
```

**Azure Cloud**:
```yaml
storage:
  type: azureblob
  endpoint: "abfss://bronze@storageaccount.dfs.core.windows.net"
  access_key: "${AZURE_STORAGE_KEY}"
  bucket_base: "abfss://dataforge@storageaccount.dfs.core.windows.net"
```

**AWS Cloud**:
```yaml
storage:
  type: s3
  endpoint: "s3://dataforge-prod-bucket"
  access_key: "${AWS_ACCESS_KEY_ID}"
  secret_key: "${AWS_SECRET_ACCESS_KEY}"
```

**Implementation**: `StorageHelper` class handles path construction:
```python
bronze_path = storage.get_path('bronze')  # Returns endpoint/bucket/bronze
```

### Spark Migration Path

**Local (Docker)**:
```python
config.get('spark.master')  # "local[4]"
```

**Databricks** (Azure):
```python
# Set via environment / config
spark_master = "https://adb-<workspace_id>.azuredatabricks.net"
```

**EMR** (AWS):
```python
spark_master = "spark://master.example.eu-west-1.compute.internal:7077"
```

---

## Extensibility

### Adding New Data Sources

**Example: NSE Bhavcopy CSV**

1. Extend `StockDataIngestor`:
```python
class StockDataIngestor:
    def download_nse_bhavcopy(self, symbol, date):
        """Download from NSE (requires registration)"""
        url = f"https://www1.nseindia.com/DispatchReport/{date}_bhav.csv.zip"
        # Download + parse
```

2. Update config:
```yaml
ingestion:
  sources:
    - name: "yahoo_finance"
      symbols: ["RELIANCE.NS"]
    - name: "nse_bhavcopy"
      symbols: ["RELIANCE"]  # Different format
```

3. Update DAG:
```python
def ingest_stock_data(**context):
    ingestor = StockDataIngestor(spark)
    # Choose source based on config
```

### Adding New Transformations

**Example: ML Feature Engineering**

1. Create `GoldPipeline.calculate_ml_features()`:
```python
class GoldPipeline:
    def calculate_ml_features(self, df):
        # Add lag features, momentum indicators, etc.
        return df.withColumn("price_momentum_5d", ...)
```

2. Wire into DAG:
```python
def generate_gold_analytics(**context):
    gold.run_transformation()
    gold.calculate_ml_features()
```

### Supporting Real-Time Streaming

**Future**: Add Kafka streaming ingestion:

```python
class StreamingIngestor:
    def ingest_from_kafka(self, topic, target_path):
        df = self.spark.readStream.format("kafka") \
            .option("kafka.bootstrap.servers", kafka_brokers) \
            .option("subscribe", topic) \
            .load()
        
        # Stream to Bronze (Delta Lake supports streamed writes)
        df.writeStream.format("delta") \
            .option("checkpointLocation", checkpoint) \
            .start(target_path)
```

---

## Monitoring & Observability

### Logging Strategy

```
Level    Used for
-----    --------
DEBUG    Development, detailed execution trace
INFO     Pipeline milestones, record counts
WARNING  Data quality issues, late arrivals
ERROR    Pipeline failures, exceptions
```

**Structured logging** (via structlog):
```python
logger.info("Transformation complete", 
    layer="silver", 
    records=1000000, 
    duration_seconds=45)
```

Enables: machine-parsing, analytics, alerting

### Metrics to Track

```
Pipeline Metrics:
  - Records processed per DAG run
  - Processing time (start → end)
  - Error rate / failure reason
  - Data quality score (nulls, duplicates)

Data Metrics:
  - Growing symbols count
  - Latest date for each symbol
  - Average volume per symbol
  - Return distribution (mean, std)

System Metrics:
  - Spark job duration
  - Memory consumption
  - Partition counts
  - Storage size by layer
```

---

## Governance & Compliance

### Data Lineage Tracking

**Bronze → Silver → Gold documented**:
```
date: 2024-01-01
symbol: RELIANCE.NS

Bronze (Raw)
  ↓ [dedup + null filter + schema standard]
Silver (Clean)
  ↓ [window functions + aggs]
Gold (Analytics)
```

### Retention Compliance

```
Regulation: SEC / RBI requires 7-year stock data history
Solution:   Bronze layer (unlimited retention)

Regulation: GDPR right-to-be-forgotten
Current:    Not applicable (financial data, not PII)
Future:     Implement anonymization layer if needed
```

---

## Performance Tuning

### Query Optimization

**Before**:
```python
df.select("*").filter(col("symbol") == "RELIANCE.NS")
# Full table scan
```

**After** (partition pruning):
```python
df.filter(col("date") >= "2024-01-01" & col("symbol") == "RELIANCE.NS")
# Reads only required partitions
```

### Spark Tuning Parameters

```python
spark.conf.set("spark.sql.shuffle.partitions", 200)  # Parallelism
spark.conf.set("spark.sql.adaptive.enabled", "true")  # AQE
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
```

---

## Testing Strategy

### Unit Tests
- Config loading
- Schema validation
- Transformation logic (dedup, nulls)

### Integration Tests
- Full Bronze → Silver → Gold flow
- Data quality checks
- Partitioning validation

### API Tests (Future)
- Endpoint response format
- Query execution correctness
- Error handling

---

## Glossary

| Term | Definition |
|------|-----------|
| OHLC | Open, High, Low, Close prices |
| MA | Moving Average |
| YTD | Year-to-date |
| Medallion | Bronze/Silver/Gold lakehouse pattern |
| CDC | Change Data Capture (future streaming) |
| DQ | Data Quality |
| SLA | Service Level Agreement |
| RPO | Recovery Point Objective (data intervals) |
| RTO | Recovery Time Objective (restart time) |

---

## References

- [Delta Lake Official Docs](https://docs.delta.io/)
- [Apache Spark SQL Programming Guide](https://spark.apache.org/docs/latest/sql-programming-guide.html)
- [Databricks Lakehouse Architecture](https://databricks.com/blog/2020/01/30/what-is-a-data-lakehouse.html)
- [Azure Databricks Architecture](https://docs.microsoft.com/en-us/azure/databricks/getting-started/overview)

---

**Last Updated**: February 2024 | **Version**: 1.0.0
