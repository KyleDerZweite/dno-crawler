# Logging Conventions

## Core Principle

Emit **one wide event per request** containing all context. No scattered log lines.

## Log Levels

| Level | When to Use | Examples |
|-------|-------------|---------|
| `debug` | Development diagnostics | Cache lookups, SQL queries, internal state |
| `info` | Normal operations | Request completed, job started, user action |
| `warning` | Recoverable issues | Rate limit approaching, retry attempted |
| `error` | Failures requiring attention | Unhandled exception, external service down |

## Field Naming Rules

- **snake_case** for all field names: `user_id`, `request_id`, `created_at`
- **Dot notation** for nested objects: `user.id`, `http.method`, `error.code`
- **Lowercase** enum values: `"status": "pending"`, `"level": "error"`
- **Boolean prefixes**: `is_`, `has_`, `can_` (`is_admin`, `has_subscription`)

## Standard Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 with ms and UTC (`2026-01-09T10:23:47.123Z`) |
| `request_id` | string | Unique per request |
| `trace_id` | string | Distributed trace ID |
| `level` | string | debug, info, warning, error |
| `event` | string | Event type name |
| `duration_ms` | integer | Duration in milliseconds |
| `outcome` | string | success, error |

## HTTP Fields

`http.method`, `http.path`, `http.status_code`, `http.client_ip`, `http.user_agent`

## User Fields

`user.id`, `user.email`, `user.roles`, `user.is_admin`

## Error Fields

`error.type` (class name), `error.code` (machine-readable), `error.message` (human-readable), `error.retriable` (bool), `error.stack` (debug only)

## Best Practices

| Do | Don't |
|----|-------|
| One wide event per request | Multiple logs for one request |
| Consistent field names (snake_case) | Mixed casing (`userId`, `user-id`) |
| Include `request_id` in every event | Log without correlation IDs |
| Structured JSON format | String interpolation for messages |
| ISO 8601 timestamps with timezone | Unix timestamps or ambiguous formats |
| Add business context (user tier, flags) | Log sensitive data (passwords, tokens, PII) |
| Keep errors at 100% sample rate | Log inside tight loops |
