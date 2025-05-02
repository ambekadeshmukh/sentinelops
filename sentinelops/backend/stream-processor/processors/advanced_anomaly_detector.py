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

logger = logging.getLogger(__name__)

class AdvancedAnomalyDetector:
    """
    Advanced anomaly detection for LLM monitoring.
    
    This class implements various anomaly detection algorithms for LLM metrics:
    - Statistical anomaly detection (Z-score, IQR)
    - Time-based anomaly detection (trend analysis)
    - Content-based anomaly detection (for hallucinations and quality issues)
    - Error pattern detection
    """
    
    def __init__(
        self,
        window_size: int = 100,
        lookback_period: int = 1000,
        alert_sensitivity: float = 3.0,
        min_data_points: int = 30
    ):
        """
        Initialize the anomaly detector.
        
        Args:
            window_size: Size of the window for moving statistics
            lookback_period: Number of data points to keep for historical analysis
            alert_sensitivity: Sensitivity threshold for anomaly detection (z-score)
            min_data_points: Minimum number of data points required for analysis
        """
        self.window_size = window_size
        self.lookback_period = lookback_period
        self.alert_sensitivity = alert_sensitivity
        self.min_data_points = min_data_points
        
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
        
        # Check for different types of anomalies
        
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
        
        # 6. Check for hallucination indicators if we have completion text
        if "completion" in current_metrics:
            hallucination_anomalies = self._check_hallucination_indicators(
                current_metrics["completion"],
                current_metrics
            )
            anomalies.extend(hallucination_anomalies)
        
        return anomalies
    
    def _check_inference_time_anomalies(
        self,
        inference_time: float,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for anomalies in inference time."""
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
        """Check for anomalies in token usage."""
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
    
    def _check_memory_usage_anomalies(
        self,
        memory_used: float,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for anomalies in memory usage."""
        anomalies = []
        
        provider = metadata.get("provider", "unknown")
        model = metadata.get("model", "unknown")
        application = metadata.get("application", "unknown")
        
        key = f"{provider}:{model}:{application}"
        metric_type = "memory_used"
        
        # Get historical data
        history = self.metrics_data[metric_type].get(key, [])
        
        # Need enough data for meaningful detection
        if len(history) < self.min_data_points:
            return anomalies
        
        # Get recent values
        recent_values = [h["value"] for h in history[-self.window_size:]]
        
        # Calculate statistics
        mean_memory = np.mean(recent_values)
        std_memory = np.std(recent_values)
        
        # Check for unusually high memory usage
        if std_memory > 0:  # Avoid division by zero
            z_score = (memory_used - mean_memory) / std_memory
            if z_score > self.alert_sensitivity:
                anomaly_id = str(uuid.uuid4())
                anomalies.append({
                    "type": "high_memory_usage",
                    "anomaly_id": anomaly_id,
                    "value": memory_used,
                    "mean": mean_memory,
                    "std": std_memory,
                    "z_score": z_score,
                    "threshold": mean_memory + (self.alert_sensitivity * std_memory),
                    "metadata": metadata
                })
        
        return anomalies
    
    def _check_hallucination_indicators(
        self,
        completion_text: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for indicators of hallucination in the completion text."""
        anomalies = []
        
        # Skip if completion is too short
        if len(completion_text) < 10:
            return anomalies
        
        # Simple heuristics for hallucination detection
        hallucination_phrases = [
            "I don't know but",
            "I'm not sure, but",
            "I don't have specific information",
            "I can't provide specific",
            "As an AI, I don't have access to",
            "I don't have access to real-time",
            "I'm making this up",
            "This is fictional",
            "This is not based on actual",
            "I'm speculating",
            "I am speculating",
            "I have to guess",
            "I'm guessing",
            "I am guessing"
        ]
        
        uncertainty_indicators = [
            "might be",
            "could be",
            "perhaps",
            "possibly",
            "maybe",
            "I think",
            "probably",
            "likely",
            "it seems",
            "it appears",
            "often",
            "typically",
            "generally",
            "usually"
        ]
        
        # Convert to lowercase for comparison
        lower_text = completion_text.lower()
        
        # Check for hallucination phrases
        found_phrases = []
        for phrase in hallucination_phrases:
            if phrase.lower() in lower_text:
                found_phrases.append(phrase)
        
        # Count uncertainty indicators
        uncertainty_count = 0
        for indicator in uncertainty_indicators:
            if " " + indicator.lower() + " " in " " + lower_text + " ":
                uncertainty_count += 1
        
        # If we found hallucination phrases or many uncertainty indicators, report it
        if found_phrases or uncertainty_count >= 4:
            anomaly_id = str(uuid.uuid4())
            anomalies.append({
                "type": "potential_hallucination",
                "anomaly_id": anomaly_id,
                "hallucination_phrases": found_phrases,
                "uncertainty_count": uncertainty_count,
                "metadata": metadata
            })
        
        # Check for contradictory statements (basic version)
        sentences = completion_text.split(". ")
        if len(sentences) > 5:  # Only check longer completions
            contradictions = self._detect_contradictions(sentences)
            if contradictions:
                if not anomalies or anomalies[-1]["type"] != "potential_hallucination":
                    anomaly_id = str(uuid.uuid4())
                    anomalies.append({
                        "type": "contradictory_statements",
                        "anomaly_id": anomaly_id,
                        "contradictions": contradictions[:3],  # Limit to top 3
                        "metadata": metadata
                    })
        
        return anomalies
    
    def _detect_contradictions(self, sentences: List[str]) -> List[Tuple[str, str]]:
        """
        Basic contradiction detection between sentences.
        This is a simplified implementation and could be improved with NLP techniques.
        """
        contradictions = []
        
        # Convert to lowercase for comparison
        sentences = [s.lower() for s in sentences]
        
        # Simple negation check
        for i in range(len(sentences)):
            for j in range(i+1, len(sentences)):
                # Skip short sentences
                if len(sentences[i]) < 10 or len(sentences[j]) < 10:
                    continue
                    
                # Check for basic contradictions
                if (("is" in sentences[i] and "is not" in sentences[j]) or
                    ("is not" in sentences[i] and "is" in sentences[j]) or
                    ("can" in sentences[i] and "cannot" in sentences[j]) or
                    ("cannot" in sentences[i] and "can" in sentences[j]) or
                    ("will" in sentences[i] and "will not" in sentences[j]) or
                    ("will not" in sentences[i] and "will" in sentences[j])):
                    contradictions.append((sentences[i], sentences[j]))
        
        return contradictions
    
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
        
        # Check for patterns across applications
        
        # Look for systemic performance issues by provider/model
        inference_time_by_provider_model = defaultdict(list)
        
        for key, history in self.metrics_data["inference_time"].items():
            if len(history) < self.min_data_points:
                continue
                
            # Get provider and model from key
            provider, model, _ = key.split(":")
            provider_model_key = f"{provider}:{model}"
            
            # Get recent values
            recent_values = [h["value"] for h in history[-self.window_size:]]
            avg_time = np.mean(recent_values)
            
            inference_time_by_provider_model[provider_model_key].append(avg_time)
        
        # Check for models that are consistently slower
        for provider_model, times in inference_time_by_provider_model.items():
            if len(times) >= 3:  # Have data from at least 3 applications
                avg_time = np.mean(times)
                provider, model = provider_model.split(":")
                
                # Check if this model is significantly slower than a threshold
                # This threshold could be dynamically determined based on all models
                if avg_time > 2.0:  # Example threshold
                    anomaly_id = str(uuid.uuid4())
                    anomalies.append({
                        "type": "model_performance_issue",
                        "anomaly_id": anomaly_id,
                        "provider": provider,
                        "model": model,
                        "avg_inference_time": avg_time,
                        "timestamp": current_time
                    })
        
        # Check for applications with increasing error rates
        for key, history in self.metrics_data["inference_time"].items():
            if len(history) < 100:  # Need more data for this analysis
                continue
                
            # Get application info
            provider, model, application = key.split(":")
            
            # Count recent errors vs older errors
            recent_history = history[-50:]  # Last 50 requests
            older_history = history[-100:-50]  # Previous 50 requests
            
            recent_errors = sum(1 for h in recent_history if not h["metadata"].get("success", True))
            older_errors = sum(1 for h in older_history if not h["metadata"].get("success", True))
            
            # Calculate error rates
            recent_error_rate = recent_errors / len(recent_history) if recent_history else 0
            older_error_rate = older_errors / len(older_history) if older_history else 0
            
            # Check for significant increase in error rate
            if recent_error_rate > 0.1 and recent_error_rate > (2 * older_error_rate + 0.05):
                anomaly_id = str(uuid.uuid4())
                anomalies.append({
                    "type": "increasing_error_rate",
                    "anomaly_id": anomaly_id,
                    "provider": provider,
                    "model": model,
                    "application": application,
                    "recent_error_rate": recent_error_rate,
                    "previous_error_rate": older_error_rate,
                    "timestamp": current_time
                })
        
        return anomalies