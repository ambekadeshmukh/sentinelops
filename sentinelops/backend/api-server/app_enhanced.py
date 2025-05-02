# sentinelops/backend/api-server/app_enhanced.py
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, validator
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx
from minio import Minio
import pandas as pd
import io

# Import our services and middleware
from services.database import get_connection
from services.storage import get_object_content
from services.hallucination_detector import HallucinationDetector
from services.aggregation import AggregationService
from middleware.auth import AuthService, RateLimiter, rate_limit_middleware, require_permissions

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

# Create FastAPI app
app = FastAPI(
    title="SentinelOps API",
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

# Initialize services
db_connection = psycopg2.connect(
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    dbname=POSTGRES_DB
)

# Set up services
auth_service = AuthService(db_connection)
rate_limiter = RateLimiter()
hallucination_detector = HallucinationDetector()
aggregation_service = AggregationService(db_connection)

# Add rate limiting middleware
@app.middleware("http")
async def add_rate_limiting(request: Request, call_next):
    return await rate_limit_middleware(request, call_next)

# Add service state to app
app.state.auth_service = auth_service
app.state.db_connection = db_connection

# MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Set to True if using HTTPS
)

# Data models
class MetricsQuery(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    application: Optional[str] = None
    environment: Optional[str] = None
    limit: int = 100
    
    @validator('start_time', 'end_time', pre=True)
    def parse_datetime(cls, value):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value
    
class AnomalyQuery(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    anomaly_type: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    application: Optional[str] = None
    limit: int = 100
    
    @validator('start_time', 'end_time', pre=True)
    def parse_datetime(cls, value):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value

class RequestDetails(BaseModel):
    request_id: str

class TimeRange(BaseModel):
    start_time: datetime
    end_time: datetime = Field(default_factory=lambda: datetime.now())
    
    @validator('start_time', 'end_time', pre=True)
    def parse_datetime(cls, value):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value
    
class AggregateBy(BaseModel):
    group_by: List[str] = ["provider", "model"]
    metrics: List[str] = ["avg_inference_time", "total_tokens", "total_cost", "error_rate"]

class ModelComparisonRequest(BaseModel):
    models: List[Dict[str, str]]
    start_time: datetime
    end_time: datetime = Field(default_factory=lambda: datetime.now())
    metrics: Optional[List[str]] = None
    
    @validator('start_time', 'end_time', pre=True)
    def parse_datetime(cls, value):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value

class HallucinationAnalysisRequest(BaseModel):
    text: str
    context: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# API routes
@app.get("/")
async def root():
    return {"message": "SentinelOps API", "version": "0.1.0"}

@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        conn = get_connection()
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

@app.post("/v1/metrics", dependencies=[Depends(require_permissions(["write:metrics"]))])
async def submit_metrics(metrics: Dict[str, Any]):
    """Endpoint for submitting metrics directly."""
    try:
        cursor = db_connection.cursor()
        columns = list(metrics.keys())
        values = [metrics[col] for col in columns]
        placeholders = ["%s"] * len(columns)
        
        query = f"""
        INSERT INTO request_metrics ({', '.join(columns)})
        VALUES ({', '.join(placeholders)})
        """
        
        cursor.execute(query, values)
        db_connection.commit()
        
        return {"status": "success", "message": "Metrics recorded successfully"}
    except Exception as e:
        logger.error(f"Failed to record metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record metrics: {str(e)}"
        )

@app.post("/v1/metrics/query", dependencies=[Depends(require_permissions(["read:metrics"]))])
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
        
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)
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

@app.post("/v1/anomalies/query", dependencies=[Depends(require_permissions(["read:anomalies"]))])
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
        
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)
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

@app.post("/v1/requests/details", dependencies=[Depends(require_permissions(["read:requests"]))])
async def get_request_details(request_details: RequestDetails):
    """Get detailed information about a specific request."""
    try:
        # Query database for request metrics
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)
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
                content = get_object_content(storage_object_id)
                data = json.loads(content)
                
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

@app.post("/v1/metrics/aggregated", dependencies=[Depends(require_permissions(["read:metrics"]))])
async def get_aggregated_metrics(time_range: TimeRange, aggregate_by: AggregateBy):
    """Get aggregated metrics for the specified time range."""
    try:
        filters = {}
        return aggregation_service.get_metrics_summary(
            time_range.start_time,
            time_range.end_time,
            filters,
            aggregate_by.group_by
        )
    except Exception as e:
        logger.error(f"Failed to get aggregated metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get aggregated metrics: {str(e)}"
        )

@app.post("/v1/metrics/timeseries", dependencies=[Depends(require_permissions(["read:metrics"]))])
async def get_timeseries_metrics(
    time_range: TimeRange,
    interval: str = "auto",
    filters: Optional[Dict[str, Any]] = None,
    metrics: Optional[List[str]] = None
):
    """Get time series metrics for visualization."""
    try:
        return aggregation_service.get_time_series_metrics(
            time_range.start_time,
            time_range.end_time,
            interval,
            filters,
            metrics
        )
    except Exception as e:
        logger.error(f"Failed to get timeseries metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get timeseries metrics: {str(e)}"
        )

@app.post("/v1/metrics/model-comparison", dependencies=[Depends(require_permissions(["read:metrics"]))])
async def compare_models(request: ModelComparisonRequest):
    """Compare metrics between different models."""
    try:
        return aggregation_service.get_model_comparison(
            request.models,
            request.start_time,
            request.end_time,
            request.metrics
        )
    except Exception as e:
        logger.error(f"Failed to compare models: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare models: {str(e)}"
        )

@app.get("/v1/models", dependencies=[Depends(require_permissions(["read:metrics"]))])
async def get_models():
    """Get list of all models being monitored."""
    try:
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)
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

@app.get("/v1/applications", dependencies=[Depends(require_permissions(["read:metrics"]))])
async def get_applications():
    """Get list of all applications being monitored."""
    try:
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)
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

@app.get("/v1/dashboard/summary", dependencies=[Depends(require_permissions(["read:metrics"]))])
async def get_dashboard_summary():
    """Get summary metrics for dashboard."""
    try:
        # Get metrics for the last 24 hours
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)
        
        # Get summarized metrics
        metrics_summary = aggregation_service.get_metrics_summary(
            start_time, 
            end_time,
            group_by=["provider", "model"]
        )
        
        # Get anomaly summary
        anomaly_summary = aggregation_service.get_anomaly_summary(
            start_time,
            end_time
        )
        
        # Get hallucination stats if available
        try:
            hallucination_stats = aggregation_service.get_hallucination_stats(
                start_time,
                end_time
            )
        except Exception:
            hallucination_stats = {"detection_rate": 0, "total_analyzed": 0}
        
        # Prepare dashboard summary
        summary = {
            "total_requests": metrics_summary.get("total_requests", 0),
            "total_cost": metrics_summary.get("total_cost", 0),
            "avg_inference_time": metrics_summary.get("avg_inference_time", 0),
            "success_rate": metrics_summary.get("success_rate", 1.0),
            "error_rate": 1.0 - metrics_summary.get("success_rate", 1.0),
            "total_tokens": metrics_summary.get("total_tokens", 0),
            "total_anomalies": anomaly_summary.get("total_anomalies", 0),
            "hallucination_rate": hallucination_stats.get("detection_rate", 0),
            "top_models": metrics_summary.get("grouped_metrics", [])[:5],
            "recent_anomalies": anomaly_summary.get("by_type", [])[:5],
            "time_period": "last_24h"
        }
        
        return summary
    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard summary: {str(e)}"
        )

@app.post("/v1/hallucinations/analyze", dependencies=[Depends(require_permissions(["read:requests"]))])
async def analyze_hallucination(request: HallucinationAnalysisRequest):
    """
    Analyze text for potential hallucinations.
    """
    try:
        result = hallucination_detector.detect_hallucinations(
            completion=request.text,
            prompt=request.context,
            metadata=request.metadata
        )
        
        return result
    except Exception as e:
        logger.error(f"Error analyzing for hallucinations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze text: {str(e)}"
        )

@app.post("/v1/hallucinations/stats", dependencies=[Depends(require_permissions(["read:metrics"]))])
async def get_hallucination_statistics(time_range: TimeRange, filters: Optional[Dict[str, Any]] = None):
    """
    Get hallucination statistics for the given time range.
    """
    try:
        return aggregation_service.get_hallucination_stats(
            time_range.start_time,
            time_range.end_time,
            filters
        )
    except Exception as e:
        logger.error(f"Failed to get hallucination statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get hallucination statistics: {str(e)}"
        )

@app.get("/v1/cost/optimization", dependencies=[Depends(require_permissions(["read:metrics"]))])
async def get_cost_optimization():
    """
    Get cost optimization insights.
    """
    try:
        # This endpoint would integrate with the CostOptimizer
        # For now, we'll return a placeholder response
        return {
            "status": "not_implemented",
            "message": "Cost optimization insights coming soon"
        }
    except Exception as e:
        logger.error(f"Failed to get cost optimization insights: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cost optimization insights: {str(e)}"
        )

@app.get("/v1/anomalies/summary", dependencies=[Depends(require_permissions(["read:anomalies"]))])
async def get_anomalies_summary(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    application: Optional[str] = Query(None)
):
    """
    Get summary statistics for anomalies.
    """
    try:
        # Set default time range if not provided
        if not end_time:
            end_time = datetime.now()
        if not start_time:
            start_time = end_time - timedelta(days=7)
            
        # Prepare filters
        filters = {}
        if provider:
            filters["provider"] = provider
        if model:
            filters["model"] = model
        if application:
            filters["application"] = application
            
        return aggregation_service.get_anomaly_summary(
            start_time,
            end_time,
            filters
        )
    except Exception as e:
        logger.error(f"Failed to get anomalies summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get anomalies summary: {str(e)}"
        )

# Server startup
if __name__ == "__main__":
    import uvicorn
    
    # Initialize database tables if they don't exist
    try:
        conn = db_connection
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
            
            # Create hallucinations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hallucinations (
                    id SERIAL PRIMARY KEY,
                    hallucination_id VARCHAR(255) NOT NULL,
                    request_id VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    provider VARCHAR(255) NOT NULL,
                    model VARCHAR(255) NOT NULL,
                    application VARCHAR(255) NOT NULL,
                    environment VARCHAR(255) NOT NULL,
                    hallucination_detected BOOLEAN NOT NULL,
                    confidence VARCHAR(255),
                    score FLOAT,
                    reasons JSONB,
                    component_scores JSONB
                );
                CREATE INDEX IF NOT EXISTS hallucinations_request_id_idx ON hallucinations(request_id);
                CREATE INDEX IF NOT EXISTS hallucinations_timestamp_idx ON hallucinations(timestamp);
            """)
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    email VARCHAR(255),
                    password_hash VARCHAR(255),
                    tier VARCHAR(50) DEFAULT 'free',
                    is_active BOOLEAN DEFAULT TRUE,
                    rate_limit INTEGER DEFAULT 100,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            
            # Create API keys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    api_key VARCHAR(255) NOT NULL UNIQUE,
                    name VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_used TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS api_key_idx ON api_keys(api_key);
            """)
            
            # Insert default user and API key if none exists
            cursor.execute("""
                INSERT INTO users (username, email, tier, is_active)
                SELECT 'default', 'default@example.com', 'free', TRUE
                WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'default')
                RETURNING id
            """)
            
            result = cursor.fetchone()
            if result:
                user_id = result[0]
                cursor.execute("""
                    INSERT INTO api_keys (user_id, api_key, name, is_active)
                    VALUES (%s, 'test-api-key', 'Default API Key', TRUE)
                    ON CONFLICT (api_key) DO NOTHING
                """, (user_id,))
            
            conn.commit()
            logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}", exc_info=True)
    
    # Start the server
    logger.info(f"Starting API server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)