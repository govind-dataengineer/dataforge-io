# DataForge - Modern Financial Data Lakehouse Platform

> A production-grade, cloud-portable data engineering platform built for financial market data (Indian stocks). Run locally with Docker, scale to Azure Databricks or AWS with minimal refactoring.

**Status**: v1.0.0 | **Target Users**: Data Engineers, Platform Architects, Financial Data Scientists

---

## 🎯 Executive Summary

DataForge implements a **modern lakehouse architecture** for financial data with:
- **Bronze Layer**: Raw, immutable, long-term storage (1+ years)
- **Silver Layer**: Cleaned, deduplicated data (90-day ephemeral retention)
- **Gold Layer**: Analytics-ready aggregations (30-day retention)

**Design principles**: On-demand reprocessing vs. heavy duplication, local-first development, cloud-portable code, cost-optimized compute.

---

## 🏗️ Architecture Overview

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATAFORGE PLATFORM (v1.0)                        │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐  ┌──────────────────────────┐  ┌────────────────────────┐
│  INGESTION LAYER         │  │  TRANSFORMATION LAYER    │  │  API SERVING LAYER     │
├──────────────────────────┤  ├──────────────────────────┤  ├────────────────────────┤
│ ▪ Yahoo Finance (yfinance│  │ ▪ Bronze Pipeline        │  │ ▪ FastAPI Service      │
│ ▪ Daily OHLC Data        │  │ ▪ Silver Pipeline (Clean)│  │ ▪ SQL Query Engine     │
│ ▪ NSE Bhavcopy (Future)  │  │ ▪ Gold Pipeline (Agg)    │  │ ▪ DuckDB Integration   │
│ ▪ Kafka Real-time        │  │ ▪ Delta Lake Merge       │  │ ▪ JSON/CSV Export      │
└──────────────────────────┘  └──────────────────────────┘  └────────────────────────┘
         │                              │                             │
         └──────────────────────────────┆─────────────────────────────┘
                                        │
         ┌──────────────────────────────┴──────────────────────────────┐
         │                 DATA LAKE (MinIO / S3a)                      │
         │  ┌────────┐  ┌────────┐  ┌────────┐                         │
         │  │ BRONZE │  │ SILVER │  │ GOLD   │                         │
         │  │ (Raw)  │  │(Clean) │  │(Agg)   │                         │
         │  │ ∞ yrs  │  │90 days │  │30 days │                         │
         │  └────────┘  └────────┘  └────────┘                         │
         └─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│        ORCHESTRATION (Airflow) & COMPUTE (Spark) & METADATA (PG)        │
│  ▪ DAG: Bronze Ingestion → Silver Transform → Gold Analytics           │
│  ▪ Spark: Local Mode (Dev) → Databricks (Prod)                         │
│  ▪ PostgreSQL: Config, audit logs, lineage tracking                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Local Docker Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                      LOCAL DOCKER COMPOSE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Postgres          MinIO            Spark Master       Spark Worker │
│  :5432            :9000,:9001        :7077,:8080        :8081       │
│  (Metadata)       (Data Lake)      (Compute)         (Compute)     │
│                                                                     │
│  Airflow           FastAPI          Jupyter Lab                     │
│  :8888            :8000             :8888                           │
│  (Scheduler)      (APIs)            (Dev Notebook)                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
dataforge/
├── docker/                           # Docker configurations
│   ├── docker-compose.yml            # Full local stack
│   ├── Dockerfile.spark              # Spark image
│   ├── Dockerfile.airflow            # Airflow image
│   ├── Dockerfile.api                # FastAPI image
│   └── Dockerfile.jupyter            # Jupyter image
│
├── ingestion/                        # Data ingestion
│   └── __init__.py                   # StockDataIngestor (Yahoo Finance)
│
├── pipelines/                        # ETL pipelines
│   ├── __init__.py                   # BronzePipeline
│   ├── silver_pipeline.py            # Deduplication, Cleaning
│   └── gold_pipeline.py              # Analytics, Aggregations
│
├── api/                              # FastAPI service
│   ├── main.py                       # API endpoints
│   └── __init__.py
│
├── configs/                          # Configuration files
│   ├── config.yaml                   # Base config
│   └── env.local.yaml                # Local overrides
│
├── data/                             # Local data storage (dev only)
│   ├── bronze/                       # Raw data
│   ├── silver/                       # Cleaned data
│   └── gold/                         # Analytics data
│
├── notebooks/                        # Jupyter notebooks for exploration
│   └── (examples here)
│
├── tests/                            # Unit & integration tests
│   ├── test_pipelines.py
│   └── __init__.py
│
├── core.py                           # Core utilities (config, logging, Spark)
├── orchestration.py                  # Airflow DAGs
├── requirements.txt                  # Python dependencies
├── __init__.py
│
└── README.md (this file)
```

---

## 🚀 Quick Start (5 minutes)

### Prerequisites

- **macOS/Linux**: Docker Desktop (4+ CPU, 8+ GB RAM)
- **Windows**: WSL2 + Docker Desktop
- **Apple Silicon**: M1/M2 Macs fully supported (ARM64 images)

### Setup

1. **Clone and navigate**:
   ```bash
   cd dataforge
   ```

2. **Build Docker images**:
   ```bash
   docker-compose -f docker/docker-compose.yml build
   ```

3. **Start services**:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

4. **Wait for health checks** (~30 seconds):
   ```bash
   docker-compose -f docker/docker-compose.yml ps
   ```

5. **Access services**:
   - Airflow UI: http://localhost:8888 (admin/admin)
   - Spark Master: http://localhost:8080
   - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
   - API Docs: http://localhost:8000/docs
   - Jupyter: http://localhost:8888 (click link in terminal)

### Run First Pipeline

**Via Airflow UI**:
1. Go to http://localhost:8888
2. Enable `dag_bronze_ingestion` 
3. Trigger manually
4. Monitor execution

**Via CLI**:
```bash
docker exec dataforge-airflow airflow dags test dag_bronze_ingestion 2024-01-01
```

---

## 📊 Data Model

### Bronze Layer (Raw)

**Table**: `dataforge/bronze/date=YYYY-MM-DD/symbol=TICKER/`

| Column | Type | Notes |
|--------|------|-------|
| date | DATE | Partition key |
| symbol | STRING | Partition key (e.g., RELIANCE.NS) |
| open | DOUBLE | Opening price |
| high | DOUBLE | Daily high |
| low | DOUBLE | Daily low |
| close | DOUBLE | Closing price |
| adjusted_close | DOUBLE | Adjusted close |
| volume | LONG | Trading volume |
| _ingestion_timestamp | TIMESTAMP | Metadata |

**Retention**: Unlimited (long-term archive)

---

### Silver Layer (Cleaned)

**Transformations**:
- ✅ Deduplication (per symbol/date)
- ✅ Null filtering (date, symbol, close)
- ✅ Schema standardization
- ✅ Type casting

**Retention**: 90 days (auto-cleanup)

---

### Gold Layer (Analytics)

**Metrics Computed**:
- Daily returns (%)
- 50-day moving average
- 200-day moving average
- 30-day rolling volatility
- Daily aggregates (OHLC summary)

**Example Query**:
```sql
SELECT 
  symbol,
  date,
  daily_close,
  daily_return_pct,
  ma_50_day,
  ma_200_day,
  volatility_30d
FROM gold
WHERE symbol = 'RELIANCE.NS'
  AND date >= '2024-01-01'
ORDER BY date DESC;
```

**Retention**: 30 days (analytics backfill available from Bronze)

---

## 🔄 Pipeline Execution Flow

### Airflow DAGs

**DAG 1: `dag_bronze_ingestion`** (6 AM weekdays)
```
Yahoo Finance Download → Spark Ingestion → Bronze Write
├─ Downloads OHLC data
├─ Converts to Spark DataFrame
└─ Writes with date/symbol partitioning
```

**DAG 2: `dag_silver_transform`** (8 AM weekdays)
```
Bronze Read → Deduplication → Null Filtering → Silver Write
├─ Latest record per symbol/date
├─ Validation checks
└─ 90-day auto-cleanup
```

**DAG 3: `dag_gold_analytics`** (10 AM weekdays)
```
Silver Read → Calculate Returns → MA/Volatility → Gold Write
├─ Window functions for aggregations
├─ Metric computation
└─ 30-day auto-cleanup
```

**DAG 4: `dag_full_pipeline_orchestration`** (6 AM weekdays)
```
Bronze → Silver → Gold (end-to-end)
```

---

## 🌐 API Endpoints

### Health & Status

```bash
GET /health
GET /config
```

### Stock History

```bash
GET /stocks/history/{symbol}?start_date=2024-01-01&end_date=2024-12-31&limit=100
```

Example:
```json
{
  "symbol": "RELIANCE.NS",
  "records": [
    {
      "date": "2024-09-20",
      "daily_close": 2845.50,
      "daily_return_pct": 1.23,
      "ma_50_day": 2820.45,
      "ma_200_day": 2750.30,
      "volatility_30d": 2.34
    }
  ]
}
```

### Performance Analytics

```bash
GET /stocks/performance?period_days=30&top_n=10
GET /stocks/top-gainers?limit=10
```

### Advanced SQL Query

```bash
POST /query/sql
Content-Type: application/json

{
  "query": "SELECT symbol, AVG(daily_return_pct) as avg_return FROM gold WHERE date >= '2024-01-01' GROUP BY symbol LIMIT 10"
}
```

---

## 🛠️ Development Workflow

### Local Development (No Docker)

1. **Create Python venv**:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run Spark locally**:
   ```python
   from dataforge.core import initialize_dataforge
   from dataforge.pipelines.gold_pipeline import GoldPipeline
   
   config, spark = initialize_dataforge(
       config_path="configs/config.yaml",
       env_override="configs/env.local.yaml"
   )
   
   gold = GoldPipeline(spark, "data/gold", "data/silver")
   gold.run_transformation()
   ```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_pipelines.py::TestBronzePipeline -v

# With coverage
pytest tests/ --cov=dataforge --cov-report=html
```

### Jupyter Notebook Development

```bash
# Access Jupyter at http://localhost:8888
# Example notebook workflow:

from dataforge.core import initialize_dataforge

config, spark = initialize_dataforge()

# Read Gold layer
df = spark.read.format("delta").load(config.get('storage.gold_path'))
df.show()

# Analyze
df.groupBy("symbol").agg({"daily_return_pct": "avg"}).show()
```

---

## ☁️ Cloud Migration Guide

### Azure Databricks Migration

**Step 1: Update Config**
```yaml
storage:
  type: azureblob
  endpoint: "abfss://bronze@storageaccount.dfs.core.windows.net"
  access_key: "<storage_key>"
  
spark:
  master: "https://<databricks-instance>.azuredatabricks.net"  # Databricks cluster
  app_name: "DataForge"
```

**Step 2: Map Storage**
```
Local: data/bronze → Azure: abfss://bronze@*.dfs.core.windows.net
Local: data/silver → Azure: abfss://silver@*.dfs.core.windows.net
Local: data/gold   → Azure: abfss://gold@*.dfs.core.windows.net
```

**Step 3: Deploy to Databricks**
- Upload `dataforge/` to Databricks Workspace
- Create Databricks UC (Unity Catalog) tables
- Attach Airflow DAGs to Databricks Workflows or external Airflow

### AWS Migration

**Step 1: Update Config**
```yaml
storage:
  type: s3
  endpoint: "s3://dataforge-prod-bronze"
  access_key: "<aws_access_key>"
  secret_key: "<aws_secret_key>"
```

**Step 2: Use EMR or Glue**
- EMR: Deploy Spark cluster + Airflow
- Glue: Rewrite pipelines using Glue Jobs

---

## 💰 Cost Optimization Strategy

### Development vs. Production

**Development (Local/Docker)**:
- ✅ Free compute (local machine)
- ✅ Minimal storage (sample data)
- ✅ Fast iteration feedback loop

**Production (Cloud)**:
- Ephemeral Silver: Auto-delete after 90 days
- Ephemeral Gold: Auto-delete after 30 days
- Bronze: Tiered storage (hot → cold after 6 months)
- Compute: Spot instances, job clusters, auto-shutdown

### Retention Policies

```python
# Silver cleanup (90 days)
pipeline.cleanup_old_data(retention_days=90)

# Gold cleanup (30 days)
pipeline.cleanup_old_data(retention_days=30)

# Bronze compression (archive to cold storage after 1 year)
# (Implement in production)
```

---

## 🔐 Security & Best Practices

### Secrets Management

**Local** (`.env`):
```
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin_dev
POSTGRES_PASSWORD=dataforge_dev
```

**Production** (Azure KeyVault / AWS Secrets Manager):
```yaml
storage:
  access_key: "${AZURE_STORAGE_KEY}"
  secret_key: "${AZURE_STORAGE_SECRET}"
```

### Data Governance

- ✅ **Lineage Tracking**: Bronze → Silver → Gold
- ✅ **Audit Logging**: All transformations logged
- ✅ **Data Quality**: Null checks, duplicate detection
- ✅ **Schema Evolution**: Delta Lake handles schema updates
- ✅ **Access Control**: (Future) Row-level security via UC

---

## 📈 Monitoring & Observability

### Logs

```bash
# Airflow logs
docker logs -f dataforge-airflow

# Spark logs
docker logs -f dataforge-spark-master

# API logs
docker logs -f dataforge-api
```

### Metrics

- Airflow: Metrics at http://localhost:8888/admin/metrics
- Spark: UI at http://localhost:8080
- API: Prometheus metrics at `/metrics`

### Health Checks

```bash
# Test all services
curl http://localhost:8000/health
curl http://localhost:8888/health

# Check PostgreSQL
psql -h localhost -U dataforge -d dataforge_db -c "SELECT 1;"
```

---

## 🚧 Future Roadmap

- [ ] Real-time Kafka streaming ingestion
- [ ] Great Expectations data quality framework
- [ ] Spark Delta Live Tables support
- [ ] Unity Catalog integration (Databricks)
- [ ] ML feature store layer
- [ ] LLM-powered financial Q&A
- [ ] BI tool integrations (Power BI, Tableau)
- [ ] Advanced data governance (DQA, profiling)

---

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/xyz`
2. Write tests: `pytest tests/`
3. Format code: `black dataforge/`
4. Submit PR

---

## 📖 For Interview Preparation

This codebase demonstrates:

1. **Architecture**: Lakehouse design, modular pipelines, separation of concerns
2. **Scale**: Local Docker + cloud-ready code (single config change)
3. **Best Practices**: 
   - Partitioned data for query efficiency
   - Retention policies for cost control
   - Config-driven execution
   - Comprehensive logging & error handling
   - Production-grade DAGs with retries
4. **Data Engineering fundamentals**:
   - PySpark, Delta Lake, partitioning
   - ETL/ELT patterns
   - Incremental processing
   - Data quality checks

**Interview Questions You Can Answer**:
- "How do you reduce data duplication?" → Bronze/Silver/Gold layers
- "What's your cost optimization strategy?" → Ephemeral layers + cleanup policies
- "How do you make code cloud-portable?" → Config-based storage paths
- "Describe your orchestration approach" → Airflow DAGs with retries

---

## 📝 License

MIT

---

## 📧 Contact

For questions: dataforge@example.com

---

**Built with ❤️ for modern data engineering** | DataForge v1.0.0 | 2024
