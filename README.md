# AI Voucher Agent — Financial Document & Payment Voucher Management System

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose%20%2B%20Caddy-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Pytest-85%20Tests-0A9EDC?style=flat-square&logo=pytest&logoColor=white)](ketoan-backend/tests)

A **verification-first** internal accounting and financial voucher management platform designed for commodity procurement businesses. It combines deterministic **FastAPI + PostgreSQL** financial controls (RBAC, immutable approved vouchers, database-enforced append-only audit log) with a **propose-only LLM Agent (`Agent-BE`)**, multimodal OCR document extraction, and an automated anomaly watchdog.

---

## Architecture & Hard Safety Boundary

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                 React 19 + TypeScript Frontend (Vite 8)                  │
│   Dashboard · Vouchers · Sales Invoices · Scan Review · AI Command Bar   │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ JWT + RBAC
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              FastAPI Backend & Business Rule Boundary                    │
│  • 4-Role RBAC (giam_doc, ke_toan, thu_quy, nhan_vien)                   │
│  • Strict Voucher State Machine (draft -> approved [409 lock] / void)    │
│  • Monthly Sequence Numbering & Vietnamese Form 02-TT / 02-TNDN Export   │
│  • Watchdog Engine (price deviation, overdue receivables, missing IDs)   │
├────────────────────────────────────┬─────────────────────────────────────┤
│  Agent-BE Orchestrator (Safe Loop) │  Multimodal Vision Scan Pipeline    │
│  • Providers: Claude / NIM / Ollama│  • Providers: Claude / NVIDIA NIM   │
│  • Tools: READ + PROPOSE only      │  • qty × unit_price == total check  │
│  • ZERO direct DB writes/approvals │  • Fuzzy seller match (rapidfuzz)   │
│  • Max 6 tool iterations + history │  • Captures raw + human-fixed pairs │
│    & context injection scrubbing   │    in scan_imports for OCR tuning   │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  PostgreSQL 16 + Alembic Migrations                      │
│  10+ Relational Tables · DB Trigger Blocking UPDATE/DELETE on audit_log  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Core Safety Invariant (`Proposer != Committer`):**  
`Agent-BE` never writes directly to PostgreSQL and has no write/approve tools. When a user asks the assistant to draft a voucher (e.g., *"mua 500kg mủ anh X giá 15.000"*), `propose_voucher_draft` emits a structured proposal card for human review; actual persistence always goes through `POST /vouchers/` subject to Pydantic schema validation, JWT/RBAC enforcement, and immutable audit logging.

---

## Key Capabilities

### 1. Propose-Only Agent Orchestrator (`ketoan-backend/app/agent/`)
- **Direct SDK Loop (No Black-Box Framework)**: Implements transparent tool-calling loops directly over the Anthropic SDK (`claude`) and OpenAI-compatible endpoints (`nim`, `ollama`), keeping prompts, tool schemas, and traces inspectable.
- **Guardrails & Trust Boundaries**: Strips malformed client history, sanitizes UI route context against prompt injection, caps tool loops at `MAX_TOOL_ITERATIONS = 6`, and resolves Vietnamese seller names with diacritic-insensitive + honorific-stripped fuzzy matching (`rapidfuzz`).
- **Tool Registry**:
  - `read`: `search_seller`, `get_monthly_summary`, `get_receivables`, `get_price_history`
  - `propose`: `propose_voucher_draft` (never mutates DB; returns a UI confirmation card)

### 2. Multimodal OCR Scan & Human-in-the-Loop Flywheel (`app/services/scan_extraction_service.py`)
- Extracts structured line items from photographed purchase sheets via **Claude Vision** or **NVIDIA NIM (`llama-3.2-90b-vision-instruct`)**.
- Automatically verifies arithmetic (`quantity × unit_price` vs. extracted total within tolerance), matches vendor names against master records, and flags suspect rows for accountant review before creating draft vouchers.
- Stores original scans, raw model outputs, and human-corrected outputs in `scan_imports` as a labeled dataset for future domain-specific handwriting OCR fine-tuning.

### 3. Financial Integrity, Watchdog & Compliance Exports
- **Database-Enforced Append-Only Audit Log**: PostgreSQL trigger blocks `UPDATE` and `DELETE` on `audit_log` at the database layer.
- **Role-Gated State Machine**: Draft vouchers can be edited; approved vouchers are locked (`HTTP 409`); only `giam_doc` (Director) can approve or void with a mandatory reason.
- **Watchdog Anomaly Alerts (`app/services/watchdog_service.py`)**: Detects unit-price outliers relative to historical medians (excluding voided vouchers), overdue accounts receivable, and top sellers missing required tax ID / citizen ID fields.
- **Compliance Excel Exports (`app/services/export_service.py`)**: Generates seller-grouped payment vouchers (`Mẫu 02-TT`) preserving exact print layout and Vietnamese tax purchase summaries (`Bảng kê 02/TNDN`).

---

## Repository Layout

```text
.
├── ketoan-backend/        # FastAPI API, SQLAlchemy models, Alembic migrations, Agent-BE, 85 pytest tests
├── ketoan-frontend/       # React 19 + TypeScript 6 + Vite 8 web app + AI Command Bar
├── deploy/                # Production Docker Compose + Caddyfile reverse proxy + backup scripts
├── gom_nhom_phieu_chi.py  # Standalone Excel voucher-grouping utility (Phase 0 seed)
├── run-all.ps1            # One-command local dev launcher (PostgreSQL + Backend + Frontend)
└── KE_HOACH_*.md          # System architecture, compliance risk analysis & UX roadmap (Vietnamese)
```

For detailed module documentation in Vietnamese, see:
- [ketoan-backend/README.md](ketoan-backend/README.md)
- [ketoan-frontend/README.md](ketoan-frontend/README.md)
- [deploy/README.md](deploy/README.md)

---

## Quickstart

### Option A: Docker Compose (Backend + PostgreSQL)
```bash
cd ketoan-backend
cp .env.example .env
# Edit .env with your PostgreSQL password, JWT SECRET_KEY, and optional ANTHROPIC_API_KEY / NIM_API_KEY

docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_initial_data
```
API docs are available at `http://localhost:8000/docs`.

### Option B: Frontend Local Dev
```bash
cd ketoan-frontend
cp .env.example .env
npm install
npm run dev
```

### Running Tests & Lint
```bash
# Backend (85 tests covering auth, RBAC, voucher state machine, audit trigger, agent tools/orchestrator, OCR scans, exports, reports & watchdog)
cd ketoan-backend
createdb ketoan_test_db   # once
pytest -v

# Frontend lint & type-checked build
cd ketoan-frontend
npm run lint
npm run build
```
