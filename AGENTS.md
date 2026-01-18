# AI Agent Operational Protocol

## 1. Context and Knowledge Retrieval

**DO NOT HALLUCINATE.** You are strictly bound by the Source of Truth documentation. Before generating code, planning features, or answering questions, you must ingest the context from the following files.

| Document | Purpose |
|----------|---------|
| `docs/PROJECT.md` | Project scope, API reference, and directory structure |
| `docs/ARCHITECTURE.md` | System design, data flow diagrams, and database schema |
| `README.md` | Installation guide and available development commands |

## 2. Standards and Conventions

You must strictly adhere to the standards defined in the `docs/` directory. Do not use generic conventions if a specific project standard exists.

| Standard | Scope |
|----------|-------|
| `docs/FILE_NAMING_CONVENTIONS.md` | Files, classes, variables, functions, and directory structure |
| `docs/LOGGING_CONVENTIONS.md` | Structured logging, log levels, and Wide Events patterns |

## 3. Development Workflow

When assigned a task, follow this loop.

1. **Analysis** Check `docs/PROJECT.md` for context and `README.md` for available scripts.
2. **Plan** Briefly outline proposed changes. Check `docs/ARCHITECTURE.md` to ensure architectural consistency.
3. **Implementation**
   - Apply the KISS principle (Keep It Simple, Stupid).
   - Follow naming rules in `docs/FILE_NAMING_CONVENTIONS.md`.
   - Implement observability per `docs/LOGGING_CONVENTIONS.md`.
   - Do not hard code secrets.
4. **Verification** Ensure new code passes linting and tests defined in the root `README.md`.

## 4. Tech Stack Autonomy

Do not rely on text descriptions of the stack. Determine the active versioning and dependencies by inspecting the live configuration files.

| Component | Configuration File |
|-----------|-------------------|
| Backend | `backend/pyproject.toml` |
| Frontend | `frontend/package.json` and `frontend/vite.config.ts` |
| Infrastructure | `docker-compose.yml` |

## 5. Interaction Guidelines

| Guideline | Description |
|-----------|-------------|
| Output Style | Provide short, detailed, and technical responses. Exclude verbose feedback loops and internal summaries. Only state relevant information. |
| Tone | Maintain a strictly professional and enterprise grade tone. **DO NOT USE EMOJIS.** Avoid informal sentence structures and dashes within sentences. |
| Reference Strategy | Link to relevant `docs/` files instead of duplicating explanations. |
| Design Philosophy | Strictly adhere to the KISS principle. Prefer modular and single responsibility functions. |
| Defensive Coding | Always validate inputs (Zod for frontend and Pydantic for backend) and handle errors gracefully. |