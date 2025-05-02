# sentinelops/backend/stream-processor/processors/cost_optimizer.py
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

class CostOptimizer:
    """
    Provides cost optimization insights for LLM usage.
    
    Features:
    - Model selection optimization
    - Prompt engineering suggestions
    - Batch processing recommendations
    - Usage pattern analysis
    - Caching recommendations
    """
    
    def __init__(self, 
                 min_data_points: int = 100,
                 analysis_period_days: int = 30,
                 model_cost_data: Optional[Dict[str, float]] = None):
        """
        Initialize the cost optimizer.
        
        Args:
            min_data_points: Minimum number of data points needed for analysis
            analysis_period_days: Number of days to analyze
            model_cost_data: Optional dictionary of model costs per 1K tokens
        """
        self.min_data_points = min_data_points
        self.analysis_period_days = analysis_period_days
        self.request_history = []
        self.cost_by_model = defaultdict(float)
        self.cost_by_application = defaultdict(float)
        self.total_tokens_by_model = defaultdict(int)
        self.prompt_tokens_by_model = defaultdict(int)
        self.completion_tokens_by_model = defaultdict(int)
        self.request_count_by_model = defaultdict(int)
        self.model_cost_data = model_cost_data or self._default_model_costs()
        
        # Track common prompts
        self.prompt_fingerprints = defaultdict(list)
        self.max_fingerprints = 1000
        
        # Track usage patterns
        self.hourly_usage = defaultdict(lambda: defaultdict(int))
        self.daily_usage = defaultdict(lambda: defaultdict(int))
        
        # Track model performance
        self.model_latency = defaultdict(list)
        
        # Token efficiency metrics
        self.token_efficiency = {}
    
    def _default_model_costs(self) -> Dict[str, Dict[str, float]]:
        """
        Default cost data for common models.
        
        Returns:
            Dictionary of model costs per 1K tokens
        """
        return {
            # OpenAI models
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
            "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
            "gpt-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
            
            # Anthropic models
            "claude-2": {"prompt": 0.011, "completion": 0.0325},
            "claude-instant-1": {"prompt": 0.00163, "completion": 0.00551},
            
            # Cohere models
            "command": {"prompt": 0.0015, "completion": 0.0015},
            "command-light": {"prompt": 0.0003, "completion": 0.0003},
            
            # Google models
            "gemini-pro": {"prompt": 0.00025, "completion": 0.0005}
        }
    
    def add_request(self, request_data: Dict[str, Any]) -> None:
        """
        Add a request to the optimizer for analysis.
        
        Args:
            request_data: The request data to analyze
        """
        # Validate required fields
        required_fields = ["model", "prompt_tokens", "completion_tokens", "estimated_cost"]
        if not all(field in request_data for field in required_fields):
            logger.warning("Missing required fields in request data for cost optimization")
            return
        
        # Store the request
        self.request_history.append(request_data)
        
        # Trim old data if needed
        cutoff_date = datetime.now() - timedelta(days=self.analysis_period_days)
        self.request_history = [
            req for req in self.request_history 
            if req.get("timestamp", datetime.now()) >= cutoff_date
        ]
        
        # Update aggregations
        model = request_data["model"]
        application = request_data.get("application", "unknown")
        prompt_tokens = request_data["prompt_tokens"]
        completion_tokens = request_data.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = request_data["estimated_cost"]
        
        self.cost_by_model[model] += estimated_cost
        self.cost_by_application[application] += estimated_cost
        self.total_tokens_by_model[model] += total_tokens
        self.prompt_tokens_by_model[model] += prompt_tokens
        self.completion_tokens_by_model[model] += completion_tokens
        self.request_count_by_model[model] += 1
        
        # Update latency tracking
        if "inference_time" in request_data:
            self.model_latency[model].append(request_data["inference_time"])
            
            # Keep only recent latencies
            if len(self.model_latency[model]) > 1000:
                self.model_latency[model] = self.model_latency[model][-1000:]
        
        # Update usage patterns
        timestamp = request_data.get("timestamp", datetime.now())
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
            
        hour_key = timestamp.hour
        day_key = timestamp.weekday()
        
        self.hourly_usage[model][hour_key] += total_tokens
        self.daily_usage[model][day_key] += total_tokens
        
        # Update prompt fingerprinting for caching potential
        if "prompt" in request_data:
            self._update_prompt_fingerprints(model, request_data)
    
    def _update_prompt_fingerprints(self, model: str, request_data: Dict[str, Any]) -> None:
        """
        Update prompt fingerprints for caching analysis.
        
        Args:
            model: The model used
            request_data: The request data
        """
        # Simple fingerprinting by truncating and hashing the prompt
        prompt = request_data.get("prompt", "")
        if not prompt:
            return
            
        # Create a simple fingerprint
        try:
            import hashlib
            # Normalize whitespace and take first 100 chars
            normalized = " ".join(prompt[:100].split())
            fingerprint = hashlib.md5(normalized.encode('utf-8')).hexdigest()
            
            # Store with relevant metrics
            self.prompt_fingerprints[fingerprint].append({
                "model": model,
                "prompt_tokens": request_data["prompt_tokens"],
                "completion_tokens": request_data.get("completion_tokens", 0),
                "estimated_cost": request_data["estimated_cost"],
                "timestamp": request_data.get("timestamp", datetime.now())
            })
            
            # Limit number of fingerprints
            if len(self.prompt_fingerprints) > self.max_fingerprints:
                # Remove oldest or least frequent
                to_remove = min(
                    self.prompt_fingerprints.items(),
                    key=lambda x: len(x[1])
                )[0]
                del self.prompt_fingerprints[to_remove]
        except Exception as e:
            logger.warning(f"Error updating prompt fingerprints: {str(e)}")
    
    def get_optimization_insights(self) -> Dict[str, Any]:
        """
        Get comprehensive cost optimization insights.
        
        Returns:
            Dictionary of optimization insights
        """
        if len(self.request_history) < self.min_data_points:
            return {
                "status": "insufficient_data",
                "message": f"Need at least {self.min_data_points} requests for optimization analysis",
                "request_count": len(self.request_history)
            }
        
        # Calculate token efficiency
        self._calculate_token_efficiency()
        
        # Generate insights
        insights = {
            "status": "success",
            "request_count": len(self.request_history),
            "analysis_period_days": self.analysis_period_days,
            "total_cost": sum(self.cost_by_model.values()),
            "model_insights": self._get_model_insights(),
            "prompt_optimization": self._get_prompt_optimization_insights(),
            "caching_potential": self._analyze_caching_potential(),
            "usage_pattern_insights": self._get_usage_pattern_insights(),
            "model_alternatives": self._recommend_model_alternatives(),
            "batch_processing_opportunities": self._identify_batch_opportunities()
        }
        
        return insights
    
    def _calculate_token_efficiency(self) -> None:
        """Calculate token efficiency metrics for each model."""
        self.token_efficiency = {}
        
        for model, total_tokens in self.total_tokens_by_model.items():
            if self.request_count_by_model[model] == 0:
                continue
                
            prompt_tokens = self.prompt_tokens_by_model[model]
            completion_tokens = self.completion_tokens_by_model[model]
            
            # Skip if no completion tokens (error cases)
            if completion_tokens == 0:
                continue
                
            # Calculate metrics
            efficiency = {}
            
            # Prompt-to-completion ratio
            efficiency["prompt_to_completion_ratio"] = prompt_tokens / completion_tokens if completion_tokens > 0 else float('inf')
            
            # Tokens per request
            efficiency["tokens_per_request"] = total_tokens / self.request_count_by_model[model]
            
            # Cost per token
            if total_tokens > 0:
                efficiency["cost_per_token"] = self.cost_by_model[model] / total_tokens
            
            # Cost per request
            efficiency["cost_per_request"] = self.cost_by_model[model] / self.request_count_by_model[model]
            
            # Store efficiency metrics
            self.token_efficiency[model] = efficiency
    
    def _get_model_insights(self) -> List[Dict[str, Any]]:
        """
        Get insights for each model used.
        
        Returns:
            List of model insights
        """
        insights = []
        
        for model, cost in sorted(self.cost_by_model.items(), key=lambda x: x[1], reverse=True):
            if cost == 0 or self.request_count_by_model[model] == 0:
                continue
                
            total_tokens = self.total_tokens_by_model[model]
            prompt_tokens = self.prompt_tokens_by_model[model]
            completion_tokens = self.completion_tokens_by_model[model]
            request_count = self.request_count_by_model[model]
            
            # Calculate key metrics
            avg_tokens_per_request = total_tokens / request_count
            avg_cost_per_request = cost / request_count
            
            prompt_percentage = (prompt_tokens / total_tokens * 100) if total_tokens > 0 else 0
            
            # Calculate latency stats if available
            latency_stats = {}
            if model in self.model_latency and len(self.model_latency[model]) > 0:
                latencies = self.model_latency[model]
                latency_stats = {
                    "avg_inference_time": np.mean(latencies),
                    "p95_inference_time": np.percentile(latencies, 95),
                    "tokens_per_second": np.mean([
                        total_tokens / lat if lat > 0 else 0 
                        for (total_tokens, lat) in zip(
                            [self.prompt_tokens_by_model[model] + self.completion_tokens_by_model[model]] * len(latencies),
                            latencies
                        )
                    ])
                }
            
# Get efficiency metrics
            efficiency = self.token_efficiency.get(model, {})
            
            # Generate insight
            insight = {
                "model": model,
                "total_cost": cost,
                "total_tokens": total_tokens,
                "request_count": request_count,
                "avg_tokens_per_request": avg_tokens_per_request,
                "avg_cost_per_request": avg_cost_per_request,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "prompt_percentage": prompt_percentage,
                "efficiency_metrics": efficiency,
                "latency_stats": latency_stats
            }
            
            # Add optimization recommendations
            recommendations = []
            
            # Check for high prompt percentage
            if prompt_percentage > 75:
                recommendations.append({
                    "type": "high_prompt_ratio",
                    "message": "High percentage of tokens used by prompts. Consider prompt optimization.",
                    "severity": "high" if prompt_percentage > 85 else "medium",
                    "potential_savings": f"{(prompt_percentage - 60) / 100 * cost:.2f}"
                })
            
            # Check for inefficient token usage
            if avg_tokens_per_request < 100 and request_count > 50:
                recommendations.append({
                    "type": "low_token_utilization",
                    "message": "Low token utilization per request. Consider batching requests.",
                    "severity": "medium",
                    "potential_savings": "Depends on implementation."
                })
            
            # Add model-specific recommendations
            if "gpt-4" in model and request_count > 100:
                gpt35_savings = cost * 0.9  # Assuming 90% savings by switching models
                recommendations.append({
                    "type": "model_downgrade",
                    "message": "Consider using GPT-3.5 Turbo for less critical tasks.",
                    "severity": "high",
                    "potential_savings": f"{gpt35_savings:.2f}"
                })
            
            insight["recommendations"] = recommendations
            
            insights.append(insight)
        
        return insights
    
    def _get_prompt_optimization_insights(self) -> Dict[str, Any]:
        """
        Get insights on prompt optimization opportunities.
        
        Returns:
            Dictionary of prompt optimization insights
        """
        insights = {
            "high_token_prompts": [],
            "redundant_instructions": False,
            "excessive_examples": False,
            "recommendations": []
        }
        
        # Find high token prompts
        for req in self.request_history:
            if req.get("prompt_tokens", 0) > 1000:
                model = req.get("model", "unknown")
                insights["high_token_prompts"].append({
                    "model": model,
                    "prompt_tokens": req["prompt_tokens"],
                    "timestamp": req.get("timestamp", datetime.now()),
                    "request_id": req.get("request_id", "unknown")
                })
        
        # Look for patterns suggesting redundant instructions
        # This would require prompt text analysis, which we may not always have
        # For now, we'll use a simple heuristic: consistently high prompt tokens with low completion tokens
        high_ratio_models = []
        for model, efficiency in self.token_efficiency.items():
            ratio = efficiency.get("prompt_to_completion_ratio", 1.0)
            if ratio > 5.0 and self.request_count_by_model[model] > 50:
                high_ratio_models.append(model)
                insights["redundant_instructions"] = True
        
        # Generate recommendations
        if insights["high_token_prompts"]:
            insights["recommendations"].append({
                "type": "reduce_prompt_length",
                "message": "Consider reducing length of high token prompts to decrease costs.",
                "affected_models": list(set(p["model"] for p in insights["high_token_prompts"])),
                "severity": "high" if len(insights["high_token_prompts"]) > 10 else "medium"
            })
        
        if insights["redundant_instructions"]:
            insights["recommendations"].append({
                "type": "remove_redundant_instructions",
                "message": "High prompt-to-completion ratio suggests redundant instructions in prompts.",
                "affected_models": high_ratio_models,
                "severity": "high"
            })
        
        return insights
    
    def _analyze_caching_potential(self) -> Dict[str, Any]:
        """
        Analyze potential for response caching.
        
        Returns:
            Dictionary of caching insights
        """
        insights = {
            "repeated_prompts": [],
            "estimated_savings": 0.0,
            "cache_hit_potential": 0.0,
            "recommendations": []
        }
        
        # Find fingerprints with multiple occurrences
        repeated_prompts = []
        total_savings = 0.0
        
        for fingerprint, requests in self.prompt_fingerprints.items():
            if len(requests) > 1:
                # Calculate potential savings
                first_request = requests[0]  # We would cache this one
                subsequent_requests = requests[1:]  # These could be served from cache
                
                savings = sum(req["estimated_cost"] for req in subsequent_requests)
                total_savings += savings
                
                if savings > 0.01:  # Only report significant savings
                    repeated_prompts.append({
                        "occurrence_count": len(requests),
                        "model": first_request["model"],
                        "estimated_savings": savings,
                        "first_seen": first_request["timestamp"]
                    })
        
        # Sort by savings
        repeated_prompts.sort(key=lambda x: x["estimated_savings"], reverse=True)
        
        # Calculate cache hit potential
        total_requests = sum(self.request_count_by_model.values())
        if total_requests > 0:
            potentially_cached = sum(p["occurrence_count"] - 1 for p in repeated_prompts)
            cache_hit_potential = potentially_cached / total_requests
        else:
            cache_hit_potential = 0.0
        
        # Populate insights
        insights["repeated_prompts"] = repeated_prompts[:10]  # Top 10 repeated prompts
        insights["estimated_savings"] = total_savings
        insights["cache_hit_potential"] = cache_hit_potential
        
        # Generate recommendations
        if total_savings > 0:
            recommendation_severity = "high" if cache_hit_potential > 0.1 else "medium"
            insights["recommendations"].append({
                "type": "implement_response_caching",
                "message": f"Implement response caching for repeated prompts to save approximately ${total_savings:.2f}",
                "estimated_savings": total_savings,
                "cache_hit_rate": cache_hit_potential,
                "severity": recommendation_severity
            })
        
        return insights
    
    def _get_usage_pattern_insights(self) -> Dict[str, Any]:
        """
        Analyze usage patterns for optimization opportunities.
        
        Returns:
            Dictionary of usage pattern insights
        """
        insights = {
            "hourly_patterns": {},
            "daily_patterns": {},
            "peak_hours": [],
            "recommendations": []
        }
        
        # Process hourly patterns
        all_hours = {}
        for model, hours in self.hourly_usage.items():
            for hour, tokens in hours.items():
                all_hours[hour] = all_hours.get(hour, 0) + tokens
        
        # Find peak hours (top 20% of hours)
        if all_hours:
            total_tokens = sum(all_hours.values())
            sorted_hours = sorted(all_hours.items(), key=lambda x: x[1], reverse=True)
            
            cumulative = 0
            peak_hours = []
            for hour, tokens in sorted_hours:
                cumulative += tokens
                peak_hours.append(hour)
                if cumulative > 0.6 * total_tokens:  # Top hours accounting for 60% of usage
                    break
            
            insights["peak_hours"] = peak_hours
        
        # Get daily patterns
        all_days = {}
        for model, days in self.daily_usage.items():
            for day, tokens in days.items():
                all_days[day] = all_days.get(day, 0) + tokens
        
        # Normalize patterns
        if all_hours:
            total_hourly = sum(all_hours.values())
            insights["hourly_patterns"] = {str(h): t/total_hourly for h, t in all_hours.items()} if total_hourly > 0 else {}
        
        if all_days:
            total_daily = sum(all_days.values())
            insights["daily_patterns"] = {str(d): t/total_daily for d, t in all_days.items()} if total_daily > 0 else {}
        
        # Generate recommendations
        if peak_hours and len(peak_hours) <= 4:
            # Convert hour integers to readable time ranges
            peak_hour_ranges = []
            for hour in peak_hours:
                start_hour = f"{hour:02d}:00"
                end_hour = f"{(hour+1) % 24:02d}:00"
                peak_hour_ranges.append(f"{start_hour}-{end_hour}")
            
            insights["recommendations"].append({
                "type": "load_balancing",
                "message": f"High usage during peak hours ({', '.join(peak_hour_ranges)}). Consider load balancing.",
                "peak_hours": peak_hour_ranges,
                "severity": "medium"
            })
        
        return insights
    
    def _recommend_model_alternatives(self) -> List[Dict[str, Any]]:
        """
        Recommend alternative models to reduce costs.
        
        Returns:
            List of model alternative recommendations
        """
        recommendations = []
        
        # Define model alternatives with relative performance and cost
        alternatives = {
            "gpt-4": [
                {"name": "gpt-3.5-turbo", "cost_ratio": 0.05, "performance_ratio": 0.75},
                {"name": "claude-instant-1", "cost_ratio": 0.15, "performance_ratio": 0.80}
            ],
            "gpt-4-32k": [
                {"name": "gpt-4", "cost_ratio": 0.50, "performance_ratio": 0.95},
                {"name": "claude-2", "cost_ratio": 0.30, "performance_ratio": 0.85}
            ],
            "gpt-3.5-turbo-16k": [
                {"name": "gpt-3.5-turbo", "cost_ratio": 0.50, "performance_ratio": 0.95}
            ],
            "claude-2": [
                {"name": "claude-instant-1", "cost_ratio": 0.15, "performance_ratio": 0.80}
            ]
        }
        
        # Evaluate each currently used model
        for model, cost in self.cost_by_model.items():
            if model in alternatives and cost > 10.0:  # Only recommend alternatives for significant costs
                for alt in alternatives[model]:
                    potential_savings = cost * (1 - alt["cost_ratio"])
                    
                    # Only recommend if savings are significant
                    if potential_savings > 5.0:
                        recommendations.append({
                            "current_model": model,
                            "alternative_model": alt["name"],
                            "potential_savings": potential_savings,
                            "performance_impact": f"{(1 - alt['performance_ratio']) * 100:.1f}%",
                            "message": f"Consider replacing {model} with {alt['name']} for a ${potential_savings:.2f} cost reduction with {(1 - alt['performance_ratio']) * 100:.1f}% performance impact."
                        })
        
        # Sort by potential savings
        recommendations.sort(key=lambda x: x["potential_savings"], reverse=True)
        
        return recommendations
    
    def _identify_batch_opportunities(self) -> List[Dict[str, Any]]:
        """
        Identify opportunities for batch processing.
        
        Returns:
            List of batch processing recommendations
        """
        opportunities = []
        
        # Check for rapid sequential requests that could be batched
        # This would require temporal analysis of requests
        sequential_requests = self._find_sequential_requests()
        
        if sequential_requests:
            for model, seq_data in sequential_requests.items():
                if seq_data["count"] > 10:  # Only report significant batching opportunities
                    opportunities.append({
                        "model": model,
                        "request_count": seq_data["count"],
                        "avg_time_between": seq_data["avg_time_between"],
                        "potential_savings": seq_data["potential_savings"],
                        "message": f"Found {seq_data['count']} requests to {model} with average {seq_data['avg_time_between']:.2f}s between them. Consider batching."
                    })
        
        # Check for small requests that could be batched
        small_requests = self._find_small_requests()
        
        if small_requests:
            for model, count in small_requests.items():
                if count > 20:  # Only report significant opportunities
                    avg_tokens = self.total_tokens_by_model[model] / self.request_count_by_model[model]
                    
                    # Calculate potential token savings (assuming 20% overhead per request)
                    token_overhead = 0.2 * avg_tokens * count
                    cost_per_token = self.cost_by_model[model] / self.total_tokens_by_model[model]
                    potential_savings = token_overhead * cost_per_token
                    
                    opportunities.append({
                        "model": model,
                        "small_request_count": count,
                        "avg_tokens": avg_tokens,
                        "potential_savings": potential_savings,
                        "message": f"Found {count} small requests to {model} with {avg_tokens:.1f} tokens on average. Consider batching."
                    })
        
        return opportunities
    
    def _find_sequential_requests(self) -> Dict[str, Dict[str, Any]]:
        """
        Find sequential requests that could be batched.
        
        Returns:
            Dictionary of sequential request data by model
        """
        result = {}
        
        # Sort requests by timestamp
        sorted_requests = sorted(
            self.request_history, 
            key=lambda x: x.get("timestamp", datetime.now())
        )
        
        # Group by model
        model_requests = defaultdict(list)
        for req in sorted_requests:
            model = req.get("model", "unknown")
            model_requests[model].append(req)
        
        # Find sequential requests
        for model, requests in model_requests.items():
            if len(requests) < 5:  # Need at least a few requests
                continue
                
            sequential_count = 0
            time_diffs = []
            
            for i in range(1, len(requests)):
                prev_time = requests[i-1].get("timestamp", datetime.now())
                curr_time = requests[i].get("timestamp", datetime.now())
                
                # Convert to datetime if needed
                if isinstance(prev_time, (int, float)):
                    prev_time = datetime.fromtimestamp(prev_time)
                if isinstance(curr_time, (int, float)):
                    curr_time = datetime.fromtimestamp(curr_time)
                
                # Calculate time difference
                time_diff = (curr_time - prev_time).total_seconds()
                
                # If requests are close together
                if 0 < time_diff < 5:  # Within 5 seconds
                    sequential_count += 1
                    time_diffs.append(time_diff)
            
            # If we found sequential requests
            if sequential_count > 0 and time_diffs:
                avg_time_between = sum(time_diffs) / len(time_diffs)
                
                # Calculate potential savings
                # Batching would save on context overhead
                # Assuming 20% context overhead per request
                avg_tokens = self.total_tokens_by_model[model] / self.request_count_by_model[model]
                token_overhead = 0.2 * avg_tokens * sequential_count
                cost_per_token = self.cost_by_model[model] / self.total_tokens_by_model[model]
                potential_savings = token_overhead * cost_per_token
                
                result[model] = {
                    "count": sequential_count,
                    "avg_time_between": avg_time_between,
                    "potential_savings": potential_savings
                }
        
        return result
    
    def _find_small_requests(self) -> Dict[str, int]:
        """
        Find small requests that could be batched.
        
        Returns:
            Dictionary of small request counts by model
        """
        small_requests = defaultdict(int)
        
        # Define "small" based on model capabilities
        model_thresholds = {
            "gpt-4": 500,  # Tokens
            "gpt-3.5-turbo": 300,
            "claude-2": 500,
            "default": 200  # Default threshold
        }
        
        for req in self.request_history:
            model = req.get("model", "unknown")
            total_tokens = req.get("prompt_tokens", 0) + req.get("completion_tokens", 0)
            
            # Get threshold for this model
            threshold = model_thresholds.get(model, model_thresholds["default"])
            
            # If tokens are less than threshold
            if total_tokens < threshold:
                small_requests[model] += 1
        
        return small_requests