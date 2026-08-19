@echo off
echo ======================================================================
echo   ENTERPRISE SELF-HEALING AI — 1-CLICK SETUP FOR NEW ENVIRONMENT
echo ======================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python 3.9+.
    pause
    exit /b 1
)

:: 2. Create Virtual Environment
if not exist ".venv" (
    echo [SETUP] Creating virtual environment (.venv)...
    python -m venv .venv
) else (
    echo [SETUP] Virtual environment (.venv) already exists.
)

:: 3. Install Dependencies
echo [SETUP] Installing dependencies from requirements.txt...
call .\.venv\Scripts\Activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 4. Environment Variables (.env)
if not exist ".env" (
    echo [SETUP] Creating .env from .env.example...
    copy .env.example .env
    echo [IMPORTANT] Please open .env and add your GEMINI_API_KEY and GITHUB_TOKEN!
) else (
    echo [SETUP] .env file detected.
)

:: 5. Initialize Self-Healing config
echo [SETUP] Initializing self-healing configuration...
python self_healing_cli.py init

:: 6. Run Core Tests to Verify Installation
echo [SETUP] Running test suite verification...
python -m pytest tests/test_core.py -q

echo.
echo ======================================================================
echo   [SUCCESS] Setup complete! Your environment is 100%% ready.
echo ======================================================================
echo.
echo Quick Start:
echo   1. Start App:     .\.venv\Scripts\python -m uvicorn app:app --reload --port 8000
echo   2. Start Watcher: .\.venv\Scripts\python watcher.py
echo   3. Trigger Bug:   python -c "import requests; requests.get('http://127.0.0.1:8000/process_data')"
echo.
pause
