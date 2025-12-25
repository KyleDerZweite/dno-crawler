# System Architecture

## Overview
DNO Crawler is a full-stack application designed to extract, normalize, and serve data from German Distribution Network Operators (DNOs). It features a React frontend for user interaction and administration, and a FastAPI backend that orchestrates data retrieval via synchronous APIs and asynchronous background workers.

## 1. System Architecture

The system follows a modern microservices-lite architecture with a clear separation of concerns between the API layer, background processing, and data persistence.

```mermaid
flowchart TD
    %% Users
    User((Public User))
    Admin((Admin/Client))

    %% Frontend Layer
    subgraph Frontend ["Frontend Layer (React SPA)"]
        UI[User Interface]
        AuthProvider["Auth Provider<br/>(react-oidc-context)"]
        ApiClient["API Client<br/>(Axios Interceptors)"]
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
            AdminRoute[Admin Dashboard]
            FilesRoute[File Downloads]
            AuthRoute[Auth /me]
        end
        
        subgraph Services ["Service Layer"]
            SkeletonSvc[Skeleton Service]
            DNOResolver[DNO Resolver]
            VNBSvc[VNB Digital Client]
        end
    end

    %% Async Layer
    subgraph Async ["Async Worker Layer"]
        RedisQ[(Redis Queue)]
        Worker[ARQ Worker]
        PDFDownloader[PDF Downloader]
        LLMExtractor[LLM Extractor]
    end

    %% Data Layer
    subgraph Data ["Data Persistence"]
        Postgres[(PostgreSQL DB)]
        RedisCache[(Redis Cache)]
    end

    %% External Systems
    subgraph External ["External Systems"]
        VNBDigital[VNB Digital API]
        TargetSites[Target DNO Websites]
    end

    %% Connections
    User --> UI
    Admin --> UI
    UI --> AuthProvider
    AuthProvider <--> Zitadel
    UI --> ApiClient
    ApiClient --> |"JWT Token"| Gateway
    
    Gateway --> PublicAPI
    Gateway --> ProtectedAPI
    
    PublicAPI --> SkeletonSvc
    ProtectedAPI --> RedisQ
    
    SkeletonSvc --> VNBSvc
    VNBSvc <--> VNBDigital
    
    RedisQ --> Worker
    Worker --> PDFDownloader
    Worker --> LLMExtractor
    PDFDownloader <--> TargetSites
    
    SkeletonSvc --> Postgres
    Worker --> Postgres
    PublicAPI --> RedisCache
    
    classDef frontend fill:#e1f5fe,stroke:#01579b
    classDef backend fill:#fff3e0,stroke:#e65100
    classDef data fill:#e8f5e9,stroke:#1b5e20
    classDef external fill:#f3e5f5,stroke:#4a148c
    
    class UI,AuthProvider,ApiClient frontend
    class Gateway,PublicAPI,ProtectedAPI,Services,Async backend
    class Postgres,RedisCache,RedisQ data
    class Zitadel,VNBDigital,TargetSites external
```

### Key Components
- **Frontend**: Handles OIDC authentication flow and attaches JWT tokens to requests via Axios interceptors. Supports a "No-Auth" fallback for simplified local development.
- **Public API**: Allows unauthenticated users to perform rate-limited searches and generate skeleton DNO records.
- **Protected API**: Secured by `Depends(get_current_user)`, allowing admins/members to trigger crawls and manage data. The authentication strategy is modular (Zitadel OIDC vs. Mock Admin).
- **Async Worker**: Powered by ARQ and Redis, this component handles long-running tasks like crawling, PDF downloading, and LLM extraction to prevent blocking the HTTP API.

---

## 2. Core User Journey

This sequence demonstrates the flow from a user logging in to retrieving complex dataset extraction results.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as Frontend (React)
    participant Auth as Zitadel / Auth
    participant API as Backend API
    participant DB as Database
    participant Redis as Redis Queue
    participant Worker as ARQ Worker
    
    %% Login Flow
    Note over User, Auth: Authentication Phase
    User->>Frontend: Click "Login"
    Frontend->>Auth: Redirect to OIDC Provider
    Auth->>User: Login Prompt
    User->>Auth: Credentials
    Auth->>Frontend: Callback with Code
    Frontend->>Frontend: Exchange Code for Token
    Frontend->>API: GET /auth/me (Verify Token)
    API-->>Frontend: 200 OK (User Info)

    %% Search Flow
    Note over User, Worker: Search & Crawl Phase
    User->>Frontend: Enter Address "Musterstr. 1, Berlin"
    Frontend->>API: POST /api/v1/search
    API->>DB: Check Location Cache
    alt Cache Miss
        API->>API: Call VNB Digital API
        API->>DB: Create Skeleton DNO Record
    end
    API-->>Frontend: 202 Accepted (Skeleton Returned)
    
    %% Crawl Trigger
    User->>Frontend: Click "Request Data" (Trigger Crawl)
    Frontend->>API: POST /api/v1/dnos/{id}/crawl
    API->>DB: Create CrawlJob (Status: Pending)
    API->>Redis: Enqueue 'crawl_dno_job'
    API-->>Frontend: 201 Created (Job ID)
    
    %% Async Processing
    Redis->>Worker: Pick up Job
    Worker->>DB: Update Job (Status: Running)
    
    loop Extraction Process
        Worker->>Worker: Resolve PDF URLs
        Worker->>Worker: Download & Parse PDF
        Worker->>Worker: Extract Data (LLM/Regex)
    end
    
    Worker->>DB: Save Netzentgelte & HLZF Data
    Worker->>DB: Update Job (Status: Completed)
    
    %% Result Retrieval
    loop Polling
        Frontend->>API: GET /api/v1/dnos/{id}/jobs
        API-->>Frontend: Job Status (Running -> Completed)
    end
    
    Frontend->>API: GET /api/v1/dnos/{id}/data
    API->>DB: Fetch Netzentgelte & HLZF
    DB-->>API: Return Data
    API-->>Frontend: Display Data Tables
```

---

## 3. Database Schema

The database is normalized to support efficient spatial lookups and historical data versioning.

```mermaid
erDiagram
    users ||--o{ crawl_jobs : "triggers"
    users {
        string id PK "Zitadel Subject ID"
        string email
        string role
    }

    dnos ||--o{ locations : "serves"
    dnos ||--o{ netzentgelte : "has"
    dnos ||--o{ hlzf : "has"
    dnos ||--o{ crawl_jobs : "target of"
    dnos ||--|{ crawl_configs : "configured by"
    
    dnos {
        int id PK
        string slug UK
        string name
        string vnb_id UK
        string status
        datetime crawl_locked_at
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
        float leistung
        float arbeit
        string verification_status
    }

    hlzf {
        int id PK
        int dno_id FK
        int year
        string voltage_level
        string winter
        string fruehling
        string sommer
        string herbst
    }

    crawl_jobs ||--o{ crawl_job_steps : "contains"
    crawl_jobs {
        int id PK
        int dno_id FK
        string user_id
        string status
        int priority
        string error_message
    }

    crawl_job_steps {
        int id PK
        int job_id FK
        string step_name
        string status
        json details
    }
    
    crawl_configs {
        int id PK
        int dno_id FK
        string crawl_type
        bool auto_crawl
    }
```

### Key Entities
- **DNOModel (`dnos`)**: The core entity representing a utility provider. Contains VNB Digital integration IDs and crawling status.
- **LocationModel (`locations`)**: Maps addresses and coordinates to DNOs. Uses `address_hash` for efficient lookup and caching of VNB Digital results.
- **Data Tables (`netzentgelte`, `hlzf`)**: Store the extracted pricing and time-window data, linked to DNOs and specific years.
- **Job Tracking (`crawl_jobs`)**: Manages the state of background tasks, providing visibility into the long-running extraction process.
