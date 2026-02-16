# DNO Crawler - Knowledge Base

This document consolidates research, strategies, and improvement ideas for the DNO Crawler project.

---

## 1. Data Sources

### Primary Sources (All Implemented ✅)
| Source | Purpose | Status |
|--------|---------|--------|
| **MaStR** (Marktstammdatenregister) | Official German registry of ~800 DNOs | ✅ CSV import via seeder.py |
| **VNB-digital GraphQL** | Grid polygons for address→DNO mapping | ✅ vnb/client.py |
| **BDEW-Codes.de** | BDEW codes + EDIFACT emails | ✅ bdew_client.py |

---

## 2. Implementation Status

### Fully Implemented ✅
| Feature | File |
|---------|------|
| VNB-digital GraphQL | `vnb/client.py` |
| Skeleton Service | `vnb/skeleton.py` |
| Impressum Extractor | `impressum_extractor.py` |
| BFS Crawler | `web_crawler.py` |
| Token URL Detection | `_is_token_url()` in web_crawler.py |
| AI/PDF/HTML Extraction | `extraction/` folder |
| Sitemap Discovery | `discovery/sitemap.py` |
| robots.txt Parsing | `robots_parser.py` |
| **BDEW jTable API** | `bdew_client.py` |
| **MaStR CSV Import** | `db/seeder.py` |
| **Pattern Learning** | `pattern_learner.py` |
| **Wide Events Logging** | `core/logging.py`, `middleware/wide_events.py` |

### Not Yet Implemented ❌
- Westnetz Ghost Paths (using manual upload instead)
- CMS Fingerprinting (Schleupen/Thüga detection)
- Historical data storage (multi-year comparison)
- Bulk export API
- HLZF iCal export
- Price alert system
- Cost calculator
- EV charging integration (evcc)

---

## 3. Future Vision: THE German DNO Platform 🏆

### Unique Features (Partially Built)
| Feature | Status |
|---------|--------|
| AI-Powered PDF Extraction | ✅ Done |
| Address → DNO Lookup | ✅ Done |
| Pattern Learning System | ✅ Done |
| Cost Calculator | ❌ Future |
| HLZF iCal Export | ❌ Future |
| Price Alert System | ❌ Future |
| EV Charging Integration | ❌ Future |
| Bulk Comparison Tool | ❌ Future |

### API Expansion Ideas (Future)
- `GET /api/v1/lookup?lat=X&lon=Y` - Geo lookup
- `POST /api/v1/webhooks` - Price change notifications
- Bulk export (CSV/JSON)
- GraphQL endpoint

---

## 4. Data Hoarding Philosophy 📦

> "Store everything. Transform later. You never know what future-you will need."

**Principles:**
1. **Never delete raw data** - Keep original PDFs/HTML even after extraction
2. **Log everything** - Crawl timestamps, HTTP headers, response codes
3. **Version history** - Track when data changed, not just current state

**Storage Estimate: ~20 GB** for everything

---

## 5. Competitive Positioning

| Competitor | Our Advantage |
|------------|---------------|
| GET AG | Free + open source |
| ene't | Self-hostable, API-first |
| Manual research | AI automation |
| Netztransparenz.de | All 800 DNOs, modern UX |

**Our Moat:** Open source + AI extraction + community

---

## 6. Refined Backlog Tasks

### Completed

- [x] **TASK-001 MaStR Baseline Integration**
	- **Status:** Done
	- **Outcome:** MaStR source import and backend linkage are implemented.
	- **Reference:** `marktstammdatenregister/README.md`

### Planned

- [ ] **TASK-002 MaStR Multi-Year History (Append-Only)**
	- **Goal:** Track MaStR changes over time without overwriting historical records.
	- **Scope:**
		- Introduce snapshot/version fields for MaStR imports.
		- Store each import batch as append-only records.
		- Add frontend comparison view for year-over-year deltas.
	- **Deliverables:**
		- DB migration for versioned MaStR snapshots.
		- Import pipeline update preserving historical entries.
		- API endpoint for historical series per DNO.
	- **Acceptance Criteria:**
		- Re-importing MaStR data does not delete prior versions.
		- User can compare at least two periods for one DNO.

- [ ] **TASK-003 Data Versioning for Manual Edits and Re-Runs**
	- **Goal:** Provide auditable history for extracted and manually edited records.
	- **Scope:**
		- Version netzentgelte and HLZF records on edit and re-extraction.
		- Persist change metadata (who, when, source, reason).
		- Add API support for viewing and diffing record versions.
	- **Deliverables:**
		- Version tables and triggers or application-level version writes.
		- UI panel showing change history and rollback candidate selection.
	- **Acceptance Criteria:**
		- Every update creates an immutable version entry.
		- Version history is queryable and visible in UI.

- [ ] **TASK-004 OpenStreetMap-Based Geo Resolution**
	- **Goal:** Reduce dependency on VNB Digital for geolocation and lookup.
	- **Scope:**
		- Build optional OSM-based geospatial lookup path.
		- Cache/precompute lookup artifacts for fast runtime queries.
		- Keep VNB Digital as fallback/validation source.
	- **Deliverables:**
		- Geospatial ingestion job and indexed lookup table.
		- Resolver service abstraction with provider strategy.
		- Benchmark report for lookup latency and coverage.
	- **Acceptance Criteria:**
		- System can resolve addresses through OSM path for supported regions.
		- Fallback to VNB path works when OSM resolution confidence is low.

- [ ] **TASK-005 Idle-Time Autonomous Crawl Scheduler**
	- **Goal:** Automatically crawl highest-value DNOs when workers are idle.
	- **Scope:**
		- Define relevance score (coverage gap, data staleness, MaStR priority signals).
		- Queue jobs only within safe concurrency/rate limits.
		- Include anti-abuse protections to avoid IP blocking.
	- **Deliverables:**
		- Scheduler worker/cron job.
		- Priority scoring module with explainable factors.
		- Guardrails for host budget and crawl politeness.
	- **Acceptance Criteria:**
		- Scheduler enqueues jobs only when idle threshold is met.
		- Crawl throughput increases without elevated block/protection incidents.
 