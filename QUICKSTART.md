# QRYVANTA — Quick Start Guide (Windows)

## Option 1: One-Click Windows Scripts

1. **Setup (installs Python + Node dependencies, trains ML model, seeds demo data):**
   ```bat
   setup.bat
   ```
2. **Run (starts FastAPI backend on port 8000 and React frontend on port 5173):**
   ```bat
   run.bat
   ```
3. **Test (runs Pytest, Vitest, and TypeScript production build):**
   ```bat
   test.bat
   ```

## Option 2: Manual Step-by-Step Windows Commands

### Terminal 1 — Backend Setup & Server
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Copy-Item .env.example .env
python scripts\train_classifier.py
python scripts\seed_database.py
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### Terminal 2 — Frontend Setup & Dev Server
```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in your browser. API documentation is at `http://127.0.0.1:8000/docs`.

## Local Demo Credentials
> **Security Notice**: Temporary local development password only (`DemoUser#2026`). Change before any deployment.

| Role | Email |
|---|---|
| Administrator | `admin@qryvanta.local` |
| Support Manager | `manager@qryvanta.local` |
| Billing Agent | `billing.agent@qryvanta.local` |
| Technical Support Agent | `tech.agent@qryvanta.local` |
| Logistics Agent | `logistics.agent@qryvanta.local` |
| Account Services Agent | `account.agent@qryvanta.local` |
| Customer | `customer@qryvanta.local` |
