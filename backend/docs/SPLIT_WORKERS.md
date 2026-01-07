# Split Worker Architecture

This document describes the split crawl/extract worker architecture introduced for more efficient job processing.

## Overview

The job pipeline is now split into two independent workers:

1. **Crawl Worker** (`worker-crawl`): Handles discovery and downloading (steps 0-3)
2. **Extract Worker** (`worker-extract`): Handles extraction, validation, and finalization (steps 4-6)

## Why Split?

| Phase | Resource Profile | Constraint |
|-------|------------------|------------|
| Crawl (steps 0-3) | I/O bound (network) | Must be polite - 0.5-1.5s delays between requests |
| Extract (steps 4-6) | CPU/API bound | AI extraction can be slow, but parallelizable |

**Benefits:**
- Crawl delays don't block extraction work
- AI rate limits don't block crawl discovery
- Better queue visibility (see crawl vs extract backlogs separately)
- Extract workers can be scaled horizontally

## Job Types

| Type | Steps | Queue | Use Case |
|------|-------|-------|----------|
| `full` | 0-6 | `default` | Legacy - runs all steps in sequence |
| `crawl` | 0-3 | `crawl` | Only discover and download file |
| `extract` | 4-6 | `extract` | Only process an existing file |

## How It Works

### Full Pipeline (default behavior)
1. User triggers a job → API creates `job_type: 'crawl'` job
2. Crawl worker executes steps 0-3
3. On success, crawl job creates a new `job_type: 'extract'` job
4. Extract worker picks up and runs steps 4-6
5. Jobs are linked via `parent_job_id` / `child_job_id`

### Crawl Only
- Use case: Just want to download files for later processing
- Set `job_type: 'crawl'` in trigger request
- After completion, you can trigger extract later

### Extract Only
- Use case: File already exists locally (uploaded or previously crawled)
- Set `job_type: 'extract'` in trigger request
- Requires a file at `data/downloads/{slug}/{slug}-{type}-{year}.{ext}`

## Configuration

### Docker Compose Workers

```yaml
# Crawl worker - ONE ONLY for polite crawling
worker-crawl:
  command: arq app.jobs.CrawlWorkerSettings
  
# Extract worker - can scale if needed
worker-extract:
  command: arq app.jobs.ExtractWorkerSettings
```

### ARQ Settings

```python
class CrawlWorkerSettings:
    queue_name = "crawl"
    max_jobs = 1  # Only 1 for polite crawling

class ExtractWorkerSettings:
    queue_name = "extract"
    max_jobs = 1  # Can increase if CPU allows
```

## Database Changes

New columns on `crawl_jobs` table:
- `job_type` - 'full', 'crawl', or 'extract'
- `parent_job_id` - For extract jobs, links to parent crawl job
- `child_job_id` - For crawl jobs, links to spawned extract job

Run migration for existing databases:
```bash
psql -d dno_crawler -f backend/scripts/migrations/001_add_job_type.sql
```

## API Changes

The `POST /dnos/{id}/crawl` endpoint now accepts:
```json
{
  "year": 2025,
  "data_type": "netzentgelte",
  "job_type": "full"  // or "crawl" or "extract"
}
```

Response includes:
```json
{
  "job_id": "123",
  "job_type": "crawl",
  "status": "pending"
}
```

## Frontend

The trigger dialog now has Advanced Options with:
- **Job Type Selection**: Full Pipeline, Crawl Only, Extract Only
- Extract Only shows a note that it requires an existing file

Jobs page shows:
- Job type badge (Full/Crawl/Extract)
- Links to parent/child jobs when applicable
