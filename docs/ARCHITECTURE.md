# System Architecture

## Overview

DNO Crawler is a full-stack application for automated extraction of regulatory data from German Distribution Network Operators (DNOs). The system features a React SPA frontend for user interaction and a FastAPI backend that orchestrates data retrieval via synchronous APIs and asynchronous background workers.

## 1. System Architecture

The system follows a microservices-lite architecture with clear separation between the API layer, background processing, and data persistence.

```mermaid
flowchart TD
    %% Users
    User((Public User))
    Admin((Authenticated User))

    %% Frontend Layer
    subgraph Frontend ["Frontend Layer (React SPA)"]
        UI[User Interface]
        AuthProvider["Auth Provider<br/>(react-oidc-context)"]
        ApiClient["API Client<br/>(Axios + TanStack Query)"]
    end

    %% Auth Provider
    Zitadel[Zitadel OIDC Provider]

    %% Backend Layer
    subgraph Backend ["Backend Layer (FastAPI)"]
        Gateway[API Gateway / Main]
        
        subgraph PublicAPI ["Public API Layer"]
            SearchRoute[POST /api/v1/search]
            HealthRoute[GET /health]
        end

        subgraph ProtectedAPI ["Protected API Layer"]
            DNORoute[DNO Management]
            JobsRoute[Job Tracking]
            AdminRoute[Admin Dashboard]
            FilesRoute[File Downloads]
            VerifyRoute[Data Verification]
        end
        
        subgraph Services ["Service Layer"]
            SkeletonSvc[Skeleton Service]
            VNBSvc[VNB Digital Client]
            BDEWSvc[BDEW Client]
            MaStRSvc[MaStR Seed Importer]
        end
    end

    %% Async Layer
    subgraph Async ["Async Worker Layer"]
        RedisQ[(Redis Queue)]
        Worker[arq Worker]
        subgraph Pipeline ["Extraction Pipeline"]
            DiscoverStep[Step 01: Discover]
            DownloadStep[Step 03: Download]
            ExtractStep[Step 04: Extract]
            ValidateStep[Step 05: Validate]
        end
    end

    %% Data Layer
    subgraph Data ["Data Persistence"]
        Postgres[(PostgreSQL)]
        RedisCache[(Redis Cache)]
        FileStorage[(Local File Storage)]
    end

    %% External Systems
    subgraph External ["External Systems"]
        VNBDigital[VNB Digital GraphQL API]
        BDEWRegistry[BDEW JTables Endpoint]
        TargetSites[Target DNO Websites]
    end

    %% Connections
    User --> UI
    Admin --> UI
    UI --> AuthProvider
    AuthProvider <--> Zitadel
    UI --> ApiClient
    ApiClient --> |"JWT Bearer Token"| Gateway
    
    Gateway --> PublicAPI
    Gateway --> ProtectedAPI
    
    PublicAPI --> SkeletonSvc
    ProtectedAPI --> RedisQ
    
    SkeletonSvc --> VNBSvc
    SkeletonSvc --> BDEWSvc
    VNBSvc <--> VNBDigital
    BDEWSvc <--> BDEWRegistry
    
    RedisQ --> Worker
    Worker --> Pipeline
    Pipeline <--> TargetSites
    
    SkeletonSvc --> Postgres
    Worker --> Postgres
    Worker --> FileStorage
    PublicAPI --> RedisCache
    
    classDef frontend fill:#e1f5fe,stroke:#01579b
    classDef backend fill:#fff3e0,stroke:#e65100
    classDef data fill:#e8f5e9,stroke:#1b5e20
    classDef external fill:#f3e5f5,stroke:#4a148c
    
    class UI,AuthProvider,ApiClient frontend
    class Gateway,PublicAPI,ProtectedAPI,Services,Async backend
    class Postgres,RedisCache,RedisQ,FileStorage data
    class Zitadel,VNBDigital,BDEWRegistry,TargetSites external
```

### Key Components

- **Frontend**: React SPA with OIDC authentication via react-oidc-context. Attaches JWT tokens to requests via Axios interceptors. TanStack Query manages server state with automatic caching and polling.
- **Public API**: Rate-limited endpoints for address search and skeleton DNO creation. No authentication required.
- **Protected API**: Secured by `Depends(get_current_user)`. Provides DNO management, job triggering, data verification, and admin functions.
- **Service Layer**: Integrates with three external data sources:
  - **VNB Digital**: GraphQL API for real-time address-to-DNO resolution
  - **BDEW Registry**: JTables endpoint (POST request interception) for BDEW codes
  - **MaStR Importer**: Processes manual CSV/XML exports from Bundesnetzagentur
- **Async Worker**: arq-powered Redis worker executes multi-step extraction pipeline without blocking HTTP requests.

---

## 2. Core User Journey

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as Frontend (React)
    participant Auth as Zitadel / Mock Auth
    participant API as Backend API
    participant DB as PostgreSQL
    participant Redis as Redis Queue
    participant Worker as arq Worker
    participant DNOSite as DNO Website
    
    %% Login Flow
    Note over User, Auth: Authentication Phase
    User->>Frontend: Click "Login"
    Frontend->>Auth: Redirect to OIDC Provider
    Auth->>User: Login Prompt
    User->>Auth: Credentials
    Auth->>Frontend: Callback with Authorization Code
    Frontend->>Frontend: Exchange Code for Token
    Frontend->>API: GET /auth/me (Verify Token)
    API-->>Frontend: 200 OK (User Info)

    %% Search Flow
    Note over User, Worker: Search & DNO Resolution
    User->>Frontend: Enter Address "Musterstr. 1, Berlin"
    Frontend->>API: POST /api/v1/search
    API->>DB: Check Location Cache (address_hash)
    alt Cache Miss
        API->>API: Query VNB Digital GraphQL API
        API->>DB: Create/Update DNO Record
        API->>DB: Cache Location
    end
    API-->>Frontend: 200 OK (DNO with Data Preview)
    
    %% Crawl Trigger
    Note over User, Worker: Data Extraction Pipeline
    User->>Frontend: Click "Trigger Crawl"
    Frontend->>API: POST /api/v1/dnos/{id}/crawl
    API->>DB: Create CrawlJob (Status: pending)
    API->>Redis: Enqueue 'run_crawl_job'
    API-->>Frontend: 201 Created (Job ID)
    
    %% Async Processing
    Redis->>Worker: Dequeue Job
    Worker->>DB: Update Job (Status: running)
    
    Worker->>Worker: Step 00: Gather Context
    Worker->>Worker: Step 01: Discover Source
    alt Cached URL Pattern
        Worker->>Worker: Try learned URL with year substitution
    else BFS Crawl
        Worker->>DNOSite: BFS crawl with keyword scoring
    end
    
    Worker->>DNOSite: Step 03: Download File
    Worker->>Worker: Step 04: Extract (Regex first, AI fallback)
    Worker->>Worker: Step 05: Validate
    Worker->>DB: Step 06: Save Netzentgelte & HLZF
    Worker->>DB: Update Job (Status: completed)
    
    %% Result Retrieval
    loop Polling (TanStack Query)
        Frontend->>API: GET /api/v1/jobs/{id}
        API-->>Frontend: Job Status
    end
    
    Frontend->>API: GET /api/v1/dnos/{id}
    API->>DB: Fetch DNO with Netzentgelte & HLZF
    DB-->>API: Return Data
    API-->>Frontend: Display Data Tables
```

---

## 3. External Data Sources

The system aggregates DNO metadata from three authoritative sources using a hub-and-spoke pattern.

```mermaid
erDiagram
    DNO ||--o| DNOMastrData : "has"
    DNO ||--o| DNOVnbData : "has"
    DNO ||--o{ DNOBdewData : "has"
    
    DNO {
        int id PK
        string slug UK
        string name "Best available"
        string mastr_nr UK "Quick lookup"
        string vnb_id UK "Quick lookup"
        string primary_bdew_code "Quick lookup"
    }
    
    DNOMastrData {
        int id PK
        int dno_id FK
        string mastr_nummer UK
        string firmenname
        json raw_data "Full MaStR export"
    }
    
    DNOVnbData {
        int id PK
        int dno_id FK
        string vnb_id UK
        string official_name
        string homepage_url
        string phone
        string email
    }
    
    DNOBdewData {
        int id PK
        int dno_id FK
        string bdew_code
        string function_code
        bool is_grid_operator
    }
```

| Source | Method | Update Frequency | Data Provided |
|--------|--------|------------------|---------------|
| **VNB Digital** | GraphQL API queries | Real-time | Address resolution, official names, homepage URLs, contact info |
| **Marktstammdatenregister** | Manual XML/CSV export | Periodic (manual) | Market roles (Marktrollen), ACER codes, legal names, registered addresses |
| **BDEW Codes Registry** | JTables POST interception | On-demand | BDEW identification codes, grid operator function codes |

---

## 4. Database Schema

```mermaid
erDiagram
    dnos ||--o{ locations : "serves"
    dnos ||--o{ netzentgelte : "has"
    dnos ||--o{ hlzf : "has"
    dnos ||--o{ crawl_jobs : "target of"
    dnos ||--o{ dno_source_profiles : "configured by"
    
    dnos {
        int id PK
        string slug UK
        string name
        string official_name
        string website
        string mastr_nr UK
        string vnb_id UK
        string primary_bdew_code
        string status "uncrawled|crawled|error"
        bool crawlable
        string crawl_blocked_reason
        text robots_txt
        json sitemap_urls
        json disallow_paths
    }

    locations {
        int id PK
        int dno_id FK
        string address_hash UK
        string zip_code
        string city
        decimal latitude
        decimal longitude
    }

    netzentgelte {
        int id PK
        int dno_id FK
        int year
        string voltage_level
        float arbeit "ct/kWh"
        float leistung "EUR/kW"
        string extraction_source "ai|pdf_regex|html_parser|manual"
        string extraction_model "gemini-2.0-flash|etc"
        string verification_status
    }

    hlzf {
        int id PK
        int dno_id FK
        int year
        string voltage_level
        text winter
        text fruehling
        text sommer
        text herbst
        string extraction_source
    }

    crawl_jobs ||--o{ crawl_job_steps : "contains"
    crawl_jobs {
        int id PK
        int dno_id FK
        int year
        string data_type "netzentgelte|hlzf"
        string status "pending|running|completed|failed"
        int progress
        string current_step
        json context
    }

    crawl_job_steps {
        int id PK
        int job_id FK
        string step_name
        string status
        json details
        int duration_seconds
    }
    
    dno_source_profiles {
        int id PK
        int dno_id FK
        string data_type
        string source_format "pdf|html|xlsx"
        string url_pattern "URL with {year} placeholder"
        string discovery_method "pattern_match|bfs_crawl|exact_url"
    }
    
    crawl_path_patterns {
        int id PK
        string path_pattern UK "e.g. /downloads/{year}/netzentgelte.pdf"
        string data_type
        int success_count
        int fail_count
    }

    data_sources {
        int id PK
        int dno_id FK
        int year
        string data_type
        string source_url
        string file_path
        string file_hash
        string extraction_method
    }
```

### Key Entities

- **DNOModel (`dnos`)**: Hub entity in a hub-and-spoke pattern. Contains resolved display fields (best values from MaStR/VNB/BDEW), quick-access external IDs, and crawlability metadata.
- **Source Data Tables**: `dno_mastr_data`, `dno_vnb_data`, `dno_bdew_data` store raw data from each external source.
- **LocationModel (`locations`)**: Maps addresses and coordinates to DNOs. Uses `address_hash` for O(1) cache lookups.
- **Data Tables (`netzentgelte`, `hlzf`)**: Extracted pricing and time-window data with provenance tracking (extraction source, model used).
- **Source Profiles (`dno_source_profiles`)**: Per-DNO learned patterns for fast re-crawling.
- **Path Patterns (`crawl_path_patterns`)**: Cross-DNO URL patterns with success/failure statistics for prioritized discovery.
- **Job Tracking (`crawl_jobs`, `crawl_job_steps`)**: State machine for background tasks with step-level granularity.

---

## 5. Extraction Pipeline

The extraction layer implements a cost-aware, deterministic-first approach.

```mermaid
flowchart TD
    FILE[Downloaded File] --> EXT{File Type?}
    
    EXT --> |"PDF"| PDF_REGEX[PDF Regex Extraction<br/>pdfplumber + patterns]
    EXT --> |"HTML"| HTML_PARSE[HTML Parser<br/>BeautifulSoup + CSS selectors]
    EXT --> |"XLSX"| EXCEL[Excel Parser<br/>pandas/openpyxl]
    
    PDF_REGEX --> VALIDATE{Sanity Check}
    HTML_PARSE --> VALIDATE
    EXCEL --> VALIDATE
    
    VALIDATE --> |"Pass"| SAVE[Save to Database]
    VALIDATE --> |"Fail"| AI_CHECK{AI Configured?}
    
    AI_CHECK --> |"No"| FAIL[Mark Extraction Failed]
    AI_CHECK --> |"Yes"| AI_PREP[Pre-filter PDF Pages]
    
    AI_PREP --> AI[AI Vision/Text Extraction<br/>OpenAI-compatible API]
    AI --> AI_VALIDATE{Sanity Check}
    
    AI_VALIDATE --> |"Pass"| SAVE
    AI_VALIDATE --> |"Fail"| FAIL
```

### Sanity Validation Rules

| Data Type | Rule |
|-----------|------|
| Netzentgelte | ≥3 voltage levels, each with at least one price value (arbeit or leistung) |
| HLZF | ≥1 record with winter time window present |

### AI Optimization

1. Extract text from each PDF page using pdfplumber
2. Filter pages containing target keywords (reduces payload by 60-80%)
3. Send optimized PDF to vision model
4. If no data found, retry with full PDF before falling back to failure

---

## 6. Security Architecture

- **Authentication**: OIDC-based via Zitadel. Frontend handles redirect flow and attaches Bearer tokens via Axios interceptors. Mock mode available for development.
- **Authorization**: Role-based access control via `Depends(get_current_user)` and `Depends(require_admin)`.
- **Secret Management**: All credentials managed via environment variables and `.env` files.
- **Rate Limiting**: IP-based rate limiting on public endpoints. Per-user quotas on protected endpoints.
- **Data Protection**: PostgreSQL connections use SSL in production. File storage uses content hashing for integrity verification.

---

## 7. Observability

- **Logging**: Structured JSON logging via `structlog` with correlation IDs for request tracing.
- **Health Endpoint**: `GET /api/v1/health` returns service status for uptime monitoring.
- **Job Visibility**: Real-time step-by-step progress via `crawl_jobs` and `crawl_job_steps` tables, exposed through polling API.
- **Query Logging**: `query_logs` table tracks user searches for analytics.

---

## 8. Production Maintenance

### Database Migrations

Schema changes are versioned via Alembic:

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Crawl Job Recovery

The `crawl_recovery` service automatically resets jobs stuck in `running` or `crawling` state on backend startup, handling worker crashes or unexpected restarts.

### Container Health Checks

All services in `docker-compose.yml` include health checks:

- **PostgreSQL**: `pg_isready`
- **Redis**: `redis-cli ping`
- **Backend**: `curl /api/health`
