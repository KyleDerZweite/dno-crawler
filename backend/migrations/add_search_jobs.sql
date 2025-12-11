-- Migration: Add search_jobs table for natural language search with timeline UI
-- 
-- Run this migration with: psql -d dno_crawler -f add_search_jobs.sql
-- Or via Docker: docker exec -i dno-db psql -U dno -d dno_crawler < add_search_jobs.sql
-- 
-- Note: If using init_db() with create_all(), this table will be created automatically.
-- This migration is provided for manual/incremental deployments.

BEGIN;

CREATE TABLE IF NOT EXISTS search_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    
    -- Input
    input_text TEXT NOT NULL,
    filters JSONB DEFAULT '{}',
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    current_step VARCHAR(255),
    
    -- Step History (JSON array for timeline UI)
    steps_history JSONB DEFAULT '[]',
    
    -- Result
    result JSONB,
    error_message TEXT,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_search_jobs_user_created 
    ON search_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_jobs_status 
    ON search_jobs(status) WHERE status IN ('pending', 'running');

COMMIT;

SELECT 'Migration complete: search_jobs table created' as result;
