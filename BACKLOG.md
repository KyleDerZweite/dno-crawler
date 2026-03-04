# DNO Crawler - Unified Backlog

> Consolidated on: 2026-03-04
> Source of truth for backlog, deferred work, and strategic idea context.

---

## 1. Status Summary

- Open implementation work is tracked in **Active Backlog** and **Post-MVP Deferred**.
- Strategic candidates are tracked in **Idea Pool**.
- Completed delivery items can remain documented inline in the relevant task history.

---

## 2. Active Backlog

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
  - Deliverables: geospatial ingestion plus indexed lookup, resolver strategy abstraction, latency/coverage benchmark.
  - Acceptance:
    - System can resolve addresses through OSM path for supported regions.
    - Fallback to VNB works when OSM confidence is low.

- [x] **TASK-008 DNO Importance Scoring and Priority-Based Gap Filling**
  - Goal: Establish the canonical importance score used by all automated enrichment/crawl workflows.
  - Scope: scoring formula (area, connection points, customer count), explainability output, and calibration.
  - Deliverables: scoring module, score storage/update flow, admin visibility for score distribution and factors.
  - Implementation note (2026-03-04): Canonical scoring service plus DB persistence plus script-based recompute plus read-only admin distribution shipped. Admin write endpoint intentionally removed per YAGNI.
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
  - Goal: Queue crawl jobs automatically when worker idle time exceeds a threshold, using enriched metadata and importance score.
  - Scope: idle-time detection, candidate selection from metadata gap/enrichment outputs, safe enqueue constraints, anti-abuse protections.
  - Deliverables: scheduler worker/cron, idle-threshold configuration, priority queueing policy and guardrails.
  - Acceptance:
    - Jobs are enqueued only after idle threshold is exceeded.
    - Candidate selection prioritizes high-importance DNOs with actionable metadata.
    - Throughput improves without increased block/protection incidents.

- [ ] **TASK-009 Bulk Data Directory Long-Term Strategy**
  - Goal: Define a sustainable long-term approach for bulk-data storage and lifecycle management.
  - Scope: investigate options, constraints, trade-offs, and operational impact before choosing implementation.
  - Deliverables: decision proposal documenting recommended strategy, alternatives considered, and rollout plan.
  - Acceptance:
    - A clear decision is documented for how bulk-data should be handled long term.
    - Ownership, retention/lifecycle policy, and operational workflow are explicitly defined.

- [ ] **TASK-010 HLZF Window Export as SQTV CSV (Low Priority)**
  - Goal: Export HLZF time-window status streams as SQTV-compatible CSV to avoid manual copy workflows.
  - Scope: selectable export period (for example year), source name selection (custom value or MaStR Nr / VNB Id / BDEW code / slug / name), and quantity selection (default Status or custom).
  - Deliverables: integrated export flow (API or UI-triggered backend job) that reuses existing HLZF export logic and emits SQTV CSV.
  - Acceptance:
    - For the selected period, export includes a proper timestamp series and status values where HLZF-in-window is 1, otherwise 0.
    - Source name is configurable via custom input or selected identifier strategy.
    - Quantity label is configurable (Status or custom value) in the exported stream.

---

## 3. Post-MVP Deferred

- [ ] XLSX extraction pipeline implementation.
- [ ] SQL Explorer frontend implementation (currently stub).
- [ ] Technical view frontend implementation (currently stub).
- [ ] Tools view frontend implementation (currently stub).
- [ ] LiteLLM provider implementation.
- [ ] Impressum enrichment enhancements.
- [ ] Frontend test coverage expansion.

---

## 4. Idea Pool

- [ ] Westnetz ghost paths support (manual upload workaround exists).
- [ ] CMS fingerprinting (for example Schleupen/Thüga detection).
- [ ] Historical data storage and multi-year comparison (covered by TASK-002).
- [ ] Bulk export API.
- [ ] HLZF iCal export.
- [ ] HLZF window export as SQTV CSV (selectable source name/identifier plus quantity mapping).
- [ ] Price alert system.
- [ ] Cost calculator.
- [ ] EV charging integration (evcc).
- [ ] API endpoint GET /api/v1/lookup?lat=X&lon=Y.
- [ ] API endpoint POST /api/v1/webhooks for price-change notifications.
- [ ] GraphQL endpoint.

---

## 5. Strategic Context

### Primary Data Sources (Implemented)
| Source | Purpose | Status |
|--------|---------|--------|
| MaStR (Marktstammdatenregister) | Official German registry of approximately 800 DNOs | ✅ CSV import pipeline |
| VNB-digital GraphQL | Grid polygons for address to DNO mapping | ✅ Implemented |
| BDEW-Codes.de | BDEW codes and EDIFACT contact data | ✅ Implemented |

### Capability Snapshot (Implemented)
| Capability | Status |
|------------|--------|
| VNB-digital GraphQL integration | ✅ |
| Skeleton service | ✅ |
| Impressum extraction | ✅ |
| BFS crawler | ✅ |
| Token URL detection | ✅ |
| AI/PDF/HTML extraction | ✅ |
| Sitemap discovery | ✅ |
| robots.txt parsing | ✅ |
| BDEW jTable API integration | ✅ |
| MaStR CSV import | ✅ |
| Pattern learning | ✅ |
| Wide Events logging | ✅ |

### Data Retention Principles
1. Never delete raw data. Keep original PDFs and HTML even after extraction.
2. Log operational context. Preserve crawl timestamps, relevant HTTP metadata, and response outcomes.
3. Track changes over time. Store version history for comparisons, audits, and recovery.

Estimated long-term storage footprint: approximately 20 GB.

### Competitive Positioning
| Competitor | DNO Crawler Advantage |
|------------|------------------------|
| GET AG | Free and open source |
| ene't | Self-hostable and API-first |
| Manual research | Automated extraction pipeline |
| Netztransparenz.de | Broad DNO coverage and modern UX |

Core moat: open source distribution plus AI-assisted extraction and community-driven improvements.

---

## 6. Maintenance

- Use this file as the single source of truth for planning and backlog content.
- Keep entries concise and action-oriented.
- Update task status as work moves between idea, backlog, deferred, and done.