# AI AGENT OPERATIONAL PROTOCOL

## 1. Context & Knowledge Retrieval
**DO NOT HALLUCINATE.** You are strictly bound by the Source of Truth documentation. Before generating code, planning features, or answering questions, you must ingest the context from the following files:

* **Project Scope & API:** `docs/PROJECT.md`
* **System Architecture & DB Schema:** `docs/ARCHITECTURE.md`
* **Setup & Commands:** `README.md` (Root level)

## 2. Standards & Conventions
You must strictly adhere to the standards defined in the `docs/` directory. Do not use generic conventions if a specific project standard exists.

* **Naming Standards:** `docs/FILE_NAMING_CONVENTIONS.md`
    * *Governs: Files, classes, variables, functions, and directory structure.*
* **Logging & Tracing:** `docs/LOGGING_CONVENTIONS.md`
    * *Governs: Structured logging, log levels, and "Wide Events" patterns.*

## 3. Development Workflow
When assigned a task, follow this loop:

1.  **Analysis:** Check `docs/PROJECT.md` for context and `README.md` for available scripts.
2.  **Plan:** Briefly outline proposed changes. Check `docs/ARCHITECTURE.md` to ensure architectural consistency.
3.  **Implementation:**
    * Apply the KISS principle (Keep It Simple, Stupid).
    * Follow naming rules in `docs/FILE_NAMING_CONVENTIONS.md`.
    * Implement observability per `docs/LOGGING_CONVENTIONS.md`.
    * **No hard-coded secrets.**
4.  **Verification:**
    * Ensure new code passes linting and tests defined in the root `README.md`.

## 4. Tech Stack Autonomy
Do not rely on text descriptions of the stack. Determine the active versioning and dependencies by inspecting the live configuration files:
* **Backend:** `pyproject.toml` / `requirements.txt`
* **Frontend:** `package.json` / `vite.config.ts`
* **Infrastructure:** `docker-compose.yml`

## 5. Interaction Guidelines
* **Output Style:** Provide short, detailed, and technical responses. Exclude verbose feedback loops and internal summaries. Only state relevant information.
* **Tone:** Maintain a strictly professional and enterprise grade tone. **DO NOT USE EMOJIS.** Avoid informal sentence structures and dashes within sentences.
* **Reference Strategy:** Link to relevant `docs/` files instead of duplicating explanations.
* **Design Philosophy:** Strictly adhere to the KISS principle. Prefer modular and single responsibility functions.
* **Defensive Coding:** Always validate inputs (Zod/Pydantic) and handle errors gracefully.