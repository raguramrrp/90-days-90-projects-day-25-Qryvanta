@echo off
setlocal enabledelayedexpansion

echo ====================================================================
echo   QRYVANTA — Intelligent Customer Support Operations Setup (Windows)
echo ====================================================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH. Install Python 3.11+ and retry.
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js / npm is not installed or not on PATH. Install Node.js 20+ and retry.
    exit /b 1
)

if not exist ".env" (
    echo [INFO] Creating .env from .env.example...
    copy ".env.example" ".env" >nul
) else (
    echo [INFO] Existing .env preserved.
)

if not exist ".venv" (
    echo [INFO] Creating Python virtual environment in .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create Python virtual environment.
        exit /b 1
    )
)

echo [INFO] Installing backend and ML Python dependencies...
".venv\Scripts\pip.exe" install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    exit /b 1
)

echo [INFO] Training initial TF-IDF + Logistic Regression classifier...
".venv\Scripts\python.exe" scripts\train_classifier.py
if errorlevel 1 (
    echo [ERROR] Classifier training failed.
    exit /b 1
)

echo [INFO] Applying Alembic database migrations...
".venv\Scripts\alembic.exe" -c backend\alembic.ini upgrade head
if errorlevel 1 (
    echo [ERROR] Database migration failed.
    exit /b 1
)

echo [INFO] Seeding local demo workspace (idempotent)...
".venv\Scripts\python.exe" scripts\seed_database.py
if errorlevel 1 (
    echo [ERROR] Database seeding failed.
    exit /b 1
)

echo [INFO] Seeding additive incident, SLA pressure, and resolution demo scenarios (idempotent)...
".venv\Scripts\python.exe" scripts\seed_upgrade_scenarios.py
if errorlevel 1 (
    echo [ERROR] Upgrade demo scenarios seeding failed.
    exit /b 1
)

echo [INFO] Installing frontend Node.js dependencies...
pushd frontend
call npm install
set NPM_EXIT=%errorlevel%
popd
if not "%NPM_EXIT%"=="0" (
    echo [ERROR] Frontend npm install failed.
    exit /b 1
)

echo.
echo [SUCCESS] QRYVANTA setup completed successfully!
echo Run `run.bat` to launch both the FastAPI backend and React frontend.
echo Run `test.bat` to execute backend Pytest and frontend Vitest suites.
exit /b 0
