
# Storage optimization configuration for PostgreSQL
# File: infrastructure/config/postgres-optimization.sql

-- PostgreSQL optimization for SentinelOps

-- Enable table compression for historical data
ALTER TABLE request_metrics SET (
  autovacuum_vacuum_scale_factor = 0.05,
  autovacuum_analyze_scale_factor = 0.02,
  fillfactor = 80
);

-- Create time-based partitions for metrics data
CREATE TABLE request_metrics_partitioned (
    id SERIAL NOT NULL,
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
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions for the last year
DO $
DECLARE
   start_date TIMESTAMP := date_trunc('month', CURRENT_DATE - INTERVAL '1 year');
   end_date TIMESTAMP := date_trunc('month', CURRENT_DATE + INTERVAL '3 month');
   current_date TIMESTAMP := start_date;
   partition_name TEXT;
   start_str TEXT;
   end_str TEXT;
BEGIN
   WHILE current_date < end_date LOOP
       partition_name := 'request_metrics_p' || to_char(current_date, 'YYYY_MM');
       start_str := to_char(current_date, 'YYYY-MM-DD');
       end_str := to_char(current_date + INTERVAL '1 month', 'YYYY-MM-DD');
       
       EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF request_metrics_partitioned
                      FOR VALUES FROM (%L) TO (%L)', 
                      partition_name, start_str, end_str);
       
       current_date := current_date + INTERVAL '1 month';
   END LOOP;
END $;

-- Function to create future partitions automatically
CREATE OR REPLACE FUNCTION create_partition_and_insert() RETURNS trigger AS
$
DECLARE
   partition_date TIMESTAMP := date_trunc('month', NEW.timestamp);
   partition_name TEXT := 'request_metrics_p' || to_char(partition_date, 'YYYY_MM');
   start_str TEXT := to_char(partition_date, 'YYYY-MM-DD');
   end_str TEXT := to_char(partition_date + INTERVAL '1 month', 'YYYY-MM-DD');
BEGIN
   IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = partition_name) THEN
       EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF request_metrics_partitioned
                      FOR VALUES FROM (%L) TO (%L)', 
                      partition_name, start_str, end_str);
   END IF;
   RETURN NEW;
END;
$ LANGUAGE plpgsql;

-- Create the trigger
CREATE TRIGGER insert_request_metrics_trigger
    BEFORE INSERT ON request_metrics_partitioned
    FOR EACH ROW EXECUTE PROCEDURE create_partition_and_insert();

-- Create indexes on the partitioned table
CREATE INDEX IF NOT EXISTS request_metrics_part_request_id_idx ON request_metrics_partitioned(request_id);
CREATE INDEX IF NOT EXISTS request_metrics_part_timestamp_idx ON request_metrics_partitioned(timestamp);
CREATE INDEX IF NOT EXISTS request_metrics_part_model_idx ON request_metrics_partitioned(provider, model);
CREATE INDEX IF NOT EXISTS request_metrics_part_app_idx ON request_metrics_partitioned(application, environment);

-- Migration function for moving data to partitioned tables
CREATE OR REPLACE FUNCTION migrate_to_partitioned_tables(batch_size INT DEFAULT 10000)
RETURNS void AS $
DECLARE
    min_id BIGINT;
    max_id BIGINT;
    current_batch BIGINT;
    total_rows BIGINT;
    processed_rows BIGINT := 0;
    start_time TIMESTAMP;
    duration INTERVAL;
BEGIN
    -- Get min and max IDs
    SELECT MIN(id), MAX(id) INTO min_id, max_id FROM request_metrics;
    SELECT COUNT(*) INTO total_rows FROM request_metrics;
    
    -- Exit if no rows to process
    IF total_rows = 0 THEN
        RAISE NOTICE 'No rows to migrate.';
        RETURN;
    END IF;
    
    RAISE NOTICE 'Starting migration of % rows from request_metrics to request_metrics_partitioned', total_rows;
    start_time := clock_timestamp();
    
    -- Process in batches
    current_batch := min_id;
    WHILE current_batch <= max_id LOOP
        -- Insert batch
        INSERT INTO request_metrics_partitioned
        SELECT * FROM request_metrics
        WHERE id >= current_batch AND id < current_batch + batch_size;
        
        -- Update progress
        processed_rows := processed_rows + batch_size;
        IF processed_rows % 100000 = 0 THEN
            duration := clock_timestamp() - start_time;
            RAISE NOTICE 'Processed % rows (%.1f%%) in %', 
                processed_rows, 
                (processed_rows::float / total_rows) * 100,
                duration;
        END IF;
        
        -- Move to next batch
        current_batch := current_batch + batch_size;
        
        -- Commit batch
        COMMIT;
    END LOOP;
    
    duration := clock_timestamp() - start_time;
    RAISE NOTICE 'Migration completed in %', duration;
END;
$ LANGUAGE plpgsql;

-- Create data retention cleanup function
CREATE OR REPLACE FUNCTION cleanup_old_data() RETURNS void AS
$
DECLARE
    metrics_retention_days INTEGER;
    requests_retention_days INTEGER;
    anomalies_retention_days INTEGER;
    hallucinations_retention_days INTEGER;
    settings_record RECORD;
    partition_to_drop TEXT;
    retention_date DATE;
BEGIN
    -- Get retention settings
    SELECT * INTO settings_record FROM settings WHERE key = 'retention_policy';
    
    -- Extract retention periods
    metrics_retention_days := (settings_record.value->>'metrics_days')::INTEGER;
    requests_retention_days := (settings_record.value->>'requests_days')::INTEGER;
    anomalies_retention_days := (settings_record.value->>'anomalies_days')::INTEGER;
    hallucinations_retention_days := (settings_record.value->>'hallucinations_days')::INTEGER;
    
    -- Calculate retention date for metrics
    retention_date := CURRENT_DATE - metrics_retention_days;
    
    -- Drop old partitions
    FOR partition_to_drop IN 
        SELECT relname 
        FROM pg_class
        WHERE relname LIKE 'request_metrics_p%'
        AND relname < 'request_metrics_p' || to_char(retention_date, 'YYYY_MM')
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I', partition_to_drop);
        RAISE NOTICE 'Dropped partition %', partition_to_drop;
    END LOOP;
    
    -- Delete old data from other tables
    DELETE FROM anomalies
    WHERE timestamp < NOW() - (anomalies_retention_days || ' days')::INTERVAL;
    
    DELETE FROM hallucinations
    WHERE timestamp < NOW() - (hallucinations_retention_days || ' days')::INTERVAL;
    
    DELETE FROM alerts
    WHERE timestamp < NOW() - (anomalies_retention_days || ' days')::INTERVAL;
    
    -- Return success
    RETURN;
END;
$ LANGUAGE plpgsql;

-- Schedule the cleanup function
SELECT cron.schedule('0 1 * * *', $SELECT cleanup_old_data()$);

-- End of data optimization script

