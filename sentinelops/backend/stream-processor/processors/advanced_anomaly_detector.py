# sentinelops/backend/stream-processor/processors/advanced_anomaly_detector.py
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import json
import time
from collections import defaultdict
import uuid
import statsmodels.api as sm
from statsmodels.tsa.seasonal import seasonal_decompose
from scipy.signal import find_peaks

logger = logging.getLogger(__name__)

class AdvancedAnomalyDetector:
    """
    Enhanced anomaly detection for LLM monitoring with pattern recognition.
    
    Features:
    - Statistical anomaly detection (Z-score, IQR)
    - Time-series anomaly detection with seasonal decomposition
    - Pattern recognition for recurring issues
    - Cost optimization insights
    - Multi-dimensional anomaly detection
    """
    
    def __init__(
        self,
        window_size: int = 100,
        lookback_period: int = 1000,
        alert_sensitivity: float = 3.0,
        min_data_points: int = 30,
        seasonal_period: int = 24  # Default: 24 hours
    ):
        """
        Initialize the enhanced anomaly detector.
        
        Args:
            window_size: Size of the window for moving statistics
            lookback_period: Number of data points to keep for historical analysis
            alert_sensitivity: Sensitivity threshold for anomaly detection (z-score)
            min_data_points: Minimum number of data points required for analysis
            seasonal_period: Period for seasonal decomposition (in hours)
        """
        self.window_size = window_size
        self.lookback_period = lookback_period
        self.alert_sensitivity = alert_sensitivity
        self.min_data_points = min_data_points
        self.seasonal_period = seasonal_period
        
        # State storage for different metrics by model and application
        self.metrics_data = defaultdict(lambda: defaultdict(list))
        self.anomaly_counts = defaultdict(int)  # Track anomalies to prevent alert fatigue
        
        # Storage for detected patterns
        self.error_patterns = defaultdict(int)
        
        # Internal state for token usage analysis
        self.token_ratios = defaultdict(list)
        
        # Time-series state
        self.last_analysis_time = datetime.now()
        self.time_bins = {}
        
        # Cost optimization state
        self.cost_patterns = {}  # Track cost patterns by provider/model/application
        
        # Multi-dimensional analysis state
        self.correlation_matrix = {}  # Track correlations between different metrics
    
    def add_metric(
        self, 
        metric_type: str,
        value: float,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Add a new metric data point for anomaly detection.
        
        Args:
            metric_type: Type of metric (inference_time, token_count, etc.)
            value: The metric value
            metadata: Additional metadata (provider, model, application, etc.)
        """
        # Create a compound key to separate metrics by provider/model/application
        provider = metadata.get("provider", "unknown")
        model = metadata.get("model", "unknown")
        application = metadata.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        
        # Add timestamp if not provided
        timestamp = metadata.get("timestamp", datetime.now())
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
        
        # Store the data point with metadata
        data_point = {
            "value": value,
            "timestamp": timestamp,
            "metadata": metadata
        }
        
        # Add to the appropriate list
        self.metrics_data[metric_type][key].append(data_point)
        
        # Trim old data if needed
        if len(self.metrics_data[metric_type][key]) > self.lookback_period:
            self.metrics_data[metric_type][key] = self.metrics_data[metric_type][key][-self.lookback_period:]
        
        # If we have a token ratio metric, update token ratio analysis
        if metric_type == "total_tokens" and "prompt_tokens" in metadata and "completion_tokens" in metadata:
            prompt_tokens = metadata["prompt_tokens"]
            completion_tokens = metadata["completion_tokens"]
            if prompt_tokens > 0:  # Avoid division by zero
                ratio = completion_tokens / prompt_tokens
                ratio_point = {
                    "value": ratio,
                    "timestamp": timestamp,
                    "metadata": metadata
                }
                self.token_ratios[key].append(ratio_point)
                
                # Trim if needed
                if len(self.token_ratios[key]) > self.lookback_period:
                    self.token_ratios[key] = self.token_ratios[key][-self.lookback_period:]
        
        # Update cost patterns if this is a cost metric
        if metric_type == "estimated_cost":
            self._update_cost_patterns(value, metadata)
            
        # Update correlation matrix periodically
        if len(self.metrics_data[metric_type][key]) % 50 == 0:  # Every 50 data points
            self._update_correlation_matrix(key)
    
    def _update_cost_patterns(self, cost: float, metadata: Dict[str, Any]) -> None:
        """
        Update cost patterns for optimization insights.
        
        Args:
            cost: The cost value
            metadata: Request metadata
        """
        provider = metadata.get("provider", "unknown")
        model = metadata.get("model", "unknown")
        application = metadata.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        
        # Initialize cost pattern if not exists
        if key not in self.cost_patterns:
            self.cost_patterns[key] = {
                "total_cost": 0.0,
                "request_count": 0,
                "avg_tokens_per_request": 0,
                "prompt_ratio": 0,  # Ratio of prompt tokens to total
                "last_update": datetime.now(),
                "hourly_patterns": defaultdict(float),  # Cost by hour of day
                "daily_patterns": defaultdict(float),   # Cost by day of week
            }
        
        # Update cost pattern
        self.cost_patterns[key]["total_cost"] += cost
        self.cost_patterns[key]["request_count"] += 1
        
        # Update token ratios
        if "total_tokens" in metadata and metadata["total_tokens"] > 0:
            total_tokens = metadata["total_tokens"]
            prompt_tokens = metadata.get("prompt_tokens", 0)
            
            # Update running average of tokens per request
            pattern = self.cost_patterns[key]
            old_avg = pattern["avg_tokens_per_request"]
            old_count = pattern["request_count"] - 1  # Exclude current request
            
            if old_count > 0:
                new_avg = (old_avg * old_count + total_tokens) / pattern["request_count"]
                pattern["avg_tokens_per_request"] = new_avg
            else:
                pattern["avg_tokens_per_request"] = total_tokens
            
            # Update prompt ratio
            if total_tokens > 0:
                old_ratio = pattern["prompt_ratio"]
                new_ratio = prompt_tokens / total_tokens
                
                if old_count > 0:
                    pattern["prompt_ratio"] = (old_ratio * old_count + new_ratio) / pattern["request_count"]
                else:
                    pattern["prompt_ratio"] = new_ratio
        
        # Update time patterns
        timestamp = metadata.get("timestamp", datetime.now())
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
            
        hour_key = timestamp.hour
        day_key = timestamp.weekday()  # 0 = Monday, 6 = Sunday
        
        self.cost_patterns[key]["hourly_patterns"][hour_key] += cost
        self.cost_patterns[key]["daily_patterns"][day_key] += cost
        self.cost_patterns[key]["last_update"] = timestamp
    
    def _update_correlation_matrix(self, key: str) -> None:
        """
        Update correlation matrix between different metrics.
        
        Args:
            key: The provider:model:application key
        """
        # Get available metric types for this key
        metric_types = []
        for metric_type, data_by_key in self.metrics_data.items():
            if key in data_by_key and len(data_by_key[key]) >= self.min_data_points:
                metric_types.append(metric_type)
        
        # Need at least 2 metric types for correlation
        if len(metric_types) < 2:
            return
            
        # Create data frame with aligned timestamps
        data_points = {}
        timestamps = set()
        
        # Collect all timestamps
        for metric_type in metric_types:
            for data_point in self.metrics_data[metric_type][key]:
                timestamps.add(data_point["timestamp"])
        
        # Sort timestamps
        sorted_timestamps = sorted(timestamps)
        
        # Initialize data frame
        df = pd.DataFrame(index=sorted_timestamps)
        
        # Fill data frame with values
        for metric_type in metric_types:
            values = []
            timestamp_to_value = {
                data_point["timestamp"]: data_point["value"]
                for data_point in self.metrics_data[metric_type][key]
            }
            
            for ts in sorted_timestamps:
                values.append(timestamp_to_value.get(ts, np.nan))
            
            df[metric_type] = values
        
        # Fill missing values with forward fill, then backward fill
        df = df.fillna(method="ffill").fillna(method="bfill")
        
        # Compute correlation matrix
        corr_matrix = df.corr()
        
        # Store correlation matrix
        self.correlation_matrix[key] = corr_matrix.to_dict()
    
    def detect_anomalies(
        self,
        current_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the current metrics.
        
        Args:
            current_metrics: The current metric values with metadata
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Run basic anomaly detection
        basic_anomalies = self._detect_basic_anomalies(current_metrics)
        anomalies.extend(basic_anomalies)
        
        # Run time-series anomaly detection if we have enough data
        if "timestamp" in current_metrics:
            ts_anomalies = self._detect_time_series_anomalies(current_metrics)
            anomalies.extend(ts_anomalies)
        
        # Run multi-dimensional anomaly detection
        multidim_anomalies = self._detect_multidimensional_anomalies(current_metrics)
        anomalies.extend(multidim_anomalies)
        
        # Check for optimization opportunities
        if "estimated_cost" in current_metrics:
            optimization_insights = self._check_optimization_opportunities(current_metrics)
            anomalies.extend(optimization_insights)
        
        return anomalies
    
    def _detect_basic_anomalies(
        self,
        current_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect basic statistical anomalies in current metrics.
        
        Args:
            current_metrics: The current metric values
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # 1. Inference time anomalies
        if "inference_time" in current_metrics:
            inference_anomalies = self._check_inference_time_anomalies(
                current_metrics["inference_time"],
                current_metrics
            )
            anomalies.extend(inference_anomalies)
        
        # 2. Token usage anomalies
        if "prompt_tokens" in current_metrics and "completion_tokens" in current_metrics:
            token_anomalies = self._check_token_usage_anomalies(
                current_metrics["prompt_tokens"],
                current_metrics["completion_tokens"],
                current_metrics
            )
            anomalies.extend(token_anomalies)
        
        # 3. Error pattern anomalies
        if "success" in current_metrics and not current_metrics["success"]:
            error_anomalies = self._check_error_pattern_anomalies(
                current_metrics.get("error", "unknown error"),
                current_metrics
            )
            anomalies.extend(error_anomalies)
        
        # 4. Cost anomalies
        if "estimated_cost" in current_metrics:
            cost_anomalies = self._check_cost_anomalies(
                current_metrics["estimated_cost"],
                current_metrics
            )
            anomalies.extend(cost_anomalies)
            
        # 5. Memory usage anomalies
        if "memory_used" in current_metrics:
            memory_anomalies = self._check_memory_usage_anomalies(
                current_metrics["memory_used"],
                current_metrics
            )
            anomalies.extend(memory_anomalies)
        
        return anomalies
    
    def _detect_time_series_anomalies(
        self,
        current_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies using time-series analysis.
        
        Args:
            current_metrics: Current metrics with timestamp
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Skip if no timestamp or required metrics
        if "timestamp" not in current_metrics or "inference_time" not in current_metrics:
            return anomalies
        
        provider = current_metrics.get("provider", "unknown")
        model = current_metrics.get("model", "unknown")
        application = current_metrics.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        metric_type = "inference_time"
        
        # Get historical data
        history = self.metrics_data[metric_type].get(key, [])
        
        # Need enough data points for time-series analysis
        if len(history) < self.seasonal_period * 2:
            return anomalies
        
        # Create time series from historical data
        timestamps = [h["timestamp"] for h in history[-self.lookback_period:]]
        values = [h["value"] for h in history[-self.lookback_period:]]
        
        # Sort by timestamp
        time_values = sorted(zip(timestamps, values), key=lambda x: x[0])
        timestamps = [tv[0] for tv in time_values]
        values = [tv[1] for tv in time_values]
        
        try:
            # Create pandas Series
            ts = pd.Series(values, index=timestamps)
            
            # Resample to hourly data to handle irregular timestamps
            ts = ts.resample('1H').mean().fillna(method='ffill')
            
            # Check if we have enough data after resampling
            if len(ts) < self.seasonal_period * 2:
                return anomalies
            
            # Perform seasonal decomposition
            result = seasonal_decompose(
                ts, 
                model='additive', 
                period=self.seasonal_period,
                extrapolate_trend='freq'
            )
            
            # Get residual component
            residual = result.resid
            
            # Calculate threshold for anomalies
            residual_std = residual.std()
            threshold = self.alert_sensitivity * residual_std
            
            # Current timestamp and value
            current_timestamp = current_metrics["timestamp"]
            if isinstance(current_timestamp, (int, float)):
                current_timestamp = datetime.fromtimestamp(current_timestamp)
                
            current_value = current_metrics["inference_time"]
            
            # Get expected value from trend and seasonal components
            try:
                # Find closest timestamp in the decomposition
                closest_idx = (ts.index - current_timestamp).abs().argmin()
                closest_ts = ts.index[closest_idx]
                
                expected_value = (
                    result.trend[closest_ts] + 
                    result.seasonal[closest_ts]
                )
                
                # Calculate residual for current value
                current_residual = current_value - expected_value
                
                # Check if residual exceeds threshold
                if abs(current_residual) > threshold:
                    anomaly_id = str(uuid.uuid4())
                    anomalies.append({
                        "type": "time_series_anomaly",
                        "anomaly_id": anomaly_id,
                        "value": current_value,
                        "expected": expected_value,
                        "residual": current_residual,
                        "threshold": threshold,
                        "timestamp": current_timestamp,
                        "metadata": current_metrics
                    })
            except (KeyError, IndexError):
                # If we can't find the timestamp in the decomposition, skip
                pass
                
        except Exception as e:
            logger.warning(f"Time-series anomaly detection failed: {str(e)}")
        
        return anomalies
    
    def _detect_multidimensional_anomalies(
        self,
        current_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies across multiple dimensions.
        
        Args:
            current_metrics: Current metrics
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        provider = current_metrics.get("provider", "unknown")
        model = current_metrics.get("model", "unknown")
        application = current_metrics.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        
        # Check if we have correlation data for this key
        if key not in self.correlation_matrix:
            return anomalies
            
        corr_matrix = self.correlation_matrix[key]
        
        # Example: Check if inference time and memory usage are unusually diverging
        # when they are typically highly correlated
        if ("inference_time" in corr_matrix and "memory_used" in corr_matrix and
            "inference_time" in current_metrics and "memory_used" in current_metrics):
            
            # Get correlation coefficient
            try:
                corr_coef = corr_matrix["inference_time"]["memory_used"]
                
                # If normally highly correlated (>0.7) but current values diverge
                if corr_coef > 0.7:
                    # Get normalized values
                    inference_time = current_metrics["inference_time"]
                    memory_used = current_metrics["memory_used"]
                    
                    # Get historical data
                    inference_history = self.metrics_data["inference_time"].get(key, [])
                    memory_history = self.metrics_data["memory_used"].get(key, [])
                    
                    if len(inference_history) >= self.min_data_points and len(memory_history) >= self.min_data_points:
                        # Calculate z-scores
                        inference_mean = np.mean([h["value"] for h in inference_history[-self.window_size:]])
                        inference_std = np.std([h["value"] for h in inference_history[-self.window_size:]])
                        
                        memory_mean = np.mean([h["value"] for h in memory_history[-self.window_size:]])
                        memory_std = np.std([h["value"] for h in memory_history[-self.window_size:]])
                        
                        if inference_std > 0 and memory_std > 0:
                            inference_z = (inference_time - inference_mean) / inference_std
                            memory_z = (memory_used - memory_mean) / memory_std
                            
                            # Check if z-scores diverge significantly
                            if abs(inference_z - memory_z) > self.alert_sensitivity * 1.5:
                                anomaly_id = str(uuid.uuid4())
                                anomalies.append({
                                    "type": "correlation_divergence",
                                    "anomaly_id": anomaly_id,
                                    "metric1": "inference_time",
                                    "metric2": "memory_used",
                                    "value1": inference_time,
                                    "value2": memory_used,
                                    "z_score1": inference_z,
                                    "z_score2": memory_z,
                                    "correlation": corr_coef,
                                    "metadata": current_metrics
                                })
            except (KeyError, TypeError):
                pass
        
        return anomalies
    
    def _check_optimization_opportunities(
        self,
        current_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check for cost optimization opportunities.
        
        Args:
            current_metrics: Current metrics with cost info
            
        Returns:
            List of optimization insights
        """
        insights = []
        
        if "estimated_cost" not in current_metrics:
            return insights
            
        provider = current_metrics.get("provider", "unknown")
        model = current_metrics.get("model", "unknown")
        application = current_metrics.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        
        # Skip if no cost pattern data or not enough history
        if key not in self.cost_patterns or self.cost_patterns[key]["request_count"] < self.min_data_points:
            return insights
        
        pattern = self.cost_patterns[key]
        
        # Check for high prompt token ratio (potential for optimization)
        if pattern["prompt_ratio"] > 0.8:  # 80% of tokens are prompt tokens
            if "prompt_tokens" in current_metrics and "total_tokens" in current_metrics:
                current_ratio = current_metrics["prompt_tokens"] / current_metrics["total_tokens"]
                
                if current_ratio > 0.8:
                    anomaly_id = str(uuid.uuid4())
                    insights.append({
                        "type": "cost_optimization",
                        "anomaly_id": anomaly_id,
                        "subtype": "high_prompt_ratio",
                        "value": current_ratio,
                        "avg_ratio": pattern["prompt_ratio"],
                        "metadata": current_metrics,
                        "recommendation": "Consider optimizing prompts to reduce token usage."
                    })
        
        # Check for models with similar capability but lower cost
        # This would require a model capability mapping
        model_alternatives = self._get_model_alternatives(model)
        if model_alternatives:
            anomaly_id = str(uuid.uuid4())
            insights.append({
                "type": "cost_optimization",
                "anomaly_id": anomaly_id,
                "subtype": "model_alternative",
                "value": current_metrics["estimated_cost"],
                "alternatives": model_alternatives,
                "metadata": current_metrics,
                "recommendation": "Consider using an alternative model with similar capabilities but lower cost."
            })
        
        # Check for underutilized context window
        if "prompt_tokens" in current_metrics and "completion_tokens" in current_metrics:
            total_tokens = current_metrics["prompt_tokens"] + current_metrics["completion_tokens"]
            
            # Model-specific context windows
            context_window = self._get_model_context_window(model)
            
            if context_window and total_tokens < context_window * 0.3:  # Using less than 30% of context window
                anomaly_id = str(uuid.uuid4())
                insights.append({
                    "type": "cost_optimization",
                    "anomaly_id": anomaly_id,
                    "subtype": "underutilized_context",
                    "value": total_tokens,
                    "context_window": context_window,
                    "utilization": total_tokens / context_window,
                    "metadata": current_metrics,
                    "recommendation": "Consider batching requests to more efficiently use the model's context window."
                })
        
        return insights
    
    def _get_model_alternatives(self, model: str) -> List[Dict[str, Any]]:
        """
        Get alternative models with similar capabilities but lower cost.
        
        Args:
            model: The current model
            
        Returns:
            List of alternative models with cost ratio
        """
        # This is a simplified implementation that could be expanded with real data
        alternatives = []
        
        model_lower = model.lower()
        
        # OpenAI alternatives
        if "gpt-4" in model_lower:
            alternatives.append({
                "model": "gpt-3.5-turbo",
                "cost_ratio": 0.1,  # ~10% of the cost
                "capability_ratio": 0.7  # ~70% of the capability
            })
        elif "gpt-3.5-turbo" in model_lower:
            alternatives.append({
                "model": "gpt-3.5-turbo-instruct",
                "cost_ratio": 0.8,
                "capability_ratio": 0.9
            })
        
        # Anthropic alternatives
        elif "claude-v2" in model_lower or "claude-2" in model_lower:
            alternatives.append({
                "model": "claude-instant-v1",
                "cost_ratio": 0.4,
                "capability_ratio": 0.8
            })
        
        return alternatives
    
    def _get_model_context_window(self, model: str) -> Optional[int]:
        """
        Get the context window size for a model.
        
        Args:
            model: The model name
            
        Returns:
            Context window size in tokens, or None if unknown
        """
        model_lower = model.lower()
        
        # OpenAI models
        if "gpt-4-32k" in model_lower:
            return 32768
        elif "gpt-4" in model_lower:
            return 8192
        elif "gpt-3.5-turbo-16k" in model_lower:
            return 16384
        elif "gpt-3.5-turbo" in model_lower:
            return 4096
        
        # Anthropic models
        elif "claude-2" in model_lower or "claude-v2" in model_lower:
            return 100000
        elif "claude-instant" in model_lower:
            return 100000
        
        # Other models could be added here
        
        return None
    
    def _check_inference_time_anomalies(
        self,
        inference_time: float,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check for anomalies in inference time.
        
        Args:
            inference_time: Current inference time
            metadata: Request metadata
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        provider = metadata.get("provider", "unknown")
        model = metadata.get("model", "unknown")
        application = metadata.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        metric_type = "inference_time"
        
        # Get historical data for this key
        history = self.metrics_data[metric_type].get(key, [])
        
        # Need enough data for meaningful detection
        if len(history) < self.min_data_points:
            return anomalies
        
        # Get recent values
        recent_values = [h["value"] for h in history[-self.window_size:]]
        
        # Calculate statistics
        mean_time = np.mean(recent_values)
        std_time = np.std(recent_values)
        median_time = np.median(recent_values)
        q1 = np.percentile(recent_values, 25)
        q3 = np.percentile(recent_values, 75)
        iqr = q3 - q1
        
        # Z-score anomaly detection
        if std_time > 0:  # Avoid division by zero
            z_score = (inference_time - mean_time) / std_time
            if z_score > self.alert_sensitivity:
                anomaly_id = str(uuid.uuid4())
                anomalies.append({
                    "type": "inference_time_spike",
                    "anomaly_id": anomaly_id,
                    "value": inference_time,
                    "mean": mean_time,
                    "median": median_time,
                    "std": std_time,
                    "z_score": z_score,
                    "threshold": mean_time + (self.alert_sensitivity * std_time),
                    "metadata": metadata
                })
                
        # IQR-based anomaly detection (robust to outliers)
        upper_bound = q3 + (1.5 * iqr)
        if inference_time > upper_bound:
            # Only add if we haven't already detected this as a z-score anomaly
            if not anomalies or anomalies[-1]["type"] != "inference_time_spike":
                anomaly_id = str(uuid.uuid4())
                anomalies.append({
                    "type": "inference_time_outlier",
                    "anomaly_id": anomaly_id,
                    "value": inference_time,
                    "q1": q1,
                    "median": median_time,
                    "q3": q3,
                    "iqr": iqr,
                    "upper_bound": upper_bound,
                    "metadata": metadata
                })
        
        return anomalies
    
    def _check_token_usage_anomalies(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check for anomalies in token usage.
        
        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            metadata: Request metadata
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        provider = metadata.get("provider", "unknown")
        model = metadata.get("model", "unknown")
        application = metadata.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        
        # Calculate the ratio
        if prompt_tokens > 0:  # Avoid division by zero
            ratio = completion_tokens / prompt_tokens
            
            # Get historical ratios
            history = self.token_ratios.get(key, [])
            
            # Need enough data for meaningful detection
            if len(history) < self.min_data_points:
                return anomalies
            
            # Get recent ratios
            recent_ratios = [h["value"] for h in history[-self.window_size:]]
            
            # Calculate statistics
            mean_ratio = np.mean(recent_ratios)
            std_ratio = np.std(recent_ratios)
            
            # Check for unusual ratios (both high and low)
            if std_ratio > 0:  # Avoid division by zero
                z_score = (ratio - mean_ratio) / std_ratio
                if abs(z_score) > self.alert_sensitivity:
                    anomaly_direction = "high" if ratio > mean_ratio else "low"
                    anomaly_id = str(uuid.uuid4())
                    anomalies.append({
                        "type": f"token_ratio_{anomaly_direction}",
                        "anomaly_id": anomaly_id,
                        "value": ratio,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "mean_ratio": mean_ratio,
                        "std_ratio": std_ratio,
                        "z_score": z_score,
                        "metadata": metadata
                    })
        
        # Check for high total token usage
        total_tokens = prompt_tokens + completion_tokens
        metric_type = "total_tokens"
        
        # Get historical data
        history = self.metrics_data[metric_type].get(key, [])
        
        # Need enough data for meaningful detection
        if len(history) >= self.min_data_points:
            recent_values = [h["value"] for h in history[-self.window_size:]]
            
            # Calculate statistics
            mean_tokens = np.mean(recent_values)
            std_tokens = np.std(recent_values)
            
            # Check for unusually high token usage
            if std_tokens > 0:  # Avoid division by zero
                z_score = (total_tokens - mean_tokens) / std_tokens
                if z_score > self.alert_sensitivity:
                    anomaly_id = str(uuid.uuid4())
                    anomalies.append({
                        "type": "high_token_usage",
                        "anomaly_id": anomaly_id,
                        "value": total_tokens,
                        "mean": mean_tokens,
                        "std": std_tokens,
                        "z_score": z_score,
                        "threshold": mean_tokens + (self.alert_sensitivity * std_tokens),
                        "metadata": metadata
                    })
        
        return anomalies
    
    def _check_error_pattern_anomalies(
        self,
        error: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for patterns in errors."""
        anomalies = []
        
        provider = metadata.get("provider", "unknown")
        model = metadata.get("model", "unknown")
        application = metadata.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        error_key = f"{key}:{error[:100]}"  # Truncate long errors
        
        # Update error count
        self.error_patterns[error_key] += 1
        
        # Check if errors are occurring frequently
        error_count = self.error_patterns[error_key]
        timestamp = metadata.get("timestamp", datetime.now())
        
        # Check for cluster of errors (5+ in the last hour for same error type)
        if error_count >= 5:
            # Check for recent occurrences of this error
            history = self.metrics_data["inference_time"].get(key, [])
            
            # Filter for recent errors with the same message
            current_time = timestamp if isinstance(timestamp, datetime) else datetime.fromtimestamp(timestamp)
            one_hour_ago = current_time - timedelta(hours=1)
            
            recent_errors = []
            for h in history[-100:]:  # Look at last 100 points max
                h_time = h["timestamp"]
                if h_time >= one_hour_ago and not h["metadata"].get("success", True):
                    h_error = h["metadata"].get("error", "")
                    if error[:50] in h_error:  # Match on start of error
                        recent_errors.append(h)
            
            # If we have 5+ errors of same type in the last hour, report it
            if len(recent_errors) >= 5:
                # Avoid duplicate alerts - only report once per hour
                error_alert_key = f"{error_key}:alert"
                last_alert = self.time_bins.get(error_alert_key, datetime.min)
                
                if current_time - last_alert > timedelta(hours=1):
                    anomaly_id = str(uuid.uuid4())
                    anomalies.append({
                        "type": "error_rate_spike",
                        "anomaly_id": anomaly_id,
                        "error": error,
                        "count": len(recent_errors),
                        "first_seen": recent_errors[0]["timestamp"],
                        "metadata": metadata
                    })
                    
                    # Update last alert time
                    self.time_bins[error_alert_key] = current_time
        
        return anomalies
    
    def _check_cost_anomalies(
        self,
        cost: float,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for anomalies in cost."""
        anomalies = []
        
        provider = metadata.get("provider", "unknown")
        model = metadata.get("model", "unknown")
        application = metadata.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        metric_type = "estimated_cost"
        
        # Get historical data
        history = self.metrics_data[metric_type].get(key, [])
        
        # Need enough data for meaningful detection
        if len(history) < self.min_data_points:
            return anomalies
        
        # Get recent values
        recent_values = [h["value"] for h in history[-self.window_size:]]
        
        # Calculate statistics
        mean_cost = np.mean(recent_values)
        std_cost = np.std(recent_values)
        
        # Check for unusually high cost
        if std_cost > 0 and mean_cost > 0.001:  # Avoid division by zero and only alert on meaningful costs
            z_score = (cost - mean_cost) / std_cost
            if z_score > self.alert_sensitivity:
                anomaly_id = str(uuid.uuid4())
                anomalies.append({
                    "type": "high_cost",
                    "anomaly_id": anomaly_id,
                    "value": cost,
                    "mean": mean_cost,
                    "std": std_cost,
                    "z_score": z_score,
                    "threshold": mean_cost + (self.alert_sensitivity * std_cost),
                    "metadata": metadata
                })
        
        return anomalies
    
    def perform_periodic_analysis(self) -> List[Dict[str, Any]]:
        """
        Perform periodic analysis on collected data to detect longer-term anomalies.
        This should be called regularly, e.g., every hour.
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Check if enough time has passed since last analysis
        current_time = datetime.now()
        if (current_time - self.last_analysis_time) < timedelta(minutes=30):
            return anomalies
        
        # Update last analysis time
        self.last_analysis_time = current_time
        
        # Perform trend analysis
        trend_anomalies = self._detect_trend_anomalies()
        anomalies.extend(trend_anomalies)
        
        # Perform cost pattern analysis
        cost_insights = self._analyze_cost_patterns()
        anomalies.extend(cost_insights)
        
        # Look for patterns across applications
        cross_app_anomalies = self._detect_cross_application_anomalies()
        anomalies.extend(cross_app_anomalies)
        
        return anomalies
    
    def _detect_trend_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect anomalies in trends over time.
        
        Returns:
            List of trend anomalies
        """
        anomalies = []
        
        # Look at inference time trends
        for key, history in self.metrics_data["inference_time"].items():
            if len(history) < self.min_data_points * 2:  # Need more data for trend analysis
                continue
                
            # Get provider, model and application from key
            provider, model, application = key.split(":")
            
            # Sort history by timestamp
            sorted_history = sorted(history, key=lambda x: x["timestamp"])
            
            # Split into two periods - early and recent
            split_point = len(sorted_history) // 2
            early_period = sorted_history[:split_point]
            recent_period = sorted_history[split_point:]
            
            # Calculate means for both periods
            early_mean = np.mean([h["value"] for h in early_period])
            recent_mean = np.mean([h["value"] for h in recent_period])
            
            # Calculate standard deviation for early period
            early_std = np.std([h["value"] for h in early_period])
            
            # Check if recent mean has significantly increased
            if early_std > 0 and recent_mean > early_mean:
                z_score = (recent_mean - early_mean) / early_std
                
                if z_score > self.alert_sensitivity:
                    anomaly_id = str(uuid.uuid4())
                    anomalies.append({
                        "type": "inference_time_trend",
                        "anomaly_id": anomaly_id,
                        "provider": provider,
                        "model": model,
                        "application": application,
                        "early_mean": early_mean,
                        "recent_mean": recent_mean,
                        "percent_increase": (recent_mean - early_mean) / early_mean * 100,
                        "z_score": z_score,
                        "timestamp": datetime.now()
                    })
        
        return anomalies
    
    def _analyze_cost_patterns(self) -> List[Dict[str, Any]]:
        """
        Analyze cost patterns for optimization insights.
        
        Returns:
            List of cost optimization insights
        """
        insights = []
        
        for key, pattern in self.cost_patterns.items():
            # Skip if not enough data
            if pattern["request_count"] < self.min_data_points:
                continue
                
            provider, model, application = key.split(":")
            
            # Check for time-based usage patterns that could be optimized
            hourly_patterns = pattern["hourly_patterns"]
            if hourly_patterns:
                # Find peak usage hours
                total_cost = sum(hourly_patterns.values())
                if total_cost > 0:
                    peak_hours = []
                    peak_cost = 0
                    
                    for hour, cost in hourly_patterns.items():
                        if cost > total_cost * 0.15:  # Hours that account for >15% of cost
                            peak_hours.append(hour)
                            peak_cost += cost
                    
                    # If more than 50% of cost is in peak hours
                    if peak_cost > total_cost * 0.5 and len(peak_hours) <= 6:
                        anomaly_id = str(uuid.uuid4())
                        insights.append({
                            "type": "cost_optimization",
                            "anomaly_id": anomaly_id,
                            "subtype": "peak_hour_usage",
                            "provider": provider,
                            "model": model,
                            "application": application,
                            "peak_hours": peak_hours,
                            "peak_cost_percentage": peak_cost / total_cost * 100,
                            "timestamp": datetime.now(),
                            "recommendation": "Consider optimizing workloads to avoid peak hours."
                        })
            
            # Check for inefficient model usage (high ratio of prompt tokens)
            if pattern["prompt_ratio"] > 0.75:  # More than 75% of tokens are prompt
                anomaly_id = str(uuid.uuid4())
                insights.append({
                    "type": "cost_optimization",
                    "anomaly_id": anomaly_id,
                    "subtype": "high_prompt_ratio",
                    "provider": provider,
                    "model": model,
                    "application": application,
                    "prompt_ratio": pattern["prompt_ratio"],
                    "timestamp": datetime.now(),
                    "recommendation": "High prompt-to-completion ratio detected. Consider caching results, optimizing prompts, or using a different model."
                })
        
        return insights
    
    def _detect_cross_application_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect anomalies that span multiple applications.
        
        Returns:
            List of cross-application anomalies
        """
        anomalies = []
        
        # Group metrics by provider and model
        provider_model_metrics = defaultdict(lambda: defaultdict(list))
        
        # Collect recent inference times by provider/model
        for key, history in self.metrics_data["inference_time"].items():
            if len(history) < self.min_data_points:
                continue
                
            provider, model, application = key.split(":")
            provider_model_key = f"{provider}:{model}"
            
            # Get average inference time for last window
            recent_values = [h["value"] for h in history[-self.window_size:]]
            avg_time = np.mean(recent_values)
            
            provider_model_metrics[provider_model_key]["inference_time"].append({
                "application": application,
                "avg_time": avg_time
            })
        
        # Check for outlier applications for each provider/model
        for provider_model, metrics in provider_model_metrics.items():
            if "inference_time" in metrics and len(metrics["inference_time"]) >= 3:
                inference_times = metrics["inference_time"]
                
                # Calculate overall stats
                all_times = [app["avg_time"] for app in inference_times]
                mean_time = np.mean(all_times)
                std_time = np.std(all_times)
                
                if std_time > 0:
                    # Find outliers
                    outliers = []
                    for app in inference_times:
                        z_score = (app["avg_time"] - mean_time) / std_time
                        if z_score > self.alert_sensitivity:
                            outliers.append({
                                "application": app["application"],
                                "avg_time": app["avg_time"],
                                "z_score": z_score
                            })
                    
                    if outliers:
                        provider, model = provider_model.split(":")
                        anomaly_id = str(uuid.uuid4())
                        anomalies.append({
                            "type": "cross_application_outlier",
                            "anomaly_id": anomaly_id,
                            "provider": provider,
                            "model": model,
                            "metric": "inference_time",
                            "mean": mean_time,
                            "std": std_time,
                            "outliers": outliers,
                            "timestamp": datetime.now()
                        })
        
        return anomalies