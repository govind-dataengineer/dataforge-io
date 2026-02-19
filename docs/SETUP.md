# DataForge.io Local Setup Guide

## System Requirements

### Minimum
- macOS 10.15+ (Intel or Apple Silicon M1/M2)
- Docker & Docker Compose 20.10+
- 8GB RAM
- 50GB free disk space
- Git

### Recommended
- macOS 12+ (Monterey or later)
- Docker Desktop 4.0+
- 16GB+ RAM
- 100GB free disk space
- VS Code with Docker extension

## Step 1: Install Docker Desktop

### macOS (Intel & Apple Silicon)
1. Download **Docker Desktop** from https://www.docker.com/products/docker-desktop
2. For **M1/M2 Macs**: Docker Desktop now fully supports ARM architecture
3. Install and launch Docker Desktop
4. Verify installation:
   ```bash
   docker --version
   docker-compose --version
   ```

## Step 2: Clone Repository

```bash
git clone https://github.com/yourusername/dataforge-io.git
cd dataforge-io
```

## Step 3: Configure Environment

```bash
# Copy environment template
cp .env.template .env

# Edit .env if needed
vi .env
```

### Default .env values
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
DATAFORGE_ENV=dev
```

## Step 4: Start Services

```bash
# Build and start all services
docker-compose up -d

# Wait for services to be ready (30-60 seconds)
docker-compose ps

# Check logs if needed
docker-compose logs -f
```

### Expected Output
```
CONTAINER ID   IMAGE                                    STATUS
xxx            postgres:15-alpine                        Up (healthy)
xxx            confluentinc/cp-zookeeper:7.5.0         Up 
xxx            confluentinc/cp-kafka:7.5.0              Up
xxx            minio/minio:latest                       Up
xxx            bitnami/spark:3.5.0                      Up
xxx            dataforge-airflow                        Up
xxx            dataforge-dbt                            Up
xxx            dataforge-core                           Up
```

## Step 5: Initialize Airflow

```bash
# Initialize Airflow database
docker exec dataforge-airflow airflow db init

# Create admin user
docker exec dataforge-airflow airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@dataforge.io
```

## Step 6: Verify Setup

### Test Airflow
```bash
# Open browser
open http://localhost:8888

# Login: admin / admin
```

### Test Spark
```bash
# Check Spark UI
open http://localhost:8080

# Submit test job
docker exec dataforge-spark-master spark-submit \
  --class org.apache.spark.examples.SparkPi \
  /opt/spark-apps/examples/jars/spark-examples.jar 10
```

### Test MinIO
```bash
# Open MinIO console
open http://localhost:9001

# Login: minioadmin / minioadmin
# Create buckets: dataforge-bronze, dataforge-silver, dataforge-gold
```

### Test PostgreSQL
```bash
docker exec dataforge-postgres psql -U postgres -c "SELECT current_database();"
```

## Step 7: Run Example Pipeline

### Load Sample Data
```bash
# Create sample CSV in MinIO
docker exec dataforge-minio mc cp /tmp/sample_orders.csv \
  minio/dataforge-bronze/orders/

# Or use Python to create sample data
python3 -c "
import pandas as pd
df = pd.DataFrame({
    'order_id': ['ORD001', 'ORD002'],
    'customer_id': ['CUST001', 'CUST002'],
    'order_amount': [100.00, 250.50],
    'order_date': ['2024-01-01', '2024-01-02']
})
df.to_csv('/tmp/orders.csv', index=False)
print('Sample data created at /tmp/orders.csv')
" 
```

### Submit Spark Job
```bash
docker exec dataforge-spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages io.delta:delta-spark_2.12:3.0.0 \
  /opt/spark-apps/batch/batch_ingestion.py \
  /opt/configs/ecommerce_orders_bronze.yaml
```

### Run dbt Models
```bash
# Compile dbt models
docker exec dataforge-dbt dbt compile \
  --profiles-dir /opt/dbt \
  --project-dir /opt/dbt

# Run dbt tests
docker exec dataforge-dbt dbt test \
  --profiles-dir /opt/dbt \
  --project-dir /opt/dbt
```

## Step 8: Test Python Package

```bash
# Create test script
cat > test_dataforge.py << 'EOF'
from dataforge_core.config import ConfigurationManager
from dataforge_core.logging_config import setup_logging

# Setup logging
logger = setup_logging(name="test", level="INFO")

# Load config
config_manager = ConfigurationManager()
config = config_manager.load_config(environment="dev")

logger.info(f"Environment: {config.environment}")
logger.info(f"Storage Type: {config.cloud.storage_type}")
logger.info(f"Spark Master: {config.spark.master_url}")

print("✅ DataForge Core loaded successfully!")
EOF

# Run test
docker exec dataforge-core python test_dataforge.py
```

## Common Issues & Troubleshooting

### Issue: "Docker daemon is not running"
**Solution**: Start Docker Desktop application

### Issue: "Ports already in use"
**Solution**: Change ports in docker-compose.yml or stop conflicting services:
```bash
lsof -i :<port_number>
kill -9 <PID>
```

### Issue: "M1 Mac - Image not found"
**Solution**: All images are ARM64 compatible. If you see compatibility errors:
```bash
# Force platform selection in docker-compose.yml
platform: linux/arm64
```

### Issue: "Airflow connection errors"
**Solution**: Wait for all services to be healthy:
```bash
docker-compose ps
# All should show "(healthy)" in STATUS
```

### Issue: "Out of memory"
**Solution**: Increase Docker memory:
1. Open Docker Desktop
2. Preferences → Resources
3. Increase Memory to 12GB+
4. Restart Docker

### Issue: "PostgreSQL connection refused"
**Solution**: Wait for PostgreSQL to start and check logs:
```bash
docker logs dataforge-postgres
docker exec dataforge-postgres pg_isready
```

## Useful Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f dataforge-spark-master
docker-compose logs -f dataforge-airflow
```

### Enter Container Shell
```bash
docker exec -it dataforge-airflow bash
docker exec -it dataforge-spark-master bash
docker exec -it dataforge-postgres bash
```

### Stop/Restart Services
```bash
# Stop all
docker-compose stop

# Stop specific service
docker-compose stop dataforge-airflow

# Restart
docker-compose restart dataforge-spark-master
```

### Clean Up
```bash
# Stop and remove containers
docker-compose down

# Remove volumes (WARNING: Deletes data!)
docker-compose down -v

# Remove built images
docker-compose down -v --rmi all
```

## Development Workflow

### 1. Make Code Changes
```bash
# Edit Python files in dataforge_core/
vi dataforge_core/config.py
```

### 2. Test Locally
```bash
# Run unit tests
docker exec dataforge-core python -m pytest tests/ -v
```

### 3. Test in Container
```bash
# Rebuild image with changes
docker-compose build dataforge-core

# Restart service
docker-compose restart dataforge-core
```

### 4. Check Logs
```bash
docker-compose logs -f dataforge-core
```

## Performance Tips

1. **Reduce Spark Memory** for laptops:
   ```yaml
   # docker-compose.yml
   spark-worker-1:
     environment:
       SPARK_WORKER_MEMORY: 1G

## Next Steps

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
2. Explore example DAGs in `airflow_dags/`
3. Create your first pipeline config in `dataforge_core/pipelines/configs/`
4. Deploy to cloud following [DEPLOYMENT.md](DEPLOYMENT.md)

---

**Happy data engineering!** 🚀
