# DNO Crawler - Pipeline Flowchart

This document describes the complete extraction pipeline from user input to structured data.

---

## Overview

```mermaid
flowchart TB
    subgraph Input["1. User Input"]
        A1[Address] --> SEARCH
        A2[Coordinates] --> SEARCH
        A3[DNO Name] --> SEARCH
    end
    
    SEARCH[POST /api/v1/search] --> VNB[VNB Digital GraphQL]
    
    subgraph Skeleton["2. DNO Resolution"]
        VNB --> DNO[DNO Record]
        DNO --> ENRICH[Enrichment Job]
        ENRICH --> ROB[Fetch robots.txt]
        ENRICH --> IMP[Fetch Impressum]
        ROB --> CRAWL{Crawlable?}
    end
    
    subgraph Discovery["3. Data Discovery"]
        CRAWL --> |"Yes"| STRATEGY{Discovery Strategy}
        CRAWL --> |"No: Cloudflare"| MANUAL[Manual File Upload]
        STRATEGY --> |"Cached Pattern"| PATTERN[Try URL Pattern]
        STRATEGY --> |"No Pattern"| BFS[BFS Crawl]
        PATTERN --> VERIFY[Verify Content]
        BFS --> VERIFY
    end
    
    subgraph Download["4. Download"]
        VERIFY --> TYPE{File Type?}
        MANUAL --> TYPE
        TYPE --> |"PDF"| DL_PDF[Download PDF]
        TYPE --> |"HTML"| DL_HTML[Strip & Save HTML]
        TYPE --> |"Excel"| DL_EXCEL[Download Excel]
    end
    
    subgraph Extract["5. Extraction"]
        DL_PDF --> REGEX[Regex Extraction]
        DL_HTML --> REGEX
        DL_EXCEL --> PANDAS[Pandas Extraction]
        REGEX --> SANITY{Sanity Check}
        PANDAS --> SANITY
        SANITY --> |"Pass"| DATA[Structured Data]
        SANITY --> |"Fail"| AI{AI Configured?}
        AI --> |"Yes"| AI_EXT[AI Vision/Text]
        AI --> |"No"| FAIL[Mark Failed]
        AI_EXT --> DATA
    end
    
    DATA --> DB[(PostgreSQL)]
    DATA --> PROFILE[Update Source Profile]
```

---

## Phase 1: Search & DNO Resolution

```mermaid
flowchart LR
    subgraph Input["User Input"]
        A[Address] 
        B[Coordinates]
        C[DNO Name]
    end
    
    Input --> API[POST /api/v1/search]
    
    API --> CACHE{Location Cache Hit?}
    CACHE --> |"Yes"| EXISTING[Return Cached DNO]
    CACHE --> |"No"| VNB[Query VNB Digital API]
    
    VNB --> FOUND{DNO Found?}
    FOUND --> |"Yes"| CHECK{DNO in DB?}
    FOUND --> |"No"| ERR[Error: Not Found]
    
    CHECK --> |"Yes"| UPDATE[Update Existing]
    CHECK --> |"No"| CREATE[Create Skeleton]
    
    UPDATE --> ENRICH[Queue Enrichment Job]
    CREATE --> ENRICH
```

**VNB Digital Response:**
- `kurzbezeichnung` → Display name
- `vnb_id` → External identifier
- `homepage` → Website URL
- `telefon`, `email` → Contact info
- Address components for location caching

---

## Phase 2: DNO Enrichment

```mermaid
flowchart TD
    START[Enrichment Job] --> VNB[Fetch VNB Details]
    VNB --> ROBOTS[Fetch robots.txt]
    
    subgraph RobotsCheck["robots.txt Analysis"]
        ROBOTS --> RESP{Response Type?}
        RESP --> |"200 OK"| PARSE[Parse Content]
        RESP --> |"403 + JS"| CF[Cloudflare Detected]
        RESP --> |"404"| NONE[No robots.txt]
        
        PARSE --> SITEMAP[Extract Sitemap URLs]
        PARSE --> DISALLOW[Extract Disallow Paths]
        
        CF --> FLAG["crawlable = false<br/>reason = 'cloudflare'"]
        NONE --> CRAWLABLE["crawlable = true"]
        SITEMAP --> CRAWLABLE
    end
    
    subgraph ImpressumCheck["Impressum Extraction"]
        CRAWLABLE --> IMP[Fetch /impressum]
        IMP --> IMP_OK{Success?}
        IMP_OK --> |"Yes"| ADDR[Extract Address]
        IMP_OK --> |"No"| SKIP[Skip]
    end
    
    FLAG --> SAVE
    ADDR --> SAVE
    SKIP --> SAVE
    
    SAVE[/"Update DNO:<br/>- robots_txt (full text)<br/>- sitemap_urls[]<br/>- disallow_paths[]<br/>- crawlable: bool<br/>- contact_address"/]
```

---

## Phase 3: Crawl Job Trigger

```mermaid
flowchart TD
    USER[User Clicks Crawl] --> CHECK{DNO Crawlable?}
    
    CHECK --> |"No"| HAS_LOCAL{Has Local Files?}
    HAS_LOCAL --> |"Yes"| USE_LOCAL[Use Uploaded Files]
    HAS_LOCAL --> |"No"| BLOCKED["Show: Site protected<br/>Upload files manually"]
    
    CHECK --> |"Yes"| PROFILE{Has Source Profile?}
    
    PROFILE --> |"Yes + Recent"| PATTERN[Try Cached URL Pattern]
    PROFILE --> |"No or Stale"| FULL_CRAWL[Full Discovery]
    
    PATTERN --> JOB[Create CrawlJob]
    FULL_CRAWL --> JOB
    USE_LOCAL --> JOB
    
    JOB --> QUEUE[Enqueue to Redis]
    QUEUE --> WORKER[arq Worker Picks Up]
```

---

## Phase 4: Discovery Pipeline

```mermaid
flowchart TD
    START[Step 01: Discover] --> CTX[Load DNO Context]
    
    CTX --> LOCAL{Local File Exists?}
    LOCAL --> |"Yes"| USE_FILE[Skip Discovery]
    LOCAL --> |"No"| PROFILE{Has Source Profile?}
    
    PROFILE --> |"Yes"| TRY_PATTERN[Try URL Pattern with Year]
    PROFILE --> |"No"| SITEMAP{Has Sitemap URLs?}
    
    TRY_PATTERN --> VERIFY{Content Valid?}
    VERIFY --> |"Yes"| FOUND[Source Found]
    VERIFY --> |"No"| SITEMAP
    
    SITEMAP --> |"Yes"| PARSE_SM[Parse Sitemap XML]
    SITEMAP --> |"No"| BFS[BFS Crawl from Homepage]
    
    PARSE_SM --> SCORE[Score URLs by Keywords]
    BFS --> SCORE
    
    SCORE --> TOP[Take Top Candidates]
    TOP --> PROBE[HEAD Request Each]
    PROBE --> CONTENT{Content-Type OK?}
    CONTENT --> |"Yes"| FOUND
    CONTENT --> |"No"| NEXT[Try Next Candidate]
    NEXT --> |"More"| PROBE
    NEXT --> |"None Left"| FAIL[Discovery Failed]
```

**URL Scoring Algorithm:**

| Factor | Score |
|--------|-------|
| PDF file extension | +20 |
| Excel file extension | +15 |
| Target year in URL | +25 |
| Keyword match (netzentgelte, strom, hlzf) | +15 each |
| Negative keyword (gas, vermiedene) | -15 to -30 |
| Shallow depth (≤2) | +10 |

---

## Phase 5: Download

```mermaid
flowchart TD
    SOURCE[Discovered Source URL] --> TYPE{Content Type?}
    
    TYPE --> |"application/pdf"| DL_PDF[Download PDF]
    TYPE --> |"text/html"| CHECK_HTML[Check for Embedded Data]
    TYPE --> |"application/xlsx"| DL_XLS[Download Excel]
    
    CHECK_HTML --> TABLES{Has Data Tables?}
    TABLES --> |"Yes"| STRIP[Strip HTML - Keep Tables]
    TABLES --> |"No"| NEXT[Try Next Candidate]
    
    DL_PDF --> SAVE
    STRIP --> SAVE
    DL_XLS --> SAVE
    
    SAVE[/"Save to:<br/>data/downloads/{slug}/{slug}-{type}-{year}.{ext}"/]
    
    SAVE --> RECORD[Record DataSource]
```

**HTML Table Detection:**
- Look for `<table>` elements
- Check for keywords: "hochlast", "zeitfenster", "netzentgelt"
- Check for voltage levels: "HS", "MS", "NS", "Umspannung"
- Check for year patterns: "gültig ab 01.01.2025"

---

## Phase 6: Extraction

```mermaid
flowchart TD
    FILE[Downloaded File] --> FORMAT{File Format?}
    
    FORMAT --> |"PDF"| PDF[PDFExtractor<br/>pdfplumber + regex]
    FORMAT --> |"HTML"| HTML[HTMLExtractor<br/>BeautifulSoup]
    FORMAT --> |"Excel"| EXCEL[pandas/openpyxl]
    
    PDF --> DATA[Extracted Records]
    HTML --> DATA
    EXCEL --> DATA
    
    DATA --> SANITY{Sanity Check}
    
    SANITY --> |"Pass"| SAVE[Save to Database]
    SANITY --> |"Fail"| AI_CHECK{AI Configured?}
    
    AI_CHECK --> |"No"| LOG_FAIL[Log Failure]
    AI_CHECK --> |"Yes"| OPTIMIZE[Pre-filter PDF Pages]
    
    OPTIMIZE --> AI[AIExtractor<br/>OpenAI Vision API]
    AI --> AI_DATA[AI Extracted Records]
    AI_DATA --> AI_SANITY{Sanity Check}
    
    AI_SANITY --> |"Pass"| SAVE
    AI_SANITY --> |"Fail"| LOG_FAIL
    
    SAVE --> PROFILE[Update Source Profile]
    SAVE --> PATTERN[Record Path Pattern]
```

**Sanity Check Rules:**

| Data Type | Validation |
|-----------|------------|
| Netzentgelte | ≥3 voltage levels, each with arbeit OR leistung non-null |
| HLZF | ≥1 record with winter time window present |

**AI PDF Optimization:**
1. Extract text from each page
2. Filter pages containing target keywords
3. Create optimized PDF (60-80% smaller)
4. Send to vision model
5. If empty result, retry with full PDF

---

## Phase 7: Finalization

```mermaid
flowchart TD
    DATA[Validated Data] --> SAVE_NE[Save Netzentgelte Records]
    DATA --> SAVE_HLZF[Save HLZF Records]
    
    SAVE_NE --> META[Record Extraction Metadata]
    SAVE_HLZF --> META
    
    META --> |"extraction_source"| SRC["ai | pdf_regex | html_parser"]
    META --> |"extraction_model"| MODEL["gemini-2.0-flash | etc"]
    
    SRC --> PROFILE[Update DNO Source Profile]
    PROFILE --> |"url_pattern"| PATTERN["Store URL with {year} placeholder"]
    PROFILE --> |"discovery_method"| METHOD["pattern_match | bfs_crawl"]
    
    PATTERN --> GLOBAL[Update Global Path Patterns]
    GLOBAL --> |"success_count++"| STATS[Track Success Rate]
    
    STATS --> JOB[Mark Job Completed]
```

---

## Error Handling & Fallbacks

```mermaid
flowchart LR
    subgraph Discovery
        D1[Cached Pattern] --> |"Failed"| D2[Sitemap Parse]
        D2 --> |"Failed"| D3[BFS Crawl]
        D3 --> |"Failed"| D4[Manual Upload Required]
    end
    
    subgraph Extraction
        E1[Regex/Parser] --> |"Sanity Fail"| E2[AI Fallback]
        E2 --> |"Sanity Fail"| E3[Manual Edit Required]
    end
    
    subgraph AI
        A1[Optimized PDF] --> |"No Data"| A2[Full PDF Retry]
        A2 --> |"No Data"| A3[Text Mode]
        A3 --> |"No Data"| A4[Mark Failed]
    end
```

---

## Database Entities

```mermaid
erDiagram
    DNO ||--o{ CrawlJob : "has"
    DNO ||--o{ DNOSourceProfile : "has"
    DNO ||--o{ DataSource : "produces"
    DNO ||--o{ Netzentgelte : "has"
    DNO ||--o{ HLZF : "has"
    
    CrawlJob ||--o{ CrawlJobStep : "contains"
    DataSource ||--o| Netzentgelte : "extracted"
    DataSource ||--o| HLZF : "extracted"
    
    DNO {
        int id PK
        string slug
        string website
        bool crawlable
    }
    
    DNOSourceProfile {
        int id PK
        int dno_id FK
        string data_type
        string url_pattern
        string discovery_method
    }
    
    CrawlJob {
        int id PK
        int dno_id FK
        int year
        string data_type
        string status
        json context
    }
    
    DataSource {
        int id PK
        int dno_id FK
        string source_url
        string file_path
        string extraction_method
    }
```

---

## UI States

| DNO State | UI Display | Available Actions |
|-----------|------------|-------------------|
| `crawlable=true, no_data` | "Ready to crawl" | Trigger Crawl |
| `crawlable=true, has_data` | Data tables shown | View/Edit Data, Re-crawl |
| `crawlable=false, has_local_files` | "Files uploaded" | Extract from Files |
| `crawlable=false, no_files` | "Site protected" | Upload Files |
| `job_status=running` | Progress indicator | View Steps |
| `job_status=failed` | Error message | Retry, Manual Edit |
