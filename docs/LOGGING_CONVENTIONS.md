# Logging Conventions

> **Last Updated:** 2026-01-09

This document defines logging conventions optimized for both human debugging and AI-assisted analysis. It covers the Wide Events pattern and structured logging standards.

---

## Table of Contents

1. [Philosophy: Wide Events](#1-philosophy-wide-events)
2. [AI-Optimized Logging](#2-ai-optimized-logging)
3. [Log Format Standards](#3-log-format-standards)
4. [Field Naming Conventions](#4-field-naming-conventions)
5. [Domain-Specific Fields](#5-domain-specific-fields)
6. [Tail Sampling Strategy](#6-tail-sampling-strategy)
7. [Quick Reference](#7-quick-reference)

---

## 1. Philosophy: Wide Events

### The Problem with Traditional Logging

Traditional logging creates scattered, context-free entries:

```
❌ BAD: Traditional scattered logs
2026-01-09 10:23:45 INFO Starting request
2026-01-09 10:23:45 DEBUG Loading user from database
2026-01-09 10:23:46 INFO User loaded
2026-01-09 10:23:46 DEBUG Processing payment
2026-01-09 10:23:47 ERROR Payment failed
2026-01-09 10:23:47 INFO Request completed
```

Problems:
- 6 log lines for one request
- No correlation between lines
- Missing context (which user? what amount? why failed?)
- Impossible to query effectively

### The Solution: Wide Events (Canonical Log Lines)

Emit **one comprehensive event per request** with all context:

```json
✅ GOOD: Single wide event
{
  "timestamp": "2026-01-09T10:23:47.000Z",
  "request_id": "req_a7f8b2c3",
  "http": {
    "method": "POST",
    "path": "/api/v1/checkout",
    "status_code": 500,
    "client_ip": "192.168.1.50"
  },
  "duration_ms": 2341,
  "outcome": "error",
  "user": {
    "id": "user_456",
    "email": "kyle@example.com",
    "subscription": "premium",
    "account_age_days": 847
  },
  "payment": {
    "method": "card",
    "provider": "stripe",
    "amount_cents": 15999,
    "attempt": 3
  },
  "error": {
    "type": "PaymentError",
    "code": "card_declined",
    "message": "Insufficient funds"
  },
  "service": {
    "name": "checkout-api",
    "version": "2.4.1"
  }
}
```

Benefits:
- One event = complete picture
- Queryable: `SELECT * WHERE user.subscription = 'premium' AND error.code = 'card_declined'`
- AI-parseable: Full context for analysis
- Debuggable: No grep-ing across files

---

## 2. AI-Optimized Logging

### Principles for AI-Friendly Logs

When AI assistants analyze your logs, they need:

| Principle | Why | Example |
|-----------|-----|---------|
| **Structured JSON** | Parseable, queryable | `{"user_id": "123"}` not `user 123 logged in` |
| **Consistent field names** | Pattern matching | Always `user_id`, never `userId`, `user-id`, `uid` |
| **High cardinality IDs** | Correlation | `request_id`, `trace_id`, `user_id`, `job_id` |
| **Business context** | Understanding | Include `subscription_tier`, `feature_flags` |
| **Error classification** | Root cause analysis | `error.type`, `error.code`, `error.retriable` |

### Required Fields for Every Event

```json
{
  // ALWAYS include these - AI uses them for correlation
  "timestamp": "ISO 8601 format",
  "request_id": "unique per request",
  "level": "debug|info|warning|error",
  
  // Context fields - include what's relevant
  "service": {
    "name": "service-name",
    "version": "1.2.3",
    "environment": "production|staging|development"
  },
  
  // For HTTP requests
  "http": {
    "method": "GET|POST|PUT|DELETE",
    "path": "/api/v1/resource",
    "status_code": 200,
    "duration_ms": 123
  },
  
  // For authenticated requests
  "user": {
    "id": "user identifier",
    "roles": ["admin", "member"]
  },
  
  // For errors
  "error": {
    "type": "ErrorClassName",
    "code": "machine_readable_code",
    "message": "Human readable message",
    "stack": "optional stack trace"
  }
}
```

### AI Analysis Prompts

These logs are designed to answer questions like:

```
"Show me all failed requests for premium users in the last hour"
→ WHERE outcome = 'error' AND user.subscription = 'premium' AND timestamp > now() - 1h

"What's the error rate by endpoint?"
→ GROUP BY http.path, COUNT(*) WHERE outcome = 'error' / COUNT(*)

"Find the slowest database queries"
→ WHERE db.duration_ms > 1000 ORDER BY db.duration_ms DESC

"Correlate this user's journey across services"
→ WHERE user.id = 'user_456' ORDER BY timestamp
```

---

## 3. Log Format Standards

### Log Levels

| Level | When to Use | Examples |
|-------|-------------|----------|
| `debug` | Development diagnostics | Cache lookups, SQL queries, internal state |
| `info` | Normal operations | Request completed, job started, user action |
| `warning` | Recoverable issues | Rate limit approaching, retry attempted, deprecation |
| `error` | Failures requiring attention | Unhandled exception, external service down |

### Event Types

```python
# Define event types as constants for consistency
class EventType:
    REQUEST_COMPLETED = "request_completed"      # Wide event for HTTP requests
    JOB_STARTED = "job_started"                  # Background job lifecycle
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    EXTERNAL_CALL = "external_call"              # Calls to external APIs
    DATABASE_QUERY = "database_query"            # For slow query logging
    SECURITY_EVENT = "security_event"            # Auth failures, suspicious activity
```

### Timestamp Format

Always use ISO 8601 with milliseconds and UTC timezone:

```
✅ GOOD: "2026-01-09T10:23:47.123Z"
❌ BAD:  "1704792227"
❌ BAD:  "Jan 9 2026 10:23:47"
❌ BAD:  "2026-01-09 10:23:47" (missing timezone)
```

---

## 4. Field Naming Conventions

### General Rules

```yaml
# Use snake_case for all field names
✅ user_id, request_id, created_at, error_message
❌ userId, RequestId, createdAt, errorMessage

# Use dot notation for nested objects
✅ user.id, user.email, http.method, error.code
❌ user_id (when there's also user_email), httpMethod

# Use lowercase for enum values
✅ "status": "pending", "level": "error"
❌ "status": "PENDING", "level": "ERROR"

# Boolean fields should be prefixed with is_, has_, can_
✅ is_admin, has_subscription, can_edit
❌ admin, subscribed, editable
```

### Standard Field Names

Use these exact names across all services:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 datetime |
| `request_id` | string | Unique request identifier |
| `trace_id` | string | Distributed trace ID |
| `level` | string | debug, info, warning, error |
| `event` | string | Event type name |
| `duration_ms` | integer | Duration in milliseconds |
| `outcome` | string | success, error |

### HTTP Fields

| Field | Type | Description |
|-------|------|-------------|
| `http.method` | string | GET, POST, PUT, DELETE |
| `http.path` | string | Request path |
| `http.status_code` | integer | Response status code |
| `http.client_ip` | string | Client IP address |
| `http.user_agent` | string | User agent (truncated) |

### User Fields

| Field | Type | Description |
|-------|------|-------------|
| `user.id` | string | User identifier |
| `user.email` | string | User email |
| `user.roles` | array | User roles |
| `user.is_admin` | boolean | Admin flag |

### Error Fields

| Field | Type | Description |
|-------|------|-------------|
| `error.type` | string | Exception class name |
| `error.code` | string | Machine-readable code |
| `error.message` | string | Human-readable message |
| `error.retriable` | boolean | Can be retried |
| `error.stack` | string | Stack trace (debug only) |

---

## 5. Domain-Specific Fields

### DNO Crawler Fields

```json
{
  // DNO context
  "dno": {
    "id": 42,
    "name": "Stadtwerke München",
    "status": "crawled"
  },
  
  // Crawl job context
  "job": {
    "id": 789,
    "type": "full|crawl|extract",
    "status": "running",
    "data_type": "netzentgelte|hlzf",
    "year": 2025,
    "step": "discover|download|extract|validate"
  },
  
  // Extraction context
  "extraction": {
    "mode": "regex|ai|fallback",
    "model": "gemini-2.0-flash",
    "file_type": "pdf|html",
    "pages_processed": 5,
    "records_extracted": 15
  }
}
```

---

## 6. Tail Sampling Strategy

### Why Sample?

At scale, storing 100% of logs is expensive. Tail sampling keeps important events while sampling routine ones.

### Sampling Rules

| Event Type | Sample Rate | Reason |
|------------|-------------|--------|
| Errors (4xx, 5xx) | 100% | Always debug failures |
| Slow requests (>2s) | 100% | Performance issues |
| Admin actions | 100% | Audit trail |
| Job events | 100% | Business critical |
| Security events | 100% | Compliance |
| Success + fast | 10% | Cost control |

### Implementation

```python
def should_sample(event: dict) -> bool:
    """
    Tail sampling decision.
    
    Returns True to KEEP the event, False to DROP.
    """
    # ALWAYS keep errors
    status = event.get("http", {}).get("status_code", 200)
    if status >= 400:
        return True
    
    # ALWAYS keep slow requests (>2s)
    if event.get("duration_ms", 0) > 2000:
        return True
    
    # ALWAYS keep admin actions
    if event.get("user", {}).get("is_admin"):
        return True
    
    # ALWAYS keep job events
    if event.get("job"):
        return True
    
    # ALWAYS keep security events
    if event.get("event") == "security_event":
        return True
    
    # Sample 10% of successful fast requests
    import random
    return random.random() < 0.10
```

---

## 7. Quick Reference

### Do's ✅

- Emit one wide event per request
- Use consistent field names (snake_case)
- Include request_id in every event
- Add business context (user tier, feature flags)
- Keep errors at 100% sample rate
- Use structured JSON format
- Use ISO 8601 timestamps with timezone

### Don'ts ❌

- Don't log sensitive data (passwords, tokens, PII)
- Don't use string interpolation for log messages
- Don't emit multiple logs for one request
- Don't log inside tight loops
- Don't use inconsistent field names
- Don't forget to include error context
- Don't log without a request_id

### Example Wide Event (Complete)

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
    "name": "Stadtwerke München"
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

---

## Files Reference

| File | Purpose |
|------|---------|
| `backend/app/core/logging.py` | Wide events implementation |
| `backend/app/api/middleware/wide_events.py` | FastAPI middleware |

For infrastructure setup (OTel Collector, Loki, Prometheus, Grafana), see the separate observability stack documentation in your infrastructure repository.
