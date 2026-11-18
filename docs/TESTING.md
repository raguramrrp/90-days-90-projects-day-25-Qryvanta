# QRYVANTA — Testing & Quality Assurance

## Automated Test Suites

### 1. Backend Pytest Suite (`tests/`)
Covers authentication, RBAC, customer isolation, full ticket lifecycle, internal-note privacy, ML training/evaluation/prediction, priority/sentiment separation, confidence routing, TF-IDF duplicate detection & privacy, business-hours/holiday SLA math, analytics calculations, and CSV bulk import.

```powershell
.\.venv\Scripts\pytest.exe tests -v
```

### 2. Frontend Vitest & React Testing Library Suite (`frontend/src/__tests__/`)
Covers login & registration UI, Zod form validation on Submit Ticket, API-backed Ticket Queue rendering and empty states, and semantic status/priority/SLA indicators.

```powershell
cd frontend
npm test
npm run build
```

### 3. Combined Windows Runner
```bat
test.bat
```

## Verified Test Results

| Suite | Command | Result | Details |
|---|---|---|---|
| Backend Pytest | `.\.venv\Scripts\pytest.exe tests -v` | **PASS** | 13/13 tests passed |
| Frontend Vitest | `npm --prefix frontend test` | **PASS** | 4/4 tests passed |
| Frontend Typecheck & Build | `npm --prefix frontend run build` | **PASS** | `tsc --noEmit` + `vite build` succeeded cleanly |
| Live Server E2E Smoke Test | `uvicorn` + HTTP probe across `/health`, `/auth/login`, `/analytics/overview`, `/tickets`, `/models`, `/departments`, `/agents` | **PASS** | All endpoints returned HTTP 200 |
| Seed Idempotency Check | Re-running `python scripts/seed_database.py` | **PASS** | Detected existing 46 demo tickets and skipped duplicate creation |

## Known Testing Gaps
- PostgreSQL integration tests were not executed live against a running Postgres daemon during local SQLite testing; PostgreSQL driver (`psycopg[binary]`) and `docker-compose.yml` are configured and verified for syntax.
- Full browser end-to-end Playwright assertions (interactive click flows) are not bundled; visual rendering was verified via live headless Chrome CDP captures.
