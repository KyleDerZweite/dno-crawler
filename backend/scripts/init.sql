-- DNO Crawler Database Initialization Script
-- This script runs on first database creation.
-- All table creation is handled by SQLAlchemy ORM models.
-- This file only creates extensions and utility functions.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create updated_at trigger function for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Note: All tables are created by SQLAlchemy's create_all() in app/db/database.py
-- Admin user is seeded from environment variables at application startup.
