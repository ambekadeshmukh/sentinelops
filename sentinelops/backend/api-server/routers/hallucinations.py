# sentinelops/backend/api-server/routers/hallucinations.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging
import json

from ..services.hallucination_detector import HallucinationDetector
from ..services.database import get_connection
from ..services.storage import get_object_content

router = APIRouter(
    prefix="/v1/hallucinations",
    tags=["hallucinations"]
)

logger = logging.getLogger(__name__)

# Initialize hallucination detector service
hallucination_detector = HallucinationDetector()

# Data models
class HallucinationQuery(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    application: Optional[str] = None
    environment: Optional[str] = None
    confidence_level: Optional[str] = None  # 'high', 'medium', 'low', or 'any'
    limit: int = 100

class HallucinationAnalysisRequest(BaseModel):
    text: str
    context: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class HallucinationBatchAnalysisRequest(BaseModel):
    request_ids: List[str]
    include_content: bool = True

@router.post("/analyze")
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

@router.post("/analyze-batch")
async def analyze_batch(request: HallucinationBatchAnalysisRequest):
    """
    Analyze multiple requests for hallucinations by request ID.
    """
    try:
        records = []
        
        # Get database connection
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get the request details and storage object IDs
            placeholders = ",".join(["%s"] * len(request.request_ids))
            cursor.execute(
                f"""
                SELECT request_id, timestamp, provider, model, application, environment, 
                       storage_object_id
                FROM request_metrics
                WHERE request_id IN ({placeholders})
                """,
                request.request_ids
            )
            
            results = cursor.fetchall()
            
            # Process each request
            for row in results:
                # Skip if no storage object
                if not row['storage_object_id']:
                    continue
                    
                # Get content from storage
                try:
                    content = get_object_content(row['storage_object_id'])
                    data = json.loads(content)
                    
                    # Create record for analysis
                    record = {
                        "request_id": row['request_id'],
                        "timestamp": row['timestamp'].isoformat() if isinstance(row['timestamp'], datetime) else row['timestamp'],
                        "provider": row['provider'],
                        "model": row['model'],
                        "application": row['application'],
                        "environment": row['environment']
                    }
                    
                    # Add prompt and completion if available
                    if "prompt" in data:
                        record["prompt"] = data["prompt"]
                    if "completion" in data:
                        record["completion"] = data["completion"]
                        
                    # Only process if we have a completion
                    if "completion" in record:
                        records.append(record)
                except Exception as e:
                    logger.error(f"Error getting content for request {row['request_id']}: {str(e)}")
        
        # Analyze the records
        results = hallucination_detector.batch_analyze(records, include_completion=request.include_content)
        
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Error in batch analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze batch: {str(e)}"
        )

@router.post("/query")
async def query_hallucinations(query: HallucinationQuery):
    """
    Query detected hallucinations based on filters.
    """
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
            
        if query.confidence_level and query.confidence_level != 'any':
            conditions.append("confidence = %s")
            params.append(query.confidence_level)
            
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT * FROM hallucinations
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                params + [query.limit]
            )
            
            results = cursor.fetchall()
            
            # Convert to list of dicts and format timestamps
            hallucinations = []
            for row in results:
                record = dict(row)
                # Convert datetime objects to ISO format strings
                for key, value in record.items():
                    if isinstance(value, datetime):
                        record[key] = value.isoformat()
                hallucinations.append(record)
                
            return {"hallucinations": hallucinations, "count": len(hallucinations)}
    except Exception as e:
        logger.error(f"Failed to query hallucinations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query hallucinations: {str(e)}"
        )

@router.get("/summary")
async def get_hallucinations_summary(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    application: Optional[str] = None
):
    """
    Get summary statistics for hallucinations.
    """
    try:
        # Set default time range if not provided
        if not end_time:
            end_time = datetime.now()
        if not start_time:
            start_time = end_time - timedelta(days=7)
            
        # Build query conditions
        conditions = ["timestamp >= %s", "timestamp <= %s"]
        params = [start_time, end_time]
        
        if provider:
            conditions.append("provider = %s")
            params.append(provider)
            
        if model:
            conditions.append("model = %s")
            params.append(model)
            
        if application:
            conditions.append("application = %s")
            params.append(application)
            
        where_clause = " AND ".join(conditions)
        
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get total count
            cursor.execute(
                f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN hallucination_detected THEN 1 ELSE 0 END) as detected
                FROM hallucinations
                WHERE {where_clause}
                """,
                params
            )
            
            count_result = cursor.fetchone()
            total = count_result['total'] if count_result else 0
            detected = count_result['detected'] if count_result else 0
            
            # Get breakdown by confidence
            cursor.execute(
                f"""
                SELECT confidence, COUNT(*) as count
                FROM hallucinations
                WHERE {where_clause} AND hallucination_detected = TRUE
                GROUP BY confidence
                ORDER BY 
                    CASE 
                        WHEN confidence = 'high' THEN 1
                        WHEN confidence = 'medium' THEN 2
                        WHEN confidence = 'low' THEN 3
                        ELSE 4
                    END
                """,
                params
            )
            
            by_confidence = []
            for row in cursor.fetchall():
                by_confidence.append({
                    "confidence": row['confidence'],
                    "count": row['count']
                })
                
            # Get breakdown by model
            cursor.execute(
                f"""
                SELECT provider, model, COUNT(*) as count
                FROM hallucinations
                WHERE {where_clause} AND hallucination_detected = TRUE
                GROUP BY provider, model
                ORDER BY count DESC
                LIMIT 10
                """,
                params
            )
            
            by_model = []
            for row in cursor.fetchall():
                by_model.append({
                    "provider": row['provider'],
                    "model": row['model'],
                    "count": row['count']
                })
                
            # Get breakdown by reason type
            cursor.execute(
                f"""
                SELECT reason_type, COUNT(*) as count
                FROM hallucinations, 
                     jsonb_array_elements(reasons) as reason,
                     jsonb_extract_path(reason, 'type') as reason_type
                WHERE {where_clause} AND hallucination_detected = TRUE
                GROUP BY reason_type
                ORDER BY count DESC
                LIMIT 10
                """,
                params
            )
            
            by_reason = []
            for row in cursor.fetchall():
                by_reason.append({
                    "reason": row['reason_type'].replace('"', ''),  # Remove JSON quotes
                    "count": row['count']
                })
                
            # Calculate detection rate
            detection_rate = 0
            if total > 0:
                detection_rate = detected / total
                
            return {
                "total_analyzed": total,
                "hallucinations_detected": detected,
                "detection_rate": detection_rate,
                "by_confidence": by_confidence,
                "by_model": by_model,
                "by_reason": by_reason,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
    except Exception as e:
        logger.error(f"Failed to get hallucinations summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get hallucinations summary: {str(e)}"
        )