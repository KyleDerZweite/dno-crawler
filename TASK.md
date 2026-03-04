# TASK Register

> Consolidated on: 2026-03-03
> Sources: IDEAS.md, RESULT_MVP_SUMMARY.md, RESULT_principles_audit.md

## Status Summary

- Open tasks are tracked under **Backlog** and **Post-MVP Deferred**.
- Completed tasks are kept in **Completed** for historical context.
- Remaining open items from `RESULT_principles_audit.md`: **none** (all marked done).

## Backlog (from IDEAS.md)

- [ ] **TASK-002 MaStR Multi-Year History (Append-Only)**
  - Goal: Track MaStR changes over time without overwriting historical records.
  - Scope: snapshot/version fields, append-only import batches, frontend comparison view.
  - Deliverables: DB migration, import pipeline update, historical series API endpoint.
  - Acceptance:
    - Re-importing MaStR data does not delete prior versions.
    - User can compare at least two periods for one DNO.

- [ ] **TASK-003 Data Versioning for Manual Edits and Re-Runs**
  - Goal: Provide auditable history for extracted and manually edited records.
  - Scope: version netzentgelte/HLZF updates, persist who/when/source/reason, diff API support.
  - Deliverables: version tables and writes, UI history panel with rollback candidates.
  - Acceptance:
    - Every update creates an immutable version entry.
    - Version history is queryable and visible in UI.

- [ ] **TASK-004 OpenStreetMap-Based Geo Resolution**
  - Goal: Reduce dependency on VNB Digital for geolocation and lookup.
  - Scope: optional OSM resolver path, caching/precompute, VNB fallback and validation.
  - Deliverables: geospatial ingestion + indexed lookup, resolver strategy abstraction, latency/coverage benchmark.
  - Acceptance:
    - System can resolve addresses through OSM path for supported regions.
    - Fallback to VNB works when OSM confidence is low.

- [x] **TASK-008 DNO Importance Scoring and Priority-Based Gap Filling**
  - Goal: Establish the canonical importance score used by all automated enrichment/crawl workflows.
  - Scope: scoring formula (area, connection points, customer count), explainability output, and calibration.
  - Deliverables: scoring module, score storage/update flow, admin visibility for score distribution and factors.
  - Implementation note (2026-03-04): Canonical scoring service + DB persistence + script-based recompute + read-only admin distribution shipped. Admin write endpoint intentionally removed per YAGNI.
  - Acceptance:
    - All DNOs have an importance score.
    - Scores are explainable (factor breakdown available for operators).
    - Score output is consumable by downstream automation tasks.

- [ ] **TASK-006 Automatic Metadata Gap Filler (depends on TASK-008)**
  - Goal: Automatically fill missing metadata (website/domain/robots/sitemap/etc.) prioritized by importance score.
  - Scope: scan metadata gaps, discover official domains, prefetch/cache robots/sitemap/protection status.
  - Deliverables: background enrichment job, integration with importance scoring, metadata completeness dashboard.
  - Acceptance:
    - Missing websites are flagged and auto-discovered where possible.
    - robots.txt and sitemap data are pre-cached for crawlable DNOs.
    - Processing order prioritizes high-importance DNOs first.

- [ ] **TASK-005 Idle-Time Autonomous Crawl Scheduler (depends on TASK-006)**
  - Goal: Queue crawl jobs automatically when worker idle time exceeds a threshold, using enriched metadata + importance score.
  - Scope: idle-time detection, candidate selection from metadata gap/enrichment outputs, safe enqueue constraints, anti-abuse protections.
  - Deliverables: scheduler worker/cron, idle-threshold configuration, priority queueing policy and guardrails.
  - Acceptance:
    - Jobs are enqueued only after idle threshold is exceeded.
    - Candidate selection prioritizes high-importance DNOs with actionable metadata.
    - Throughput improves without increased block/protection incidents.

- [ ] **TASK-009 Bulk Data Directory Long-Term Strategy**
  - Goal: Define a sustainable long-term approach for `bulk-data` storage and lifecycle management.
  - Scope: investigate options, constraints, trade-offs, and operational impact before choosing implementation.
  - Deliverables: decision proposal documenting recommended strategy, alternatives considered, and rollout plan.
  - Acceptance:
    - A clear decision is documented for how `bulk-data` should be handled long term.
    - Ownership, retention/lifecycle policy, and operational workflow are explicitly defined.

## Post-MVP Deferred (from RESULT_MVP_SUMMARY.md)

- [ ] XLSX extraction pipeline implementation.
- [ ] SQL Explorer frontend implementation (currently stub).
- [ ] Technical view frontend implementation (currently stub).
- [ ] Tools view frontend implementation (currently stub).
- [ ] LiteLLM provider implementation.
- [ ] Impressum enrichment enhancements.
- [ ] Frontend test coverage expansion.

## Idea Backlog (from IDEAS.md, non-TASK section)

- [ ] Westnetz Ghost Paths support (currently manual upload workaround).
- [ ] CMS fingerprinting (e.g., Schleupen/Thüga detection).
- [ ] Historical data storage and multi-year comparison (covered by TASK-002).
- [ ] Bulk export API.
- [ ] HLZF iCal export.
- [ ] Price alert system.
- [ ] Cost calculator.
- [ ] EV charging integration (evcc).
- [ ] API endpoint `GET /api/v1/lookup?lat=X&lon=Y`.
- [ ] API endpoint `POST /api/v1/webhooks` for price-change notifications.
- [ ] GraphQL endpoint.