# DataForge - Example Exploration Notebook

This directory contains Jupyter notebooks for interactive exploration and development.

## Quick Start

1. Access Jupyter: `docker exec dataforge-jupyter jupyter notebook list`
2. Open notebook in browser
3. Import and explore:

```python
from dataforge.core import initialize_dataforge
from dataforge.pipelines.gold_pipeline import GoldPipeline

config, spark = initialize_dataforge()

# Read Gold layer
df = spark.read.format("delta").load(config.get('storage.gold_path'))
df.show()

# Example queries
df.groupBy("symbol").agg({"daily_return_pct": "avg"}).show()
```

## Available Notebooks

- `01_bronze_exploration.ipynb` - Explore raw Bronze data
- `02_silver_cleaning.ipynb` - See deduplication pipeline
- `03_gold_analytics.ipynb` - Calculate returns and moving averages
- `04_api_testing.ipynb` - Test API endpoints
