# Logging Domain Fields

Project-specific logging fields and examples for the DNO Crawler application.

## Domain Fields

```json
{
  "dno": {
    "id": 42,
    "name": "Stadtwerke Munchen",
    "status": "crawled"
  },
  "job": {
    "id": 789,
    "type": "full|crawl|extract",
    "status": "running",
    "data_type": "netzentgelte|hlzf",
    "year": 2025,
    "step": "discover|download|extract|validate|finalize"
  },
  "extraction": {
    "mode": "regex|ai|fallback",
    "model": "gemini-2.0-flash",
    "file_type": "pdf|html",
    "pages_processed": 5,
    "records_extracted": 15
  },
  "verification": {
    "status": "pending|verified|flagged",
    "verified_by": "user_id",
    "flag_reason": "optional reason"
  }
}
```

## Complete Wide Event Example

```json
{
  "timestamp": "2026-01-09T10:23:47.123Z",
  "request_id": "req_a7f8b2c3",
  "trace_id": "abc123def456",
  "level": "info",
  "event": "request_completed",
  "service": {
    "name": "dno-crawler-api",
    "version": "0.1.0",
    "environment": "production"
  },
  "http": {
    "method": "POST",
    "path": "/api/v1/dnos/42/crawl",
    "status_code": 201,
    "client_ip": "192.168.1.50",
    "duration_ms": 847
  },
  "user": {
    "id": "user_456",
    "email": "admin@example.com",
    "roles": ["admin"],
    "is_admin": true
  },
  "dno": {
    "id": 42,
    "name": "Stadtwerke Munchen"
  },
  "job": {
    "id": 789,
    "type": "full",
    "data_type": "netzentgelte",
    "year": 2025
  },
  "outcome": "success",
  "duration_ms": 847
}
```

## Tail Sampling Rules

| Event Type | Sample Rate | Reason |
|------------|-------------|--------|
| Errors (4xx, 5xx) | 100% | Always debug failures |
| Slow requests (>2s) | 100% | Performance issues |
| Admin actions | 100% | Audit trail |
| Job events | 100% | Business critical |
| Security events | 100% | Compliance |
| Success and fast | 10% | Cost control |

### Implementation

```python
def should_sample(event: dict) -> bool:
    """Tail sampling decision. Returns True to KEEP, False to DROP."""
    status = event.get("http", {}).get("status_code", 200)
    if status >= 400:
        return True
    if event.get("duration_ms", 0) > 2000:
        return True
    if event.get("user", {}).get("is_admin"):
        return True
    if event.get("job"):
        return True
    if event.get("event") == "security_event":
        return True
    import random
    return random.random() < 0.10
```

## Files Reference

| File | Purpose |
|------|---------|
| `backend/app/core/logging.py` | Wide events implementation |
| `backend/app/api/middleware/wide_events.py` | FastAPI middleware |
