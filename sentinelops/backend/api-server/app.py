# api-server/app.py
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx
from minio import Minio
import pandas as pd
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api-server")

# Configuration from environment variables
PORT = int(os.environ.get("PORT", "8000"))
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "llmmonitor")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "llmmonitor")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "llmmonitor")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "llm-requests")
API_KEY_SECRET = os.environ.get("API_KEY_SECRET", "test-api-key")

# Create FastAPI app
app = FastAPI(
    title="LLM Monitoring API",
    description="API for monitoring and observability of LLM applications",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key security
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key

# Database connection pool
class Database:
    def __init__(self):
        self.conn = None
        
    def get_connection(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB
            )
        return self.conn
        
    def get_cursor(self):
        return self.get_connection().cursor(cursor_factory=RealDictCursor)

db = Database()

# MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Set to True if using HTTPS
)

# Prometheus client
async def query_prometheus(query: str) -> Dict:
    """Execute a PromQL query against Prometheus."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query}
        )
        if response.status_code != 200:
            logger.error(f"Prometheus query failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to query metrics from Prometheus"
            )
        return response.json()

# Data models
class MetricsQuery(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    application: Optional[str] = None
    environment: Optional[str] = None
    limit: int = 100
    
class AnomalyQuery(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    anomaly_type: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    application: Optional[str] = None
    limit: int = 100

class RequestDetails(BaseModel):
    request_id: str

class TimeRange(BaseModel):
    start_time: datetime
    end_time: datetime = Field(default_factory=lambda: datetime.now())
    
class AggregateBy(BaseModel):
    group_by: List[str] = ["provider", "model"]
    metrics: List[str] = ["avg_inference_time", "total_tokens", "total_cost", "error_rate"]
    
# Routes
@app.get("/")
async def root():
    return {"message": "LLM Monitoring API"}

@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        conn = db.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            
        # Check Prometheus connection
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{PROMETHEUS_URL}/-/healthy")
            if response.status_code != 200:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"status": "unhealthy", "message": "Prometheus is not available"}
                )
                
        # Check MinIO connection
        if not minio_client.bucket_exists(MINIO_BUCKET):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "message": "MinIO bucket not available"}
            )
            
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "message": str(e)}
        )

@app.post("/v1/metrics", dependencies=[Depends(verify_api_key)])
async def submit_metrics(metrics: Dict[str, Any]):
    """Endpoint for submitting metrics directly."""
    try:
        cursor = db.get_cursor()
        columns = list(metrics.keys())
        values = [metrics[col] for col in columns]
        placeholders = ["%s"] * len(columns)
        
        query = f"""
        INSERT INTO request_metrics ({', '.join(columns)})
        VALUES ({', '.join(placeholders)})
        """
        
        cursor.execute(query, values)
        db.get_connection().commit()
        
        return {"status": "success", "message": "Metrics recorded successfully"}
    except Exception as e:
        logger.error(f"Failed to record metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record metrics: {str(e)}"
        )

@app.post("/v1/metrics/query", dependencies=[Depends(verify_api_key)])
async def query_metrics(query: MetricsQuery):
    """Query metrics based on filters."""
    try:
        conditions = []
        params = []
        
        if query.start_time:
            conditions.append("timestamp >= %s")
            params.append(query.start_time)
            
        if query.end_time:
            conditions.append("timestamp <= %s")
            params.append(query.end_time)
            
        if query.provider:
            conditions.append("provider = %s")
            params.append(query.provider)
            
        if query.model:
            conditions.append("model = %s")
            params.append(query.model)
            
        if query.application:
            conditions.append("application = %s")
            params.append(query.application)
            
        if query.environment:
            conditions.append("environment = %s")
            params.append(query.environment)
            
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        cursor = db.get_cursor()
        cursor.execute(
            f"""
            SELECT * FROM request_metrics
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            params + [query.limit]
        )
        
        results = cursor.fetchall()
        
        # Convert to list of dicts and format timestamps
        metrics = []
        for row in results:
            record = dict(row)
            # Convert datetime objects to ISO format strings
            for key, value in record.items():
                if isinstance(value, datetime):
                    record[key] = value.isoformat()
            metrics.append(record)
            
        return {"metrics": metrics, "count": len(metrics)}
    except Exception as e:
        logger.error(f"Failed to query metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query metrics: {str(e)}"
        )

@app.post("/v1/anomalies/query", dependencies=[Depends(verify_api_key)])
async def query_anomalies(query: AnomalyQuery):
    """Query detected anomalies based on filters."""
    try:
        conditions = []
        params = []
        
        if query.start_time:
            conditions.append("timestamp >= %s")
            params.append(query.start_time)
            
        if query.end_time:
            conditions.append("timestamp <= %s")
            params.append(query.end_time)
            
        if query.anomaly_type:
            conditions.append("type = %s")
            params.append(query.anomaly_type)
            
        if query.provider:
            conditions.append("provider = %s")
            params.append(query.provider)
            
        if query.model:
            conditions.append("model = %s")
            params.append(query.model)
            
        if query.application:
            conditions.append("application = %s")
            params.append(query.application)
            
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        cursor = db.get_cursor()
        cursor.execute(
            f"""
            SELECT * FROM anomalies
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            params + [query.limit]
        )
        
        results = cursor.fetchall()
        
        # Convert to list of dicts and format timestamps
        anomalies = []
        for row in results:
            record = dict(row)
            # Convert datetime objects to ISO format strings
            for key, value in record.items():
                if isinstance(value, datetime):
                    record[key] = value.isoformat()
            anomalies.append(record)
            
        return {"anomalies": anomalies, "count": len(anomalies)}
    except Exception as e:
        logger.error(f"Failed to query anomalies: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query anomalies: {str(e)}"
        )

@app.post("/v1/requests/details", dependencies=[Depends(verify_api_key)])
async def get_request_details(request_details: RequestDetails):
    """Get detailed information about a specific request."""
    try:
        # Query database for request metrics
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT * FROM request_metrics 
            WHERE request_id = %s
            """,
            (request_details.request_id,)
        )
        
        metrics = cursor.fetchone()
        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Request {request_details.request_id} not found"
            )
            
        # Format metrics
        result = dict(metrics)
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
                
        # Check if we have the full request/response stored
        storage_object_id = result.get("storage_object_id")
        if storage_object_id:
            try:
                # Get object from MinIO
                response = minio_client.get_object(
                    bucket_name=MINIO_BUCKET,
                    object_name=storage_object_id
                )
                data = json.loads(response.read().decode('utf-8'))
                
                # Add prompt and completion if available
                if "prompt" in data:
                    result["prompt"] = data["prompt"]
                if "completion" in data:
                    result["completion"] = data["completion"]
            except Exception as e:
                logger.error(f"Failed to retrieve request/response data: {str(e)}", exc_info=True)
                result["storage_error"] = str(e)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get request details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get request details: {str(e)}"
        )

@app.post("/v1/metrics/aggregated", dependencies=[Depends(verify_api_key)])
async def get_aggregated_metrics(time_range: TimeRange, aggregate_by: AggregateBy):
    """Get aggregated metrics for the specified time range."""
    try:
        # Validate the aggregation fields
        valid_group_by = ["provider", "model", "application", "environment"]
        valid_metrics = ["avg_inference_time", "total_tokens", "total_cost", "error_rate", "request_count"]
        
        for field in aggregate_by.group_by:
            if field not in valid_group_by:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid group by field: {field}. Valid fields are {valid_group_by}"
                )
                
        for metric in aggregate_by.metrics:
            if metric not in valid_metrics:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid metric: {metric}. Valid metrics are {valid_metrics}"
                )
        
        # Build the query
        group_by_clause = ", ".join(aggregate_by.group_by)
        select_parts = [*aggregate_by.group_by]
        
        if "avg_inference_time" in aggregate_by.metrics:
            select_parts.append("AVG(inference_time) as avg_inference_time")
            
        if "total_tokens" in aggregate_by.metrics:
            select_parts.append("SUM(COALESCE(total_tokens, 0)) as total_tokens")
            
        if "total_cost" in aggregate_by.metrics:
            select_parts.append("SUM(COALESCE(estimated_cost, 0)) as total_cost")
            
        if "error_rate" in aggregate_by.metrics:
            select_parts.append("(COUNT(*) - SUM(CASE WHEN success THEN 1 ELSE 0 END)) / COUNT(*)::float as error_rate")
            
        if "request_count" in aggregate_by.metrics:
            select_parts.append("COUNT(*) as request_count")
            
        select_clause = ", ".join(select_parts)
        
        # Execute query
        cursor = db.get_cursor()
        cursor.execute(
            f"""
            SELECT {select_clause}
            FROM request_metrics
            WHERE timestamp >= %s AND timestamp <= %s
            GROUP BY {group_by_clause}
            ORDER BY {group_by_clause}
            """,
            (time_range.start_time, time_range.end_time)
        )
        
        results = cursor.fetchall()
        
        # Convert to list of dicts
        metrics = [dict(row) for row in results]
            
        return {"metrics": metrics, "count": len(metrics)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get aggregated metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get aggregated metrics: {str(e)}"
        )

@app.post("/v1/metrics/timeseries", dependencies=[Depends(verify_api_key)])
async def get_timeseries_metrics(time_range: TimeRange):
    """Get time series metrics for the specified time range."""
    try:
        # Calculate the appropriate interval based on the time range
        time_diff = time_range.end_time - time_range.start_time
        if time_diff <= timedelta(hours=1):
            interval = "1 minute"
            format_string = "YYYY-MM-DD HH24:MI:00"
        elif time_diff <= timedelta(days=1):
            interval = "15 minutes"
            format_string = "YYYY-MM-DD HH24:MI:00"
        elif time_diff <= timedelta(days=7):
            interval = "1 hour"
            format_string = "YYYY-MM-DD HH24:00:00"
        elif time_diff <= timedelta(days=30):
            interval = "1 day"
            format_string = "YYYY-MM-DD"
        else:
            interval = "1 week"
            format_string = "YYYY-WW"
            
        # Execute query
        cursor = db.get_cursor()
        cursor.execute(
            f"""
            WITH time_buckets AS (
                SELECT 
                    TO_CHAR(
                        DATE_TRUNC('{interval}', timestamp),
                        '{format_string}'
                    ) as time_bucket,
                    AVG(inference_time) as avg_inference_time,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN success THEN 0 ELSE 1 END) as error_count,
                    SUM(COALESCE(total_tokens, 0)) as total_tokens,
                    SUM(COALESCE(estimated_cost, 0)) as total_cost
                FROM request_metrics
                WHERE timestamp >= %s AND timestamp <= %s
                GROUP BY time_bucket
                ORDER BY time_bucket
            )
            SELECT * FROM time_buckets
            """,
            (time_range.start_time, time_range.end_time)
        )
        
        results = cursor.fetchall()
        
        # Convert to list of dicts
        timeseries = [dict(row) for row in results]
        
        # Calculate error rate
        for record in timeseries:
            if record["request_count"] > 0:
                record["error_rate"] = record["error_count"] / record["request_count"]
            else:
                record["error_rate"] = 0
                
        return {"timeseries": timeseries, "count": len(timeseries)}
    except Exception as e:
        logger.error(f"Failed to get timeseries metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get timeseries metrics: {str(e)}"
        )

@app.get("/v1/models", dependencies=[Depends(verify_api_key)])
async def get_models():
    """Get list of all models being monitored."""
    try:
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT DISTINCT provider, model
            FROM request_metrics
            ORDER BY provider, model
            """
        )
        
        results = cursor.fetchall()
        
        # Convert to list of dicts
        models = [dict(row) for row in results]
        
        return {"models": models, "count": len(models)}
    except Exception as e:
        logger.error(f"Failed to get models: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get models: {str(e)}"
        )

@app.get("/v1/applications", dependencies=[Depends(verify_api_key)])
async def get_applications():
    """Get list of all applications being monitored."""
    try:
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT DISTINCT application, environment
            FROM request_metrics
            ORDER BY application, environment
            """
        )
        
        results = cursor.fetchall()
        
        # Convert to list of dicts
        applications = [dict(row) for row in results]
        
        return {"applications": applications, "count": len(applications)}
    except Exception as e:
        logger.error(f"Failed to get applications: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get applications: {str(e)}"
        )

@app.get("/v1/dashboard/summary", dependencies=[Depends(verify_api_key)])
async def get_dashboard_summary():
    """Get summary metrics for dashboard."""
    try:
        # Get metrics for the last 24 hours
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)
        
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total_requests,
                AVG(inference_time) as avg_inference_time,
                MAX(inference_time) as max_inference_time,
                SUM(CASE WHEN success THEN 0 ELSE 1 END) as error_count,
                SUM(COALESCE(total_tokens, 0)) as total_tokens,
                SUM(COALESCE(estimated_cost, 0)) as total_cost
            FROM request_metrics
            WHERE timestamp >= %s AND timestamp <= %s
            """,
            (start_time, end_time)
        )
        
        result = cursor.fetchone()
        if not result:
            return {
                "total_requests": 0,
                "avg_inference_time": 0,
                "max_inference_time": 0,
                "error_rate": 0,
                "total_tokens": 0,
                "total_cost": 0,
                "time_period": "last_24h"
            }
            
        summary = dict(result)
        
        # Calculate error rate
        if summary["total_requests"] > 0:
            summary["error_rate"] = summary["error_count"] / summary["total_requests"]
        else:
            summary["error_rate"] = 0
            
        # Add time period
        summary["time_period"] = "last_24h"
        
        # Get counts by model
        cursor.execute(
            """
            SELECT 
                provider,
                model,
                COUNT(*) as request_count
            FROM request_metrics
            WHERE timestamp >= %s AND timestamp <= %s
            GROUP BY provider, model
            ORDER BY request_count DESC
            LIMIT 5
            """,
            (start_time, end_time)
        )
        
        model_results = cursor.fetchall()
        summary["top_models"] = [dict(row) for row in model_results]
        
        # Get recent anomalies
        cursor.execute(
            """
            SELECT 
                anomaly_id,
                timestamp,
                type,
                provider,
                model,
                application
            FROM anomalies
            WHERE timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp DESC
            LIMIT 5
            """
        )
        
        anomaly_results = cursor.fetchall()
        anomalies = []
        for row in anomaly_results:
            record = dict(row)
            for key, value in record.items():
                if isinstance(value, datetime):
                    record[key] = value.isoformat()
            anomalies.append(record)
            
        summary["recent_anomalies"] = anomalies
        
        return summary
    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard summary: {str(e)}"
        )

# Server startup
if __name__ == "__main__":
    import uvicorn
    
    # Initialize database tables if they don't exist
    try:
        conn = db.get_connection()
        with conn.cursor() as cursor:
            # Create request_metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS request_metrics (
                    id SERIAL PRIMARY KEY,
                    request_id VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    provider VARCHAR(255) NOT NULL,
                    model VARCHAR(255) NOT NULL,
                    application VARCHAR(255) NOT NULL,
                    environment VARCHAR(255) NOT NULL,
                    inference_time FLOAT NOT NULL,
                    success BOOLEAN NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    estimated_cost FLOAT,
                    memory_used FLOAT,
                    error TEXT,
                    storage_object_id VARCHAR(255)
                );
                CREATE INDEX IF NOT EXISTS request_metrics_request_id_idx ON request_metrics(request_id);
                CREATE INDEX IF NOT EXISTS request_metrics_timestamp_idx ON request_metrics(timestamp);
                CREATE INDEX IF NOT EXISTS request_metrics_model_idx ON request_metrics(provider, model);
                CREATE INDEX IF NOT EXISTS request_metrics_app_idx ON request_metrics(application, environment);
            """)
            
            # Create anomalies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS anomalies (
                    id SERIAL PRIMARY KEY,
                    anomaly_id VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    type VARCHAR(255) NOT NULL,
                    request_id VARCHAR(255) NOT NULL,
                    provider VARCHAR(255) NOT NULL,
                    model VARCHAR(255) NOT NULL,
                    application VARCHAR(255) NOT NULL,
                    details JSONB
                );
                CREATE INDEX IF NOT EXISTS anomalies_anomaly_id_idx ON anomalies(anomaly_id);
                CREATE INDEX IF NOT EXISTS anomalies_timestamp_idx ON anomalies(timestamp);
                CREATE INDEX IF NOT EXISTS anomalies_type_idx ON anomalies(type);
            """)
            
            conn.commit()
            logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}", exc_info=True)
    
    # Start the server
    logger.info(f"Starting API server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)