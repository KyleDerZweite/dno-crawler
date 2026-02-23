# Operations Guards

> Documentation note: The codebase is authoritative. This document records stable operational guardrail behavior.

Repository-level guardrails implemented for expensive operations and multi-phase writes.

The codebase is authoritative for exact implementation. This document captures stable operational behavior and intent.

## Admin endpoint rate limiting (per user)

Expensive admin operations apply per-user Redis-backed limits to reduce abuse and accidental load spikes.

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

### Cases handled
- JSON list string input
- Comma-separated string input
- Direct list input

Fallback if cleaned list is empty: `http://localhost:5173`

## Job orchestration idempotency guards

Shared job lifecycle helpers now centralize start/completion/failure metadata writes.

### Guard behavior
- `mark_job_running()` returns `False` for jobs already in `running`, `completed`, or `cancelled` state.
- Worker handlers skip execution when `False` is returned, preventing duplicate pipeline runs for re-delivered jobs.
- Completion timestamps are enforced via `ensure_job_failure_timestamp()` in error paths.
