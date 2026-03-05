# Importance Recompute Workflow

This document describes the backend operational workflow referred to as `backend.importance.recompute`.

## Purpose

Use this workflow to recompute and persist canonical importance scoring fields for all DNO records.

## Execution Modes

- **Persist mode**: recomputes and commits updated importance fields in batches.
- **Dry-run mode**: recomputes in batches and rolls back at the end.

## Behavior Guarantees

- Processes DNO records in bounded batches to avoid loading the full dataset into memory.
- Eager-loads MaStR relation data required by scoring logic.
- Applies the canonical scoring service (`app.services.importance`) consistently.

## Operational Notes

- Use this workflow for batch recomputation tasks instead of admin write endpoints.
- Keep admin API usage focused on read-only diagnostics and distribution reporting.
