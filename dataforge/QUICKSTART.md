# DataForge - 60-Second Quick Start

> **For impatient data engineers** 🚀

## Prerequisites

- Docker Desktop (4+ CPU, 8 GB RAM)
- macOS / Linux / Windows (WSL2)

## One-Command Setup

```bash
cd dataforge
make setup
```

Wait 2 minutes. All services will be online.

## Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **Airflow** | http://localhost:8888 | admin / admin |
| **API** | http://localhost:8000/docs | (no auth) |
| **Spark UI** | http://localhost:8080 | (no auth) |
| **MinIO** | http://localhost:9001 | minioadmin / minioadmin |

## Test It

### Option 1: Via Airflow UI (Easiest)
1. Open http://localhost:8888
2. Click `dag_bronze_ingestion`
3. Click "Trigger DAG" (blue button)
4. Monitor execution

### Option 2: Via CLI
```bash
make dag-bronze    # Run Bronze ingestion
make dag-silver    # Run Silver transform
make dag-gold      # Run Gold analytics
make dag-full      # Run all 3 (dependency aware)
```

### Option 3: Via API
```bash
curl -s http://localhost:8000/stocks/top-gainers | python -m json.tool
```

## What Just Happened?

```
1. Bronze Ingestion (6 AM)
   Downloaded 1 year OHLC data for 5 Indian stocks (RELIANCE, TCS, etc)
   ↓
   ~ 1260 records stored partitioned by date/symbol

2. Silver Transform (8 AM)
   Deduplicated + cleaned
   ↓
   ~ 1260 clean records

3. Gold Analytics (10 AM)
   Computed: daily returns, 50/200 MA, volatility
   ↓
   Analytics-ready aggregates
```

## Next Steps

### 👉 Explore Data
```bash
# Via Jupyter notebook
# Jupyter is at same URL as Airflow on alternative port

# Or via SQL
# Edit /notebooks/01_bronze_exploration.ipynb
```

### 👉 Modify Configuration
```bash
# Edit configs/config.yaml
# Add/remove stock symbols in:
#   ingestion.sources[0].symbols

# Restart: make down && make up
```

### 👉 Run Tests
```bash
make test                # Full suite
make test-cov           # With coverage report
```

### 👉 Stop Services
```bash
make down
```

---

## Troubleshooting

**Port already in use?**
```bash
lsof -i :8000  # Find process
kill -9 <PID>
```

**Services won't start?**
```bash
make clean              # Remove cache
docker system prune    # Clean up Docker
make setup             # Fresh start
```

**OutOfMemory errors?**
- Increase Docker RAM: Docker Desktop → Settings → Resources → Memory: 10GB+

---

## Files You Should Know

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Local stack definition |
| `orchestration.py` | Airflow DAGs |
| `core.py` | Config + Spark mgmt |
| `pipelines/` | ETL logic |
| `api/main.py` | FastAPI endpoints |
| `configs/config.yaml` | Configuration |
| `README.md` | Full documentation |
| `ARCHITECTURE.md` | Technical deep-dive |

---

## Interview Talking Points

✅ **Architecture**: Medallion pattern (Bronze/Silver/Gold) for cost optimization
✅ **Scale**: Local Docker + cloud-portable (Azure/AWS single config change)
✅ **Data Eng**: PySpark, Delta Lake, partitioning, incremental processing
✅ **DevOps**: Docker, Airflow, cloud-ready infrastructure-as-code
✅ **Best Practices**: Config-driven, structured logging, data quality checks

---

**Happy data engineering!** 🎉

For full docs: Read `README.md` | For architecture: Read `ARCHITECTURE.md`
