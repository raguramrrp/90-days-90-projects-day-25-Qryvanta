@echo off
setlocal

echo ====================================================================
echo   QRYVANTA — Starting Backend API and React Frontend
echo ====================================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [ERROR] Frontend dependencies not installed. Please run setup.bat first.
    pause
    exit /b 1
)

echo [INFO] Starting FastAPI backend on http://127.0.0.1:8000 (API Docs: /docs)...
start "QRYVANTA Backend API" cmd /k ""%CD%\.venv\Scripts\uvicorn.exe" app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload"

echo [INFO] Starting React frontend on http://127.0.0.1:5173 ...
start "QRYVANTA React Frontend" cmd /k "cd /d "%CD%\frontend" && npm run dev"

echo.
echo Both services are launching in dedicated terminal windows:
echo   Frontend UI : http://127.0.0.1:5173
echo   Backend API : http://127.0.0.1:8000
echo   OpenAPI Docs: http://127.0.0.1:8000/docs
echo.
echo Local Demo Login (Password: DemoUser#2026):
echo   Admin: admin@qryvanta.local | Manager: manager@qryvanta.local | Customer: customer@qryvanta.local
exit /b 0
