"""
DataForge FastAPI Service
Exposes endpoints for stock analytics and portfolio metrics.
- Reads from Gold/Silver layers
- Real-time query execution
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import traceback
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, desc
import duckdb

from core import initialize_dataforge, logger, StorageHelper

# Initialize FastAPI
app = FastAPI(title="DataForge API", version="1.0.0")

# Initialize Spark and config at startup
config = None
spark = None
storage = None


@app.on_event("startup")
async def startup_event():
    global config, spark, storage
    config, spark = initialize_dataforge()
    storage = StorageHelper(config)
    logger.info("DataForge API started")


@app.on_event("shutdown")
async def shutdown_event():
    if spark:
        spark.stop()
    logger.info("DataForge API stopped")


# ============================================================================
# Health & Status Endpoints
# ============================================================================
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/config")
async def get_config():
    """Get current platform configuration (non-sensitive)."""
    return {
        "environment": config.get('environment'),
        "version": config.get('version'),
        "storage_type": config.get('storage.type'),
        "spark_master": config.get('spark.master'),
    }


# ============================================================================
# Stock History Endpoints
# ============================================================================
@app.get("/stocks/history/{symbol}")
async def get_stock_history(
    symbol: str,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get historical OHLC data for a stock.
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE.NS')
        start_date: Start date (defaults to 1 year ago)
        end_date: End date (defaults to today)
        limit: Max records to return
    """
    try:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        # Read from Gold layer
        gold_path = storage.get_path('gold')
        df = spark.read.format("delta").load(gold_path)
        
        # Filter
        df_result = (
            df
            .filter((col("symbol") == symbol) & (col("date") >= start_date) & (col("date") <= end_date))
            .orderBy(desc("date"))
            .limit(limit)
        )
        
        records = df_result.toPandas().to_dict('records')
        
        return {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "records": records,
            "count": len(records)
        }
    
    except Exception as e:
        logger.error(f"Error fetching history", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Performance Endpoints
# ============================================================================
@app.get("/stocks/performance")
async def get_stock_performance(
    period_days: int = Query(30, ge=1, le=365),
    top_n: int = Query(10, ge=1, le=100)
):
    """
    Get top performing stocks over a period.
    
    Args:
        period_days: Number of days to look back
        top_n: Top N stocks to return
    """
    try:
        start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
        
        gold_path = storage.get_path('gold')
        df = spark.read.format("delta").load(gold_path)
        
        # Calculate cumulative returns
        df_perf = (
            df
            .filter(col("date") >= start_date)
            .groupBy("symbol")
            .agg(
                (((col("daily_close").last() - col("daily_close").first()) / col("daily_close").first()) * 100)
                .alias("return_pct"),
                col("daily_volume").avg().alias("avg_volume"),
                col("volatility_30d").avg().alias("avg_volatility")
            )
            .orderBy(desc("return_pct"))
            .limit(top_n)
        )
        
        records = df_perf.toPandas().to_dict('records')
        
        return {
            "period_days": period_days,
            "as_of_date": datetime.now().strftime("%Y-%m-%d"),
            "top_performers": records,
            "count": len(records)
        }
    
    except Exception as e:
        logger.error(f"Error fetching performance", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/top-gainers")
async def get_top_gainers(limit: int = Query(10, ge=1, le=50)):
    """Get top gainers from the last trading day."""
    try:
        gold_path = storage.get_path('gold')
        df = spark.read.format("delta").load(gold_path)
        
        # Get latest date
        latest_date = df.agg({"date": "max"}).collect()[0][0]
        
        df_gainers = (
            df
            .filter(col("date") == latest_date)
            .orderBy(desc("daily_return_pct"))
            .limit(limit)
            .select("symbol", "daily_close", "daily_return_pct", "ma_50_day", "ma_200_day")
        )
        
        records = df_gainers.toPandas().to_dict('records')
        
        return {
            "as_of_date": str(latest_date),
            "gainers": records,
            "count": len(records)
        }
    
    except Exception as e:
        logger.error(f"Error fetching gainers", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Advanced Query Endpoints
# ============================================================================
@app.post("/query/sql")
async def execute_sql_query(query: str):
    """
    Execute SQL query against Gold layer (dangerous, use with caution).
    
    Args:
        query: SQL query string
    """
    try:
        if len(query) > 10000:
            raise ValueError("Query too large")
        
        # Validate query doesn't modify data
        disallowed = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]
        if any(keyword in query.upper() for keyword in disallowed):
            raise ValueError("Modification operations not allowed")
        
        result = spark.sql(query)
        records = result.toPandas().to_dict('records')
        
        return {
            "query": query,
            "results": records,
            "count": len(records)
        }
    
    except Exception as e:
        logger.error(f"Query execution failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Error Handlers
# ============================================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.get("/")
async def root():
    return {
        "message": "Welcome to DataForge API",
        "docs": "/docs",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
