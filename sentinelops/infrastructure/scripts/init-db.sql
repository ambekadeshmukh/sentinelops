-- scripts/init-db.sql

-- Create tables for LLM monitoring

-- Request Metrics Table: Stores core metrics for each LLM request
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

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS request_metrics_request_id_idx ON request_metrics(request_id);
CREATE INDEX IF NOT EXISTS request_metrics_timestamp_idx ON request_metrics(timestamp);
CREATE INDEX IF NOT EXISTS request_metrics_model_idx ON request_metrics(provider, model);
CREATE INDEX IF NOT EXISTS request_metrics_app_idx ON request_metrics(application, environment);

-- Anomalies Table: Stores detected anomalies
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

-- Create indexes for anomalies
CREATE INDEX IF NOT EXISTS anomalies_anomaly_id_idx ON anomalies(anomaly_id);
CREATE INDEX IF NOT EXISTS anomalies_timestamp_idx ON anomalies(timestamp);
CREATE INDEX IF NOT EXISTS anomalies_type_idx ON anomalies(type);
CREATE INDEX IF NOT EXISTS anomalies_request_id_idx ON anomalies(request_id);

-- Daily Aggregates: Pre-calculated daily statistics
CREATE TABLE IF NOT EXISTS daily_aggregates (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    provider VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL,
    application VARCHAR(255) NOT NULL,
    environment VARCHAR(255) NOT NULL,
    request_count INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    total_tokens BIGINT NOT NULL,
    total_cost FLOAT NOT NULL,
    avg_inference_time FLOAT NOT NULL,
    max_inference_time FLOAT NOT NULL,
    p95_inference_time FLOAT,
    p99_inference_time FLOAT
);

CREATE UNIQUE INDEX IF NOT EXISTS daily_aggregates_composite_idx 
ON daily_aggregates(date, provider, model, application, environment);

-- API Keys Table: For managing access to the monitoring API
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_name VARCHAR(255) NOT NULL,
    api_key VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS api_keys_api_key_idx ON api_keys(api_key);

-- Insert a default API key
INSERT INTO api_keys (key_name, api_key) 
VALUES ('default', 'test-api-key')
ON CONFLICT DO NOTHING;

-- Settings Table: For configuration
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert default settings
INSERT INTO settings (key, value)
VALUES 
    ('anomaly_thresholds', '{"inference_time": 5.0, "error_rate": 0.1, "token_usage": 1000}'),
    ('retention_policy', '{"metrics_days": 90, "requests_days": 30, "anomalies_days": 180}')
ON CONFLICT DO NOTHING;

-- Alerts Table: For tracking sent alerts
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    type VARCHAR(255) NOT NULL,
    anomaly_id VARCHAR(255),
    message TEXT NOT NULL,
    sent_to JSONB,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS alerts_timestamp_idx ON alerts(timestamp);
CREATE INDEX IF NOT EXISTS alerts_type_idx ON alerts(type);

-- Functions and Procedures

-- Function to aggregate daily metrics (to be run by a scheduler)
CREATE OR REPLACE FUNCTION aggregate_daily_metrics(target_date DATE)
RETURNS VOID AS $$
BEGIN
    -- Delete existing aggregates for the day
    DELETE FROM daily_aggregates 
    WHERE date = target_date;
    
    -- Insert aggregated data
    INSERT INTO daily_aggregates (
        date,
        provider,
        model,
        application,
        environment,
        request_count,
        success_count,
        error_count,
        total_tokens,
        total_cost,
        avg_inference_time,
        max_inference_time,
        p95_inference_time,
        p99_inference_time
    )
    SELECT
        target_date as date,
        provider,
        model,
        application,
        environment,
        COUNT(*) as request_count,
        SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
        SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count,
        SUM(COALESCE(total_tokens, 0)) as total_tokens,
        SUM(COALESCE(estimated_cost, 0)) as total_cost,
        AVG(inference_time) as avg_inference_time,
        MAX(inference_time) as max_inference_time,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY inference_time) as p95_inference_time,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY inference_time) as p99_inference_time
    FROM request_metrics
    WHERE timestamp::DATE = target_date
    GROUP BY provider, model, application, environment;
    
    -- Return success
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old data based on retention policy
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS VOID AS $$
DECLARE
    metrics_retention_days INTEGER;
    requests_retention_days INTEGER;
    anomalies_retention_days INTEGER;
    settings_record RECORD;
BEGIN
    -- Get retention settings
    SELECT * INTO settings_record FROM settings WHERE key = 'retention_policy';
    
    -- Extract retention periods
    metrics_retention_days := (settings_record.value->>'metrics_days')::INTEGER;
    requests_retention_days := (settings_record.value->>'requests_days')::INTEGER;
    anomalies_retention_days := (settings_record.value->>'anomalies_days')::INTEGER;
    
    -- Delete old data from metrics table
    DELETE FROM request_metrics
    WHERE timestamp < NOW() - (metrics_retention_days || ' days')::INTERVAL;
    
    -- Delete old request/response objects from MinIO (this would be handled in application code)
    
    -- Delete old anomalies
    DELETE FROM anomalies
    WHERE timestamp < NOW() - (anomalies_retention_days || ' days')::INTERVAL;
    
    -- Delete old alerts
    DELETE FROM alerts
    WHERE timestamp < NOW() - (anomalies_retention_days || ' days')::INTERVAL;
    
    -- Return success
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- Views for easier queries

-- Request metrics with error rate
CREATE OR REPLACE VIEW request_metrics_summary AS
SELECT
    date_trunc('hour', timestamp) as time_bucket,
    provider,
    model,
    application,
    environment,
    COUNT(*) as request_count,
    SUM(CASE WHEN success THEN 0 ELSE 1 END) as error_count,
    SUM(CASE WHEN success THEN 0 ELSE 1 END)::FLOAT / COUNT(*) as error_rate,
    AVG(inference_time) as avg_inference_time,
    SUM(COALESCE(total_tokens, 0)) as total_tokens,
    SUM(COALESCE(estimated_cost, 0)) as total_cost
FROM request_metrics
GROUP BY time_bucket, provider, model, application, environment;

-- Sample data for testing (uncomment to use)
/*
-- Insert sample providers and models
INSERT INTO request_metrics (
    request_id, timestamp, provider, model, application, environment,
    inference_time, success, prompt_tokens, completion_tokens, total_tokens,
    estimated_cost, memory_used
)
SELECT
    'req-' || generate_series::text as request_id,
    now() - (random() * interval '24 hours') as timestamp,
    CASE WHEN random() < 0.7 THEN 'openai' ELSE 'anthropic' END as provider,
    CASE 
        WHEN random() < 0.5 THEN 'gpt-3.5-turbo'
        WHEN random() < 0.8 THEN 'gpt-4' 
        ELSE 'claude-instant-1'
    END as model,
    CASE 
        WHEN random() < 0.6 THEN 'chatbot'
        WHEN random() < 0.8 THEN 'content-generator' 
        ELSE 'summarization'
    END as application,
    CASE WHEN random() < 0.8 THEN 'production' ELSE 'development' END as environment,
    random() * 5 as inference_time,
    random() < 0.95 as success,
    floor(random() * 500 + 10)::integer as prompt_tokens,
    floor(random() * 1000 + 50)::integer as completion_tokens,
    floor(random() * 1500 + 60)::integer as total_tokens,
    random() * 0.05 as estimated_cost,
    random() * 200 + 50 as memory_used
FROM generate_series(1, 1000);

-- Insert some errors
UPDATE request_metrics
SET 
    success = false,
    error = CASE 
        WHEN random() < 0.3 THEN 'Rate limit exceeded'
        WHEN random() < 0.6 THEN 'Context length exceeded'
        ELSE 'Internal server error'
    END,
    completion_tokens = null,
    total_tokens = prompt_tokens
WHERE random() < 0.05;

-- Insert some anomalies
INSERT INTO anomalies (
    anomaly_id, timestamp, type, request_id, provider, model, application, details
)
SELECT
    'anom-' || generate_series::text as anomaly_id,
    now() - (random() * interval '24 hours') as timestamp,
    CASE 
        WHEN random() < 0.7 THEN 'inference_time_spike'
        ELSE 'error_rate_spike'
    END as type,
    'req-' || floor(random() * 1000 + 1)::text as request_id,
    CASE WHEN random() < 0.7 THEN 'openai' ELSE 'anthropic' END as provider,
    CASE 
        WHEN random() < 0.5 THEN 'gpt-3.5-turbo'
        WHEN random() < 0.8 THEN 'gpt-4' 
        ELSE 'claude-instant-1'
    END as model,
    CASE 
        WHEN random() < 0.6 THEN 'chatbot'
        WHEN random() < 0.8 THEN 'content-generator' 
        ELSE 'summarization'
    END as application,
    CASE 
        WHEN random() < 0.7 THEN 
            json_build_object(
                'value', random() * 10, 
                'threshold', 5.0,
                'mean', random() * 3,
                'z_score', random() * 5 + 3
            )
        ELSE 
            json_build_object(
                'count', floor(random() * 20 + 5)::integer,
                'errors', array['Rate limit exceeded', 'Context length exceeded']
            )
    END as details
FROM generate_series(1, 50);
*/