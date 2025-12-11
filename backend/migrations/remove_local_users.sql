-- Migration: Remove local user management tables
-- Users are now managed in Zitadel
-- 
-- Run this migration with: psql -d dno_crawler -f remove_local_users.sql
-- Or via Docker: docker exec -i dno-db psql -U dno -d dno_crawler < remove_local_users.sql

BEGIN;

-- First, remove FKs from other tables that reference users
-- These columns can stay but just won't have a FK constraint

-- Remove FK from netzentgelte.verified_by (but keep the column for audit trail)
ALTER TABLE netzentgelte DROP CONSTRAINT IF EXISTS netzentgelte_verified_by_fkey;

-- Remove FK from hlzf.verified_by (but keep the column for audit trail)
ALTER TABLE hlzf DROP CONSTRAINT IF EXISTS hlzf_verified_by_fkey;

-- Remove FK from crawl_jobs.user_id (but keep the column for audit trail)
ALTER TABLE crawl_jobs DROP CONSTRAINT IF EXISTS crawl_jobs_user_id_fkey;

-- Remove FK from query_logs.user_id (but keep the column for audit trail)
ALTER TABLE query_logs DROP CONSTRAINT IF EXISTS query_logs_user_id_fkey;

-- Now we can safely drop the user-related tables
-- Order matters due to FK between users and the other tables

-- Drop sessions table (FK to users)
DROP TABLE IF EXISTS sessions CASCADE;

-- Drop api_keys table (FK to users)
DROP TABLE IF EXISTS api_keys CASCADE;

-- Drop users table
DROP TABLE IF EXISTS users CASCADE;

COMMIT;

-- Output success message
SELECT 'Migration complete: users, sessions, api_keys tables dropped' as result;
