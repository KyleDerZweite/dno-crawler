# Operations Guards

Repository-level guardrails implemented for expensive operations and multi-phase writes.

## Admin endpoint rate limiting (per user)

Expensive admin endpoints now apply per-user Redis rate limits through `RateLimiter.check_key_limit()`.

### Where
- `backend/app/core/rate_limiter.py`
- `backend/app/api/routes/admin.py`

### Key format
- `rate_limit:admin_user:{user_id}:{operation}`

### Current limits
- Scan-heavy operations (`/admin/files`): 12 requests / 60s
- Bulk operations (`/admin/extract/*`, cancel/delete): 20 requests / 60s

### Behavior
- Uses atomic Redis `INCR + EXPIRE` pipeline.
- Returns `429` with `Retry-After` on limit exceed.
- Fails open if rate limiter is not initialized (dev/Redis unavailable).

## Import transactional boundaries (partial progress protection)

DNO import now commits by record type to avoid losing successful Netzentgelte writes when HLZF import fails.

### Where
- `backend/app/api/routes/dnos/import_export.py`

### Flow
1. Netzentgelte replace/delete scope + upsert loop
2. `commit()` Netzentgelte phase
3. HLZF replace/delete scope + upsert loop
4. `commit()` HLZF phase

### Result
- HLZF phase errors no longer roll back already committed Netzentgelte progress.
- Sanitization failures still return `400` and rollback current phase transaction.

## CORS origin normalization hardening

CORS parsing now strips empty values and literal `"null"` origins, with localhost fallback.

### Where
- `backend/app/core/config.py`

### Cases handled
- JSON list string input
- Comma-separated string input
- Direct list input

Fallback if cleaned list is empty: `http://localhost:5173`

## Job orchestration idempotency guards

Shared job lifecycle helpers now centralize start/completion/failure metadata writes.

### Where
- `backend/app/jobs/common.py`
- `backend/app/jobs/crawl_job.py`
- `backend/app/jobs/extract_job.py`
- `backend/app/jobs/search_job.py`

### Guard behavior
- `mark_job_running()` returns `False` for jobs already in `running`, `completed`, or `cancelled` state.
- Worker handlers skip execution when `False` is returned, preventing duplicate pipeline runs for re-delivered jobs.
- Completion timestamps are enforced via `ensure_job_failure_timestamp()` in error paths.
