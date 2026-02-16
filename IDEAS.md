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

New Ideas, that need refinining:
1. Markstadammdatenregister (see marktstammdatenregister/README.md)
2. Add a multi year option, that shows how the Markstadammdaten change / develop over the years, so that the user can get insights into that. So never override, only extend
3. In general maybe a versioning so that even after manually editing or rerunning a job u can see previous versions, like a git just in postgre db (need to check and refine how that could work)
4. OpenStreetMap, for Geo-Location, without relying on the VNB digital API for this step!? Therefore reduce relience on other services and buildup a geo-map in the db (maybe even pre-calculate a bit so the lookup is faster then, gotta see)
5. Automatic Crawler, a job that if the service is idle queues a new crawl job for a DNO that is the most relevant (and hase not full coverage), relevance can / will be able to be calculated via the Markstammdaten. Goal would be to after time, get most dno's crawler and then accessible, without overloading the service host and without getting the IP flagged (/blocked, because of spam/bot what ever)
 