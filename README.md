# AI Voucher Agent — Financial Document & Payment Voucher System

[![CI](https://github.com/Yato742003/ai-voucher-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Yato742003/ai-voucher-agent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose%20%2B%20Caddy-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Pytest-85%20Tests-0A9EDC?style=flat-square&logo=pytest&logoColor=white)](ketoan-backend/tests)

Internal accounting and payment voucher management system built with **FastAPI**, **PostgreSQL 16**, and **React + TypeScript**. It combines role-based financial controls (RBAC, locked approved vouchers, database-level append-only audit log) with a **propose-only** LLM assistant (`Agent-BE`), vision-based purchase sheet extraction, and automated anomaly alerts.

---

## System Architecture

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                   React + TypeScript Frontend (Vite)                     │
│   Dashboard · Vouchers · Sales Invoices · Scan Review · AI Command Bar   │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ JWT + RBAC
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend & Service Layer                     │
│  • 4-Role RBAC (giam_doc, ke_toan, thu_quy, nhan_vien)                   │
│  • Voucher State Machine (draft -> approved [409 lock] / void)           │
│  • Monthly Sequence Numbering & Vietnamese Form 02-TT / 02-TNDN Export   │
│  • Watchdog Alerts (price deviation, overdue receivables, missing IDs)   │
├────────────────────────────────────┬─────────────────────────────────────┤
│  Agent-BE Orchestrator             │  Vision Scan Extraction             │
│  • Providers: Claude / NIM / Ollama│  • Providers: Claude / NVIDIA NIM   │
│  • Tools: READ + PROPOSE only      │  • qty × unit_price == total check  │
│  • No direct DB writes/approvals   │  • Fuzzy seller match (rapidfuzz)   │
│  • Max 6 tool iterations           │  • Stores raw + corrected rows      │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  PostgreSQL 16 + Alembic Migrations                      │
│  10+ Relational Tables · DB Trigger Blocking UPDATE/DELETE on audit_log  │
└──────────────────────────────────────────────────────────────────────────┘
```

`Agent-BE` has no write or approval tools. When asked to draft a voucher (e.g., *"mua 500kg mủ anh X giá 15.000"*), `propose_voucher_draft` returns a draft proposal card in the UI; saving still goes through `POST /vouchers/` with standard Pydantic validation, RBAC checks, and audit logging.

---

## Key Features

### 1. Propose-Only Agent Assistant (`ketoan-backend/app/agent/`)
- **Direct SDK Integration:** Uses the Anthropic SDK (`claude`) and OpenAI-compatible endpoints (`nim`, `ollama`) without heavy agent frameworks, keeping prompts and tool calls easy to debug.
- **Input & Loop Controls:** Sanitizes client chat history and route context, limits tool execution to `MAX_TOOL_ITERATIONS = 6`, and matches Vietnamese seller names using diacritic-insensitive + honorific-stripped fuzzy search (`rapidfuzz`).
- **Tools:**
  - `read`: `search_seller`, `get_monthly_summary`, `get_receivables`, `get_price_history`
  - `propose`: `propose_voucher_draft` (returns a pre-filled confirmation card in the UI)

### 2. Vision OCR Scan & Arithmetic Reconciliation (`app/services/scan_extraction_service.py`)
- Extracts line items from photographed purchase sheets via **Claude Vision** or **NVIDIA NIM (`llama-3.2-90b-vision-instruct`)**.
- Checks `quantity × unit_price` against the extracted total, matches seller names against existing records, and highlights mismatched rows for review before creating draft vouchers.
- Saves the uploaded image, raw extraction, and user-corrected rows in `scan_imports`.

### 3. Accounting Controls, Watchdog & Excel Exports
- **Append-Only Audit Log:** A PostgreSQL trigger blocks `UPDATE` and `DELETE` statements on `audit_log`.
- **Voucher Lifecycle & RBAC:** Vouchers are editable only in `draft`; once `approved`, edits return `HTTP 409`. Only `giam_doc` (Director) can approve or void vouchers.
- **Watchdog Alerts (`app/services/watchdog_service.py`):** Flags unit-price outliers against historical medians (ignoring voided vouchers), overdue receivables, and frequent sellers missing citizen ID / tax ID details.
- **Excel Exports (`app/services/export_service.py`):** Exports seller-grouped payment vouchers (`Mẫu 02-TT`) preserving print layout and tax purchase summaries (`Bảng kê 02/TNDN`).

---

## Repository Structure

```text
.
├── ketoan-backend/        # FastAPI API, SQLAlchemy models, Alembic migrations, Agent-BE, 85 pytest tests
├── ketoan-frontend/       # React + TypeScript + Vite web app + AI Command Bar
├── deploy/                # Docker Compose + Caddyfile reverse proxy + DB backup scripts
├── docs/                  # Architecture notes, compliance considerations & UX roadmap (Vietnamese)
├── gom_nhom_phieu_chi.py  # Standalone Excel voucher-grouping script
└── run-all.ps1            # Local dev launcher (PostgreSQL + Backend + Frontend)
```

Component documentation (Vietnamese):
- [ketoan-backend/README.md](ketoan-backend/README.md)
- [ketoan-frontend/README.md](ketoan-frontend/README.md)
- [deploy/README.md](deploy/README.md)

---

## Quickstart

### 1. Backend + PostgreSQL (Docker Compose)
```bash
cd ketoan-backend
cp .env.example .env
# Update POSTGRES_PASSWORD, SECRET_KEY, INITIAL_ADMIN_PASSWORD, and optional ANTHROPIC_API_KEY / NIM_API_KEY

docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_initial_data
```
Swagger UI: `http://localhost:8000/docs`.

### 2. Frontend (Local Dev)
```bash
cd ketoan-frontend
cp .env.example .env
npm install
npm run dev
```

### 3. Tests & Linting
```bash
# Backend (85 pytest tests)
cd ketoan-backend
createdb ketoan_test_db   # first time only
pytest -v

# Frontend lint & build
cd ketoan-frontend
npm run lint
npm run build
```
