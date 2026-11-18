# QRYVANTA — Troubleshooting Guide

## Common Issues & Fixes

### 1. Backend fails to start: `ModuleNotFoundError: No module named 'app'`
Ensure you pass `--app-dir backend` when launching Uvicorn from the repository root:
```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend shows network errors or cannot log in
- Confirm the FastAPI backend is running on `http://127.0.0.1:8000` (`http://127.0.0.1:8000/api/health` should return `{"status": "ok"}`).
- Verify `frontend/vite.config.ts` proxies `/api` to `http://127.0.0.1:8000` or set `VITE_API_URL=http://127.0.0.1:8000` in `.env`.

### 3. Model Centre reports "No trained ML model is currently active"
Run the initial training script from the project root:
```powershell
.\.venv\Scripts\python.exe scripts\train_classifier.py
```
This generates `data/synthetic/synthetic_support_tickets.csv`, trains `v1.0.0`, saves `ml/models/ticket_classifier_v1.0.0.joblib`, and activates it in `model_versions`.

### 4. Resetting the local SQLite database cleanly
Stop the backend server, delete `qryvanta.db`, then re-run:
```powershell
.\.venv\Scripts\python.exe scripts\train_classifier.py
.\.venv\Scripts\python.exe scripts\seed_database.py
```

### 5. Switching to PostgreSQL
Update `DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql+psycopg://postgres:yourpassword@localhost:5432/qryvanta
```
Create the `qryvanta` database in PostgreSQL, then run `scripts/train_classifier.py` and `scripts/seed_database.py`.
