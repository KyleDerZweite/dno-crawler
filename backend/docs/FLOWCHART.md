# DNO Crawler - Complete Pipeline Flowchart

This document describes the complete flow of the DNO data crawler, from user input to extracted data.

---

## Overview

```mermaid
flowchart TB
    subgraph Input["1️⃣ User Input"]
        A1[Address] --> VNB
        A2[Coordinates] --> VNB
        A3[DNO Name] --> VNB
    end
    
    subgraph Skeleton["2️⃣ DNO Skeleton Creation"]
        VNB[VNB Digital API Lookup] --> DNO[DNO Record]
        DNO --> IMP[Fetch Impressum]
        DNO --> ROB[Fetch robots.txt]
        IMP --> |"Extract Address"| ADDR[Enhanced Address]
        ROB --> |"Store Full"| ROBOTS[Stored robots.txt]
        ROB --> |"Check Response"| CRAWL{Crawlable?}
    end
    
    subgraph Discovery["3️⃣ Data Discovery"]
        CRAWL --> |"Yes"| SITEMAP[Parse Sitemap from robots.txt]
        CRAWL --> |"No: JS Challenge"| MANUAL[Mark for Manual Review]
        SITEMAP --> SCORE[Score & Filter URLs]
        SCORE --> TOP[Get Top Candidates]
    end
    
    subgraph Download["4️⃣ Smart Download"]
        TOP --> TYPE{File Type?}
        TYPE --> |"PDF/Excel"| DL_FILE[Download File Directly]
        TYPE --> |"HTML Page"| CHECK_HTML[Check for Embedded Data]
        CHECK_HTML --> |"Has Tables"| STRIP[Strip & Save HTML]
        CHECK_HTML --> |"No Data"| NEXT[Try Next Candidate]
    end
    
    subgraph Extract["5️⃣ Data Extraction"]
        DL_FILE --> AI{AI Configured?}
        STRIP --> AI
        AI --> |"Yes"| AI_EXT[AI Vision Extraction]
        AI --> |"No"| REGEX[Regex Fallback Extraction]
        AI_EXT --> |"Failed"| REGEX
        REGEX --> DATA[Structured Data]
    end
    
    DATA --> DB[(Database)]
```

---

## Phase 1: User Input & DNO Lookup

```mermaid
flowchart LR
    subgraph Input["User Provides"]
        A[Address] 
        B[Coordinates]
        C[DNO Name]
    end
    
    Input --> VNB[VNB Digital API]
    
    VNB --> R1{Found?}
    R1 --> |"Yes"| INFO[/"DNO Info:
    - Official Name
    - BDEW Code  
    - Website URL
    - Contact Details"/]
    R1 --> |"No"| ERR[Error: DNO Not Found]
    
    INFO --> CHECK{DNO Exists in DB?}
    CHECK --> |"Yes"| EXISTING[Use Existing DNO]
    CHECK --> |"No"| CREATE[Create DNO Skeleton]
```

**VNB API Response Contains:**
- `strasse`, `ort`, `plz` → Address
- `homepage` → Website URL for crawling
- `telefon`, `email` → Contact info
- `kurzbezeichnung` → Short name/slug

---

## Phase 2: DNO Skeleton Creation

```mermaid
flowchart TD
    START[Create DNO Skeleton] --> VNB[VNB Data]
    
    VNB --> P1[Fetch Impressum Page]
    VNB --> P2[Fetch robots.txt]
    
    subgraph Impressum["Impressum Extraction"]
        P1 --> IMP1{Response OK?}
        IMP1 --> |"200"| PARSE[Parse HTML]
        IMP1 --> |"JS Challenge"| IMP_FAIL[Mark: JS Protected]
        IMP1 --> |"404/Error"| IMP_NONE[No Impressum]
        
        PARSE --> ADDR[/"Extract:
        - PLZ
        - City
        - Street"/]
    end
    
    subgraph Robots["robots.txt Handling"]
        P2 --> ROB1{Response OK?}
        ROB1 --> |"200 + Valid"| STORE[Store Full Content]
        ROB1 --> |"JS Challenge"| JS_FLAG[/"Set Flag:
        crawlable = false
        reason = 'cloudflare'"/]
        ROB1 --> |"404"| NO_ROBOTS[No robots.txt - Still Crawlable]
        
        STORE --> SITEMAP_URL[Extract Sitemap URLs]
        STORE --> DISALLOW[Parse Disallow Rules]
    end
    
    ADDR --> SKELETON
    IMP_FAIL --> SKELETON
    JS_FLAG --> SKELETON
    SITEMAP_URL --> SKELETON
    DISALLOW --> SKELETON
    
    SKELETON[/"DNO Skeleton:
    - name, slug, website
    - address (enhanced)
    - robots_txt (full)
    - sitemap_urls[]
    - disallow_paths[]
    - crawlable: bool
    - crawl_blocked_reason"/]
    
    SKELETON --> DB[(Save to Database)]
```

**Key Insight:** We determine crawlability during skeleton creation by checking if we can fetch robots.txt. If Cloudflare blocks us, we know before any crawl attempt.

---

## Phase 3: Crawl Job Trigger

```mermaid
flowchart TD
    USER[User Clicks "Crawl"] --> CHECK{DNO Crawlable?}
    
    CHECK --> |"No"| BLOCKED[/"Show Error:
    'Site uses JavaScript protection.
    Manual data entry required.'"/]
    
    CHECK --> |"Yes"| CACHE{Cached Data Exists?}
    
    CACHE --> |"Yes + Fresh"| USE_CACHE[Use Cached Files]
    CACHE --> |"No or Stale"| START_JOB[Start Crawl Job]
    
    USE_CACHE --> EXTRACT[Go to Extraction]
    START_JOB --> QUEUE[Add to Job Queue]
    
    QUEUE --> WORKER[Background Worker Picks Up]
```

---

## Phase 4: Discovery Pipeline

```mermaid
flowchart TD
    START[Crawl Job Starts] --> DB_READ[Load DNO from DB]
    
    DB_READ --> HAS_ROBOTS{Has robots.txt?}
    
    HAS_ROBOTS --> |"Yes"| SITEMAP[Get Sitemap URL from robots.txt]
    HAS_ROBOTS --> |"No"| TRY_COMMON[Try Common Sitemap Paths]
    
    SITEMAP --> FETCH[Fetch Sitemap XML]
    TRY_COMMON --> FETCH
    
    FETCH --> FOUND{Sitemap Found?}
    
    FOUND --> |"Yes"| PARSE[Parse All URLs from Sitemap]
    FOUND --> |"No"| BFS[Fallback: BFS Crawl]
    
    PARSE --> FILTER[Filter: Remove Disallowed Paths]
    
    FILTER --> SCORE[/"Score Each URL:
    + Keywords (netzentgelte, strom, hlzf...)
    + File Type Bonus (PDF: +20, Excel: +15)
    + Target Year Bonus (+25)
    - Negative Keywords (gas, vermiedene...)"/]
    
    SCORE --> SORT[Sort by Score DESC]
    SORT --> TOP[Take Top 20 Candidates]
    
    subgraph Special["HLZF Special Handling"]
        TOP --> HLZF{Data Type = HLZF?}
        HLZF --> |"Yes"| CHECK_SPECIFIC{Any HLZF-Specific URLs?}
        CHECK_SPECIFIC --> |"No"| SCAN_HTML[Scan HTML Pages for Embedded Tables]
        SCAN_HTML --> MERGE[Merge Results]
    end
    
    TOP --> CANDIDATES[Final Candidate List]
    MERGE --> CANDIDATES
    BFS --> CANDIDATES
```

**URL Scoring Algorithm:**
| Factor | Score |
|--------|-------|
| PDF file | +20 |
| Excel file | +15 |
| Keyword match (each) | +15 |
| Target year in URL | +25 |
| Negative keyword (each) | -15 to -30 |

---

## Phase 5: Smart Download

```mermaid
flowchart TD
    CAND[Candidate URLs] --> LOOP[For Each Candidate]
    
    LOOP --> TYPE{URL Type?}
    
    TYPE --> |"PDF"| HEAD[HEAD Request]
    TYPE --> |"Excel"| HEAD
    TYPE --> |"HTML Page"| GET_HTML[GET Request]
    
    HEAD --> VERIFY{Content-Type OK?}
    VERIFY --> |"Yes"| DOWNLOAD[Download Full File]
    VERIFY --> |"No"| SKIP[Skip, Try Next]
    
    GET_HTML --> DETECT[Detect Embedded Data Tables]
    DETECT --> HAS_DATA{Has Relevant Tables?}
    HAS_DATA --> |"Yes"| STRIP[Strip HTML - Keep Tables Only]
    HAS_DATA --> |"No"| SKIP
    
    DOWNLOAD --> SAVE[/"Save to:
    data/{slug}/{year}/{filename}"/]
    STRIP --> SAVE
    
    SAVE --> RECORD[Record Source URL + File Path]
    RECORD --> NEXT{More Candidates?}
    
    NEXT --> |"Yes, Need More"| LOOP
    NEXT --> |"Have Enough"| DONE[Files Ready for Extraction]
    
    SKIP --> NEXT
```

**HTML Embedded Data Detection:**
- Look for `<table>` elements
- Check for keywords: "hochlast", "zeitfenster", "uhr", "winter", "sommer"
- Check for voltage levels: "HS", "MS", "NS", "Umspannung"
- Check for year patterns: "gültig ab 01.01.2025"

---

## Phase 6: Data Extraction

```mermaid
flowchart TD
    FILES[Downloaded Files] --> LOOP[For Each File]
    
    LOOP --> EXT{File Extension?}
    
    EXT --> |"PDF"| AI_CHECK{AI Configured?}
    EXT --> |"HTML"| AI_CHECK
    EXT --> |"Excel"| EXCEL[Pandas/OpenPyXL Extraction]
    
    AI_CHECK --> |"Yes"| AI_PREP[Prepare for AI]
    AI_CHECK --> |"No"| REGEX[Regex Extraction]
    
    subgraph AI_Flow["AI Vision Extraction"]
        AI_PREP --> OPTIMIZE[Optimize PDF - Filter Relevant Pages]
        OPTIMIZE --> SEND[Send to Vision Model]
        SEND --> AI_RESULT{Success?}
        AI_RESULT --> |"Yes"| PARSE_JSON[Parse Structured JSON]
        AI_RESULT --> |"No Data"| RETRY{Retry with Full PDF?}
        RETRY --> |"Yes"| SEND_FULL[Send Unoptimized PDF]
        RETRY --> |"Already Tried"| REGEX
        SEND_FULL --> AI_RESULT
    end
    
    subgraph Regex_Flow["Regex Fallback"]
        REGEX --> PATTERNS[/"Apply Patterns:
        - Voltage Levels
        - Price Values
        - Date Ranges"/]
        PATTERNS --> STRUCTURED[Build Structured Output]
    end
    
    PARSE_JSON --> VALIDATE[Validate Extracted Data]
    STRUCTURED --> VALIDATE
    EXCEL --> VALIDATE
    
    VALIDATE --> STORE[Store in Database]
    STORE --> LOG[Log Extraction Results]
```

**AI Optimization Strategy:**
1. Extract text from each PDF page
2. Filter pages containing target keywords
3. Create optimized PDF with only relevant pages
4. Send to AI (reduces tokens by 60-80%)
5. If no data found, retry with full PDF

---

## Fallback Strategy Summary

```mermaid
flowchart LR
    subgraph Discovery
        D1[Sitemap] --> |"Failed"| D2[BFS Crawl]
        D2 --> |"Failed"| D3[Manual Entry Required]
    end
    
    subgraph Download
        DL1[PDF Direct] --> |"Wrong Content"| DL2[Try Next Candidate]
        DL2 --> |"All Failed"| DL3[Mark Job Failed]
    end
    
    subgraph Extraction
        E1[AI Vision] --> |"No Data"| E2[Retry Full PDF]
        E2 --> |"No Data"| E3[Regex Fallback]
        E3 --> |"No Data"| E4[Manual Extraction]
    end
```

---

## Database Schema Overview

```mermaid
erDiagram
    DNO {
        uuid id PK
        string name
        string slug UK
        string website
        string address
        string phone
        string email
        text robots_txt
        json sitemap_urls
        json disallow_paths
        bool crawlable
        string crawl_blocked_reason
    }
    
    CrawlJob {
        uuid id PK
        uuid dno_id FK
        int year
        string data_type
        string status
        json context
        timestamp started_at
        timestamp completed_at
    }
    
    DataSource {
        uuid id PK
        uuid dno_id FK
        int year
        string data_type
        string source_url
        string file_path
        string content_hash
    }
    
    ExtractedData {
        uuid id PK
        uuid dno_id FK
        uuid source_id FK
        int year
        string data_type
        json data
        bool verified
    }
    
    DNO ||--o{ CrawlJob : has
    DNO ||--o{ DataSource : has
    DNO ||--o{ ExtractedData : has
    DataSource ||--o{ ExtractedData : produces
```

---

## UI States & Error Handling

| DNO State | UI Display | Action Available |
|-----------|------------|------------------|
| `crawlable=true, no_data` | "Ready to crawl" | Trigger Crawl |
| `crawlable=true, has_data` | "Data available" | View Data / Re-crawl |
| `crawlable=false, reason=cloudflare` | "⚠️ Site protected" | Manual Entry Only |
| `crawlable=false, reason=robots_blocked` | "🚫 Crawling disallowed" | Manual Entry Only |
| `job_status=running` | "⏳ Crawling..." | View Progress |
| `job_status=failed` | "❌ Crawl failed" | Retry / Manual Entry |

---

## Proposed Codebase Cleanup

### Current Issues
1. **Discovery logic split** across `web_crawler.py`, `sitemap_discovery.py`, `bfs_discovery_test.py`
2. **Inconsistent scoring** between BFS and sitemap discovery
3. **Skeleton creation** doesn't store robots.txt or crawlability flag
4. **Missing crawlability check** in job trigger

### Proposed Refactoring

#### Step 1: Consolidate Discovery Service
```
app/services/discovery/
├── __init__.py
├── base.py            # DiscoveryResult, DiscoveredDocument
├── sitemap.py         # SitemapDiscovery - sitemap-based
├── bfs.py             # BFSDiscovery - fallback crawler  
├── html_detector.py   # HTML embedded data detection
├── scorer.py          # Unified scoring algorithm
└── manager.py         # DiscoveryManager - orchestrates strategies
```

#### Step 2: Enhance DNO Model
- Add `robots_txt` (text field)
- Add `sitemap_urls` (JSON array)
- Add `disallow_paths` (JSON array)
- Add `crawlable` (boolean)
- Add `crawl_blocked_reason` (string)

#### Step 3: Update Skeleton Service
- Fetch and store full robots.txt
- Parse sitemap URLs
- Parse disallow rules
- Detect crawlability (Cloudflare, etc.)

#### Step 4: Add Crawlability Check
- API endpoint returns crawlability status
- Frontend disables crawl button if not crawlable
- Show reason to user

#### Step 5: Unify Scoring
- Single `score_url()` function used everywhere
- Same keywords, penalties across all discovery methods
- Configurable per data type

### Files to Modify/Create

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/services/discovery/manager.py` | Unified discovery orchestration |
| CREATE | `app/services/discovery/scorer.py` | Centralized scoring |
| MODIFY | `app/models.py` | Add DNO crawlability fields |
| MODIFY | `app/services/skeleton_service.py` | Store robots.txt, detect crawlability |
| MODIFY | `app/api/routes/crawl.py` | Check crawlability before job creation |
| DELETE | `tests/manual/bfs_discovery_test.py` | Move to proper test suite |
| MODIFY | `app/jobs/steps/step_01_discover.py` | Use new DiscoveryManager |

---

## Next Steps

1. **Review this flowchart** - Ensure it matches your vision
2. **Approve the cleanup plan** - Confirm the refactoring approach
3. **Implement in phases:**
   - Phase A: DNO model + skeleton enhancements
   - Phase B: Consolidated discovery service
   - Phase C: Frontend crawlability integration
   - Phase D: Cleanup deprecated code
