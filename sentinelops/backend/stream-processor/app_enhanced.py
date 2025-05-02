# sentinelops/backend/stream-processor/app_enhanced.py
import os
import json
import time
import logging
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from kafka import KafkaConsumer
import minio
import uuid
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading

# Import our processors
from processors.advanced_anomaly_detector import AdvancedAnomalyDetector
from processors.hallucination_detector import HallucinationDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stream-processor")

# Configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "llm-monitoring")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "llmmonitor")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "llmmonitor")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "llmmonitor")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "llm-requests")

class EnhancedStreamProcessor:
    """Enhanced process for LLM monitoring events with advanced analytics."""
    
    def __init__(self):
        self.connect_kafka()
        self.connect_postgres()
        self.connect_minio()
        
        # Initialize the advanced processors
        self.anomaly_detector = AdvancedAnomalyDetector(
            window_size=100,
            lookback_period=1000,
            alert_sensitivity=3.0,
            min_data_points=30
        )
        
        self.hallucination_detector = HallucinationDetector()
        
        # Start periodic analysis thread
        self.stop_periodic_analysis = False
        self.periodic_thread = threading.Thread(target=self._run_periodic_analysis)
        self.periodic_thread.daemon = True
        self.periodic_thread.start()
        
    def connect_kafka(self):
        """Connect to Kafka broker."""
        logger.info(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")
        self.consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            group_id='llm-stream-processor',
            enable_auto_commit=True,
            auto_commit_interval_ms=5000
        )
        logger.info("Connected to Kafka")
        
    def connect_postgres(self):
        """Connect to PostgreSQL database."""
        logger.info(f"Connecting to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}")
        self.conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            dbname=POSTGRES_DB
        )
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        # Create hallucinations table if it doesn't exist
        self._create_hallucinations_table()
        
        logger.info("Connected to PostgreSQL")
        
    def _create_hallucinations_table(self):
        """Create the hallucinations table if it doesn't exist."""
        try:
            self.cursor.execute("""
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
                CREATE INDEX IF NOT EXISTS hallucinations_model_idx ON hallucinations(provider, model);
                CREATE INDEX IF NOT EXISTS hallucinations_detected_idx ON hallucinations(hallucination_detected);
            """)
            self.conn.commit()
            logger.info("Hallucinations table created or already exists")
        except Exception as e:
            logger.error(f"Error creating hallucinations table: {str(e)}", exc_info=True)
            self.conn.rollback()
        
    def connect_minio(self):
        """Connect to MinIO object storage."""
        logger.info(f"Connecting to MinIO at {MINIO_ENDPOINT}")
        self.minio_client = minio.Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False  # Set to True if using HTTPS
        )
        
        # Create bucket if it doesn't exist
        if not self.minio_client.bucket_exists(MINIO_BUCKET):
            self.minio_client.make_bucket(MINIO_BUCKET)
            logger.info(f"Created MinIO bucket: {MINIO_BUCKET}")
        
        logger.info("Connected to MinIO")
        
    def store_request_response(self, data: Dict[str, Any]) -> str:
        """Store full request/response in MinIO and return the object ID."""
        # Only store if prompt or completion is included
        if "prompt" not in data and "completion" not in data:
            return None
            
        object_id = f"{data['request_id']}.json"
        
        # Create a filtered copy with just the request/response data
        storage_data = {
            "request_id": data["request_id"],
            "timestamp": data["timestamp"],
            "provider": data["provider"],
            "model": data["model"]
        }
        
        if "prompt" in data:
            storage_data["prompt"] = data["prompt"]
            
        if "completion" in data:
            storage_data["completion"] = data["completion"]
        
        # Convert to JSON and store in MinIO
        json_data = json.dumps(storage_data).encode('utf-8')
        self.minio_client.put_object(
            bucket_name=MINIO_BUCKET,
            object_name=object_id,
            data=json.dumps(storage_data).encode('utf-8'),
            length=len(json_data),
            content_type="application/json"
        )
        
        return object_id
        
    def process_event(self, data: Dict[str, Any]):
        """Process a single monitoring event."""
        try:
            # Store request/response data if present
            object_id = self.store_request_response(data)
            
            # Extract metrics for storage and analysis
            metrics = {
                "request_id": data["request_id"],
                "timestamp": datetime.fromtimestamp(data["timestamp"]),
                "provider": data["provider"],
                "model": data["model"],
                "application": data["application"],
                "environment": data["environment"],
                "inference_time": data["inference_time"],
                "success": data["success"],
                "prompt_tokens": data["prompt_tokens"],
                "memory_used": data.get("memory_used", 0),
                "storage_object_id": object_id
            }
            
            # Add completion tokens if successful
            if data["success"] and "completion_tokens" in data:
                metrics["completion_tokens"] = data["completion_tokens"] 
                metrics["total_tokens"] = data["total_tokens"]
                metrics["estimated_cost"] = data["estimated_cost"]
            
            # Add error info if failed
            if not data["success"] and "error" in data:
                metrics["error"] = data["error"]
            
            # Insert metrics into database
            self.store_metrics(metrics)
            
            # Update anomaly detector with new metrics
            self._update_anomaly_detector(metrics, data)
            
            # Check for anomalies
            anomalies = self.anomaly_detector.detect_anomalies(metrics)
            if anomalies:
                self.report_anomalies(metrics, anomalies)
                
            # Check for hallucinations if we have completion text
            if data["success"] and "completion" in data and data["completion"]:
                prompt = data.get("prompt", None)
                self._check_hallucinations(data["request_id"], data["completion"], prompt, metrics)
                
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}", exc_info=True)
    
    def store_metrics(self, metrics: Dict[str, Any]):
        """Store metrics in PostgreSQL."""
        columns = list(metrics.keys())
        values = [metrics[col] for col in columns]
        placeholders = ["%s"] * len(columns)
        
        query = f"""
        INSERT INTO request_metrics ({', '.join(columns)})
        VALUES ({', '.join(placeholders)})
        """
        
        self.cursor.execute(query, values)
        self.conn.commit()
    
    def _update_anomaly_detector(self, metrics: Dict[str, Any], raw_data: Dict[str, Any]):
        """Update the anomaly detector with new metrics."""
        # Add inference time metric
        self.anomaly_detector.add_metric(
            metric_type="inference_time",
            value=metrics["inference_time"],
            metadata=metrics
        )
        
        # Add token metrics if available
        if "total_tokens" in metrics:
            self.anomaly_detector.add_metric(
                metric_type="total_tokens",
                value=metrics["total_tokens"],
                metadata=metrics
            )
            
        # Add cost metrics if available
        if "estimated_cost" in metrics:
            self.anomaly_detector.add_metric(
                metric_type="estimated_cost",
                value=metrics["estimated_cost"],
                metadata=metrics
            )
            
        # Add memory usage if available
        if "memory_used" in metrics:
            self.anomaly_detector.add_metric(
                metric_type="memory_used",
                value=metrics["memory_used"],
                metadata=metrics
            )
    
    def report_anomalies(self, metrics: Dict[str, Any], anomalies: List[Dict[str, Any]]):
        """Report detected anomalies to the database."""
        for anomaly in anomalies:
            anomaly_id = anomaly.get("anomaly_id", str(uuid.uuid4()))
            anomaly_type = anomaly.get("type", "unknown")
            
            # Store anomaly in database
            self.cursor.execute(
                """
                INSERT INTO anomalies 
                (anomaly_id, timestamp, type, request_id, provider, model, application, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    anomaly_id,
                    metrics["timestamp"],
                    anomaly_type,
                    metrics["request_id"],
                    metrics["provider"],
                    metrics["model"],
                    metrics["application"],
                    Json(anomaly)
                )
            )
            self.conn.commit()
            
            logger.warning(f"Anomaly detected: {anomaly_type} for request {metrics['request_id']}")
    
    def _check_hallucinations(
        self, 
        request_id: str, 
        completion: str, 
        prompt: str = None, 
        metrics: Dict[str, Any] = None
    ):
        """Check for hallucinations in the completion."""
        try:
            # Skip very short completions
            if len(completion) < 20:
                return
                
            # Analyze for hallucinations
            analysis = self.hallucination_detector.detect_hallucinations(
                completion=completion,
                prompt=prompt,
                metadata=metrics
            )
            
            # Only store in database if we have a meaningful result
            if analysis["score"] > 0:
                hallucination_id = str(uuid.uuid4())
                
                # Store the analysis results
                self.cursor.execute(
                    """
                    INSERT INTO hallucinations (
                        hallucination_id, request_id, timestamp, provider, model, 
                        application, environment, hallucination_detected, confidence, 
                        score, reasons, component_scores
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        hallucination_id,
                        request_id,
                        metrics["timestamp"],
                        metrics["provider"],
                        metrics["model"],
                        metrics["application"],
                        metrics["environment"],
                        analysis["hallucination_detected"],
                        analysis["confidence"],
                        analysis["score"],
                        Json(analysis["reasons"]),
                        Json(analysis["component_scores"])
                    )
                )
                self.conn.commit()
                
                # If high confidence hallucination, report as an anomaly
                if analysis["hallucination_detected"] and analysis["confidence"] == "high":
                    anomaly_id = str(uuid.uuid4())
                    anomaly = {
                        "type": "potential_hallucination",
                        "anomaly_id": anomaly_id,
                        "hallucination_id": hallucination_id,
                        "score": analysis["score"],
                        "confidence": analysis["confidence"],
                        "reasons": [reason["type"] for reason in analysis["reasons"]]
                    }
                    
                    self.cursor.execute(
                        """
                        INSERT INTO anomalies 
                        (anomaly_id, timestamp, type, request_id, provider, model, application, details)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            anomaly_id,
                            metrics["timestamp"],
                            "potential_hallucination",
                            request_id,
                            metrics["provider"],
                            metrics["model"],
                            metrics["application"],
                            Json(anomaly)
                        )
                    )
                    self.conn.commit()
                    
                    logger.warning(f"Hallucination detected with high confidence for request {request_id}")
                
        except Exception as e:
            logger.error(f"Error checking for hallucinations: {str(e)}", exc_info=True)
    
    def _run_periodic_analysis(self):
        """Run periodic analysis in a separate thread."""
        while not self.stop_periodic_analysis:
            try:
                # Run the periodic analysis
                anomalies = self.anomaly_detector.perform_periodic_analysis()
                
                # Report any detected anomalies
                for anomaly in anomalies:
                    anomaly_id = anomaly.get("anomaly_id", str(uuid.uuid4()))
                    anomaly_type = anomaly.get("type", "unknown")
                    
                    # Prepare the metadata for this anomaly
                    provider = anomaly.get("provider", "unknown")
                    model = anomaly.get("model", "unknown")
                    application = anomaly.get("application", "unknown")
                    timestamp = anomaly.get("timestamp", datetime.now())
                    
                    # Generate a request ID if not present
                    request_id = anomaly.get("request_id", f"periodic-{str(uuid.uuid4())}")
                    
                    # Store anomaly in database
                    self.cursor.execute(
                        """
                        INSERT INTO anomalies 
                        (anomaly_id, timestamp, type, request_id, provider, model, application, details)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            anomaly_id,
                            timestamp,
                            anomaly_type,
                            request_id,
                            provider,
                            model,
                            application,
                            Json(anomaly)
                        )
                    )
                    self.conn.commit()
                    
                    logger.warning(f"Periodic analysis detected anomaly: {anomaly_type}")
                
            except Exception as e:
                logger.error(f"Error in periodic analysis: {str(e)}", exc_info=True)
            
            # Sleep for 30 minutes before the next analysis
            for _ in range(30 * 60):  # 30 minutes in seconds
                if self.stop_periodic_analysis:
                    break
                time.sleep(1)
    
    def run(self):
        """Main processing loop."""
        logger.info("Starting enhanced stream processing loop")
        
        try:
            for message in self.consumer:
                data = message.value
                self.process_event(data)
        except KeyboardInterrupt:
            logger.info("Shutting down stream processor")
        except Exception as e:
            logger.error(f"Error in processing loop: {str(e)}", exc_info=True)
        finally:
            self.close()
    
    def close(self):
        """Clean up resources."""
        # Signal the periodic thread to stop
        self.stop_periodic_analysis = True
        
        # Wait for the thread to finish
        if self.periodic_thread.is_alive():
            self.periodic_thread.join(timeout=5)
        
        # Close database connection
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            
        # Close Kafka consumer
        if hasattr(self, 'consumer') and self.consumer:
            self.consumer.close()

if __name__ == "__main__":
    processor = EnhancedStreamProcessor()
    processor.run()