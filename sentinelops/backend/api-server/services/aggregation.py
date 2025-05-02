# sentinelops/backend/api-server/services/aggregation.py
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import json

logger = logging.getLogger(__name__)

class AggregationService:
    """Service for efficient data aggregation and querying."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        
        # Caching structures
        self.cached_aggregations = {}
        self.cache_expiry = {}
        self.cache_timeout = 300  # 5 minutes
    
    def get_metrics_summary(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: Dict[str, Any] = None,
        group_by: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get summary of metrics with efficient aggregation.
        
        Args:
            start_time: Start time for query
            end_time: End time for query
            filters: Optional filters to apply
            group_by: Optional fields to group by
            
        Returns:
            Dictionary of aggregated metrics
        """
        # Generate cache key
        cache_key = f"metrics_summary:{start_time}:{end_time}:{json.dumps(filters)}:{json.dumps(group_by)}"
        
        # Check cache
        if cache_key in self.cached_aggregations and self.cache_expiry.get(cache_key, 0) > datetime.now().timestamp():
            return self.cached_aggregations[cache_key]
        
        # Determine query parameters
        params = [start_time, end_time]
        where_clauses = ["timestamp >= %s", "timestamp <= %s"]
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if field in ["provider", "model", "application", "environment", "success"]:
                    where_clauses.append(f"{field} = %s")
                    params.append(value)
        
        # Determine grouping
        group_fields = group_by or ["provider", "model"]
        valid_group_fields = [f for f in group_fields if f in ["provider", "model", "application", "environment"]]
        
        # Fall back to default if no valid fields
        if not valid_group_fields:
            valid_group_fields = ["provider", "model"]
        
        group_clause = ", ".join(valid_group_fields)
        
        # Construct and execute query
        cursor = self.db.cursor()
        query = f"""
            SELECT 
                {group_clause},
                COUNT(*) as request_count,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count,
                AVG(inference_time) as avg_inference_time,
                MAX(inference_time) as max_inference_time,
                SUM(COALESCE(prompt_tokens, 0)) as prompt_tokens,
                SUM(COALESCE(completion_tokens, 0)) as completion_tokens,
                SUM(COALESCE(total_tokens, 0)) as total_tokens,
                SUM(COALESCE(estimated_cost, 0)) as total_cost
            FROM request_metrics
            WHERE {" AND ".join(where_clauses)}
            GROUP BY {group_clause}
            ORDER BY request_count DESC
        """
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
# Process results
        summary = {
            "total_requests": 0,
            "total_cost": 0,
            "total_tokens": 0,
            "success_rate": 0,
            "avg_inference_time": 0,
            "grouped_metrics": []
        }
        
        for row in results:
            record = dict(row)
            
            # Add to totals
            summary["total_requests"] += record["request_count"]
            summary["total_cost"] += record["total_cost"] or 0
            summary["total_tokens"] += record["total_tokens"] or 0
            
            # Calculate derived metrics
            error_rate = record["error_count"] / record["request_count"] if record["request_count"] > 0 else 0
            success_rate = 1 - error_rate
            
            # Add to grouped metrics
            grouped_record = {field: record[field] for field in valid_group_fields}
            grouped_record.update({
                "request_count": record["request_count"],
                "success_count": record["success_count"],
                "error_count": record["error_count"],
                "success_rate": success_rate,
                "error_rate": error_rate,
                "avg_inference_time": record["avg_inference_time"],
                "max_inference_time": record["max_inference_time"],
                "prompt_tokens": record["prompt_tokens"] or 0,
                "completion_tokens": record["completion_tokens"] or 0,
                "total_tokens": record["total_tokens"] or 0,
                "total_cost": record["total_cost"] or 0,
                "cost_per_1k_tokens": (record["total_cost"] * 1000 / record["total_tokens"]) if record["total_tokens"] else 0
            })
            
            summary["grouped_metrics"].append(grouped_record)
        
        # Calculate overall stats
        if summary["total_requests"] > 0:
            # Get overall success rate
            total_success = sum(r["success_count"] for r in summary["grouped_metrics"])
            summary["success_rate"] = total_success / summary["total_requests"]
            
            # Get overall avg inference time
            total_inference_time = sum(r["avg_inference_time"] * r["request_count"] for r in summary["grouped_metrics"])
            summary["avg_inference_time"] = total_inference_time / summary["total_requests"]
        
        # Cache results
        self.cached_aggregations[cache_key] = summary
        self.cache_expiry[cache_key] = (datetime.now() + timedelta(seconds=self.cache_timeout)).timestamp()
        
        return summary
    
    def get_time_series_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        interval: str = "auto",
        filters: Dict[str, Any] = None,
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get time series metrics for visualization.
        
        Args:
            start_time: Start time for query
            end_time: End time for query
            interval: Time interval (auto, minute, hour, day, week)
            filters: Optional filters to apply
            metrics: Metrics to include (default all)
            
        Returns:
            Dictionary with time series data
        """
        # Determine appropriate interval if auto
        if interval == "auto":
            time_diff = end_time - start_time
            if time_diff <= timedelta(hours=2):
                interval = "minute"
            elif time_diff <= timedelta(days=1):
                interval = "15minute"
            elif time_diff <= timedelta(days=7):
                interval = "hour"
            elif time_diff <= timedelta(days=30):
                interval = "day"
            else:
                interval = "week"
        
        # Map interval to PostgreSQL interval and format
        interval_map = {
            "minute": ("1 minute", "YYYY-MM-DD HH24:MI:00"),
            "15minute": ("15 minute", "YYYY-MM-DD HH24:MI:00"),
            "hour": ("1 hour", "YYYY-MM-DD HH24:00:00"),
            "day": ("1 day", "YYYY-MM-DD"),
            "week": ("1 week", "YYYY-WW")
        }
        
        pg_interval, format_string = interval_map.get(interval, interval_map["hour"])
        
        # Determine metrics to include
        valid_metrics = ["request_count", "error_rate", "avg_inference_time", "total_tokens", "total_cost"]
        metrics_to_include = [m for m in (metrics or valid_metrics) if m in valid_metrics]
        
        if not metrics_to_include:
            metrics_to_include = valid_metrics
        
        # Generate cache key
        cache_key = f"timeseries:{start_time}:{end_time}:{interval}:{json.dumps(filters)}:{json.dumps(metrics_to_include)}"
        
        # Check cache
        if cache_key in self.cached_aggregations and self.cache_expiry.get(cache_key, 0) > datetime.now().timestamp():
            return self.cached_aggregations[cache_key]
        
        # Determine query parameters
        params = [start_time, end_time]
        where_clauses = ["timestamp >= %s", "timestamp <= %s"]
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if field in ["provider", "model", "application", "environment", "success"]:
                    where_clauses.append(f"{field} = %s")
                    params.append(value)
        
        # Construct and execute query
        cursor = self.db.cursor()
        query = f"""
            WITH time_buckets AS (
                SELECT 
                    date_trunc('{pg_interval}', timestamp) as time_bucket,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN success THEN 0 ELSE 1 END) as error_count,
                    AVG(inference_time) as avg_inference_time,
                    SUM(COALESCE(total_tokens, 0)) as total_tokens,
                    SUM(COALESCE(estimated_cost, 0)) as total_cost
                FROM request_metrics
                WHERE {" AND ".join(where_clauses)}
                GROUP BY time_bucket
                ORDER BY time_bucket
            )
            SELECT 
                TO_CHAR(time_bucket, '{format_string}') as time_label,
                request_count,
                error_count,
                CASE WHEN request_count > 0 THEN error_count::float / request_count ELSE 0 END as error_rate,
                avg_inference_time,
                total_tokens,
                total_cost
            FROM time_buckets
        """
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Format results for time series visualization
        timeseries = {
            "labels": [],
            "datasets": {metric: [] for metric in metrics_to_include}
        }
        
        for row in results:
            record = dict(row)
            
            # Add time label
            timeseries["labels"].append(record["time_label"])
            
            # Add metrics
            for metric in metrics_to_include:
                if metric == "error_rate":
                    timeseries["datasets"][metric].append(record["error_rate"])
                else:
                    timeseries["datasets"][metric].append(record.get(metric, 0))
        
        # Add metadata
        result = {
            "timeseries": timeseries,
            "interval": interval,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "point_count": len(results)
        }
        
        # Cache results
        self.cached_aggregations[cache_key] = result
        self.cache_expiry[cache_key] = (datetime.now() + timedelta(seconds=self.cache_timeout)).timestamp()
        
        return result
    
    def get_anomaly_summary(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get summary of detected anomalies.
        
        Args:
            start_time: Start time for query
            end_time: End time for query
            filters: Optional filters to apply
            
        Returns:
            Dictionary with anomaly summary
        """
        # Generate cache key
        cache_key = f"anomaly_summary:{start_time}:{end_time}:{json.dumps(filters)}"
        
        # Check cache
        if cache_key in self.cached_aggregations and self.cache_expiry.get(cache_key, 0) > datetime.now().timestamp():
            return self.cached_aggregations[cache_key]
        
        # Determine query parameters
        params = [start_time, end_time]
        where_clauses = ["timestamp >= %s", "timestamp <= %s"]
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if field in ["provider", "model", "application", "type"]:
                    where_clauses.append(f"{field} = %s")
                    params.append(value)
        
        # Construct and execute query
        cursor = self.db.cursor()
        
        # Get anomaly counts by type
        query = f"""
            SELECT 
                type,
                COUNT(*) as count
            FROM anomalies
            WHERE {" AND ".join(where_clauses)}
            GROUP BY type
            ORDER BY count DESC
        """
        
        cursor.execute(query, params)
        type_results = cursor.fetchall()
        
        # Get anomaly counts by model
        query = f"""
            SELECT 
                provider,
                model,
                COUNT(*) as count
            FROM anomalies
            WHERE {" AND ".join(where_clauses)}
            GROUP BY provider, model
            ORDER BY count DESC
        """
        
        cursor.execute(query, params)
        model_results = cursor.fetchall()
        
        # Get anomaly counts by day
        query = f"""
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as count
            FROM anomalies
            WHERE {" AND ".join(where_clauses)}
            GROUP BY date
            ORDER BY date
        """
        
        cursor.execute(query, params)
        daily_results = cursor.fetchall()
        
        # Format results
        summary = {
            "total_anomalies": sum(r["count"] for r in type_results),
            "by_type": [dict(r) for r in type_results],
            "by_model": [dict(r) for r in model_results],
            "by_day": [dict(r) for r in daily_results],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # Cache results
        self.cached_aggregations[cache_key] = summary
        self.cache_expiry[cache_key] = (datetime.now() + timedelta(seconds=self.cache_timeout)).timestamp()
        
        return summary
    
    def get_model_comparison(
        self,
        models: List[Dict[str, str]],
        start_time: datetime,
        end_time: datetime,
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare metrics between different models.
        
        Args:
            models: List of model specs with provider and model
            start_time: Start time for query
            end_time: End time for query
            metrics: Metrics to include (default all)
            
        Returns:
            Dictionary with model comparison
        """
        if not models:
            return {"error": "No models specified for comparison"}
        
        # Determine metrics to include
        valid_metrics = [
            "avg_inference_time", "error_rate", "total_tokens_per_request", 
            "cost_per_request", "cost_per_1k_tokens"
        ]
        metrics_to_include = [m for m in (metrics or valid_metrics) if m in valid_metrics]
        
        if not metrics_to_include:
            metrics_to_include = valid_metrics
        
        # Generate cache key
        cache_key = f"model_comparison:{json.dumps(models)}:{start_time}:{end_time}:{json.dumps(metrics_to_include)}"
        
        # Check cache
        if cache_key in self.cached_aggregations and self.cache_expiry.get(cache_key, 0) > datetime.now().timestamp():
            return self.cached_aggregations[cache_key]
        
        # Prepare model data
        comparison = {
            "models": models,
            "metrics": {metric: [] for metric in metrics_to_include},
            "request_counts": []
        }
        
        # Query for each model
        for model_spec in models:
            provider = model_spec.get("provider")
            model = model_spec.get("model")
            
            if not provider or not model:
                continue
            
            # Construct query
            cursor = self.db.cursor()
            query = """
                SELECT 
                    COUNT(*) as request_count,
                    AVG(inference_time) as avg_inference_time,
                    SUM(CASE WHEN success THEN 0 ELSE 1 END)::float / COUNT(*) as error_rate,
                    SUM(COALESCE(total_tokens, 0)) / COUNT(*) as total_tokens_per_request,
                    SUM(COALESCE(estimated_cost, 0)) / COUNT(*) as cost_per_request,
                    CASE 
                        WHEN SUM(COALESCE(total_tokens, 0)) > 0 
                        THEN SUM(COALESCE(estimated_cost, 0)) * 1000 / SUM(COALESCE(total_tokens, 0)) 
                        ELSE 0 
                    END as cost_per_1k_tokens
                FROM request_metrics
                WHERE provider = %s AND model = %s
                  AND timestamp >= %s AND timestamp <= %s
            """
            
            cursor.execute(query, (provider, model, start_time, end_time))
            result = cursor.fetchone()
            
            if not result:
                # No data for this model
                for metric in metrics_to_include:
                    comparison["metrics"][metric].append(None)
                comparison["request_counts"].append(0)
                continue
            
            # Add metrics to comparison
            record = dict(result)
            for metric in metrics_to_include:
                comparison["metrics"][metric].append(record.get(metric, 0))
            
            comparison["request_counts"].append(record["request_count"])
        
        # Add metadata
        comparison["start_time"] = start_time.isoformat()
        comparison["end_time"] = end_time.isoformat()
        
        # Cache results
        self.cached_aggregations[cache_key] = comparison
        self.cache_expiry[cache_key] = (datetime.now() + timedelta(seconds=self.cache_timeout)).timestamp()
        
        return comparison
    
    def get_hallucination_stats(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get statistics on hallucination detection.
        
        Args:
            start_time: Start time for query
            end_time: End time for query
            filters: Optional filters to apply
            
        Returns:
            Dictionary with hallucination statistics
        """
        # Generate cache key
        cache_key = f"hallucination_stats:{start_time}:{end_time}:{json.dumps(filters)}"
        
        # Check cache
        if cache_key in self.cached_aggregations and self.cache_expiry.get(cache_key, 0) > datetime.now().timestamp():
            return self.cached_aggregations[cache_key]
        
        # Determine query parameters
        params = [start_time, end_time]
        where_clauses = ["timestamp >= %s", "timestamp <= %s"]
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if field in ["provider", "model", "application", "environment", "hallucination_detected"]:
                    where_clauses.append(f"{field} = %s")
                    params.append(value)
        
        # Construct and execute queries
        cursor = self.db.cursor()
        
        # Get overall stats
        query = f"""
            SELECT 
                COUNT(*) as total_analyzed,
                SUM(CASE WHEN hallucination_detected THEN 1 ELSE 0 END) as hallucinations_detected,
                AVG(score) as avg_score
            FROM hallucinations
            WHERE {" AND ".join(where_clauses)}
        """
        
        cursor.execute(query, params)
        overall = cursor.fetchone()
        
        # Get hallucination counts by confidence
        query = f"""
            SELECT 
                confidence,
                COUNT(*) as count
            FROM hallucinations
            WHERE {" AND ".join(where_clauses)} AND hallucination_detected = TRUE
            GROUP BY confidence
            ORDER BY 
                CASE 
                    WHEN confidence = 'high' THEN 1
                    WHEN confidence = 'medium' THEN 2
                    WHEN confidence = 'low' THEN 3
                    ELSE 4
                END
        """
        
        cursor.execute(query, params)
        by_confidence = cursor.fetchall()
        
        # Get hallucination counts by reason type
        query = f"""
            SELECT 
                reason_type->>'type' as reason,
                COUNT(*) as count
            FROM hallucinations h,
                 jsonb_array_elements(reasons) as reason_type
            WHERE {" AND ".join(where_clauses)} AND hallucination_detected = TRUE
            GROUP BY reason_type->>'type'
            ORDER BY count DESC
            LIMIT 10
        """
        
        cursor.execute(query, params)
        by_reason = cursor.fetchall()
        
        # Get hallucination counts by model
        query = f"""
            SELECT 
                provider,
                model,
                COUNT(*) as analyzed_count,
                SUM(CASE WHEN hallucination_detected THEN 1 ELSE 0 END) as detected_count,
                SUM(CASE WHEN hallucination_detected THEN 1 ELSE 0 END)::float / COUNT(*) as detection_rate,
                AVG(score) as avg_score
            FROM hallucinations
            WHERE {" AND ".join(where_clauses)}
            GROUP BY provider, model
            ORDER BY detected_count DESC
        """
        
        cursor.execute(query, params)
        by_model = cursor.fetchall()
        
        # Format results
        overall_rec = dict(overall) if overall else {"total_analyzed": 0, "hallucinations_detected": 0, "avg_score": 0}
        
        stats = {
            "total_analyzed": overall_rec["total_analyzed"],
            "hallucinations_detected": overall_rec["hallucinations_detected"],
            "detection_rate": overall_rec["hallucinations_detected"] / overall_rec["total_analyzed"] if overall_rec["total_analyzed"] > 0 else 0,
            "avg_score": overall_rec["avg_score"] or 0,
            "by_confidence": [dict(r) for r in by_confidence],
            "by_reason": [dict(r) for r in by_reason],
            "by_model": [dict(r) for r in by_model],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # Cache results
        self.cached_aggregations[cache_key] = stats
        self.cache_expiry[cache_key] = (datetime.now() + timedelta(seconds=self.cache_timeout)).timestamp()
        
        return stats