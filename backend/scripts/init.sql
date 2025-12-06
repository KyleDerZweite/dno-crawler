-- DNO Crawler Database Initialization Script
-- Run this after database creation

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
-- Note: user_role is handled as VARCHAR by SQLAlchemy ORM, not as ENUM

DO $$ BEGIN
    CREATE TYPE crawl_status AS ENUM ('pending', 'running', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE voltage_level AS ENUM ('NS', 'MS', 'HS', 'HöS', 'MS/NS', 'HS/MS', 'HöS/HS');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL DEFAULT 'admin',
    email_verified BOOLEAN NOT NULL DEFAULT false,
    verification_status VARCHAR(50) NOT NULL DEFAULT 'awaiting_approval',
    approved_by INTEGER,
    approved_at TIMESTAMPTZ,
    role VARCHAR(20) NOT NULL DEFAULT 'pending',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Create DNOs table
CREATE TABLE IF NOT EXISTS dnos (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    homepage_url TEXT,
    netzentgelt_url TEXT,
    bundesland VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_crawled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create netzentgelte table
CREATE TABLE IF NOT EXISTS netzentgelte (
    id SERIAL PRIMARY KEY,
    dno_id INTEGER NOT NULL REFERENCES dnos(id) ON DELETE CASCADE,
    plz VARCHAR(5) NOT NULL,
    ort VARCHAR(255),
    spannungsebene voltage_level,
    arbeitspreis_ht DECIMAL(10, 5),
    arbeitspreis_nt DECIMAL(10, 5),
    grundpreis DECIMAL(10, 2),
    leistungspreis DECIMAL(10, 2),
    gueltig_ab DATE NOT NULL,
    gueltig_bis DATE,
    source_url TEXT,
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create HLZF (Hochlastzeitfenster) table
CREATE TABLE IF NOT EXISTS hlzf (
    id SERIAL PRIMARY KEY,
    dno_id INTEGER NOT NULL REFERENCES dnos(id) ON DELETE CASCADE,
    plz VARCHAR(5),
    winter_start TIME,
    winter_end TIME,
    summer_start TIME,
    summer_end TIME,
    notes TEXT,
    gueltig_ab DATE NOT NULL,
    gueltig_bis DATE,
    source_url TEXT,
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create extraction_strategies table (for learning system)
CREATE TABLE IF NOT EXISTS extraction_strategies (
    id SERIAL PRIMARY KEY,
    dno_id INTEGER NOT NULL REFERENCES dnos(id) ON DELETE CASCADE,
    strategy_type VARCHAR(50) NOT NULL, -- 'table', 'pdf', 'api', 'javascript'
    selector_config JSONB NOT NULL, -- CSS selectors, XPath, etc.
    success_rate DECIMAL(5, 2) DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create crawl_jobs table
CREATE TABLE IF NOT EXISTS crawl_jobs (
    id SERIAL PRIMARY KEY,
    dno_id INTEGER NOT NULL REFERENCES dnos(id) ON DELETE CASCADE,
    strategy_id INTEGER REFERENCES extraction_strategies(id),
    status crawl_status NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    records_extracted INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create crawl_attempts table (for learning from failures)
CREATE TABLE IF NOT EXISTS crawl_attempts (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    strategy_id INTEGER REFERENCES extraction_strategies(id),
    success BOOLEAN NOT NULL,
    response_status INTEGER,
    error_type VARCHAR(100),
    error_message TEXT,
    duration_ms INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_netzentgelte_plz ON netzentgelte(plz);
CREATE INDEX IF NOT EXISTS idx_netzentgelte_dno ON netzentgelte(dno_id);
CREATE INDEX IF NOT EXISTS idx_netzentgelte_dates ON netzentgelte(gueltig_ab, gueltig_bis);
CREATE INDEX IF NOT EXISTS idx_hlzf_dno ON hlzf(dno_id);
CREATE INDEX IF NOT EXISTS idx_hlzf_plz ON hlzf(plz);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status ON crawl_jobs(status);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_dno ON crawl_jobs(dno_id);
CREATE INDEX IF NOT EXISTS idx_extraction_strategies_dno ON extraction_strategies(dno_id);

-- Insert default admin user (password: admin123 - CHANGE IN PRODUCTION!)
-- Default admin user is created by the backend at startup when
-- `ADMIN_EMAIL` and `ADMIN_PASSWORD` are provided via environment variables.
-- This prevents committing plaintext credentials to the DB initialization script.

-- Insert some sample DNOs
INSERT INTO dnos (name, homepage_url, netzentgelt_url, bundesland) VALUES
('Netze BW GmbH', 'https://www.netze-bw.de', 'https://www.netze-bw.de/netzentgelte', 'Baden-Württemberg'),
('Stromnetz Berlin GmbH', 'https://www.stromnetz.berlin', 'https://www.stromnetz.berlin/netzentgelte', 'Berlin'),
('Bayernwerk Netz GmbH', 'https://www.bayernwerk-netz.de', 'https://www.bayernwerk-netz.de/netzentgelte', 'Bayern'),
('E.DIS Netz GmbH', 'https://www.e-dis-netz.de', 'https://www.e-dis-netz.de/netzentgelte', 'Brandenburg'),
('Westnetz GmbH', 'https://www.westnetz.de', 'https://www.westnetz.de/netzentgelte', 'Nordrhein-Westfalen')
ON CONFLICT DO NOTHING;

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to tables
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_dnos_updated_at ON dnos;
CREATE TRIGGER update_dnos_updated_at
    BEFORE UPDATE ON dnos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_netzentgelte_updated_at ON netzentgelte;
CREATE TRIGGER update_netzentgelte_updated_at
    BEFORE UPDATE ON netzentgelte
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_hlzf_updated_at ON hlzf;
CREATE TRIGGER update_hlzf_updated_at
    BEFORE UPDATE ON hlzf
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_extraction_strategies_updated_at ON extraction_strategies;
CREATE TRIGGER update_extraction_strategies_updated_at
    BEFORE UPDATE ON extraction_strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;
