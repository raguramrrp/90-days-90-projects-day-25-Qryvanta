@echo off
setlocal

echo ====================================================================
echo   QRYVANTA — Automated Test Suite (Backend Pytest + Frontend Vitest)
echo ====================================================================

if not exist ".venv\Scripts\pytest.exe" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    exit /b 1
)

echo [1/3] Running Backend Pytest Suite...
".venv\Scripts\pytest.exe" tests -v
if errorlevel 1 (
    echo [FAIL] Backend tests failed.
    exit /b 1
)

echo.
echo [2/3] Running Frontend Vitest Suite...
pushd frontend
call npm test
set FE_TEST_EXIT=%errorlevel%
if not "%FE_TEST_EXIT%"=="0" (
    popd
    echo [FAIL] Frontend tests failed.
    exit /b 1
)

echo.
echo [3/3] Verifying Frontend TypeScript & Production Build...
call npm run build
set FE_BUILD_EXIT=%errorlevel%
popd
if not "%FE_BUILD_EXIT%"=="0" (
    echo [FAIL] Frontend build failed.
    exit /b 1
)

echo.
echo [PASS] All QRYVANTA backend tests, frontend tests, and production builds succeeded!
exit /b 0
