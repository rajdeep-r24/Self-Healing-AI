# Enterprise-Self-Healing

Self-Healing AI: Autonomous Incident Detection and Code Remediation

## MVP Overview
This MVP demonstrates a simple end-to-end self-healing loop:
1. `app.py` runs a FastAPI endpoint that intentionally raises an error.
2. The error and traceback are logged to `logs/server.log`.
3. `watcher.py` continuously monitors `server.log`.
4. Upon detecting an error, it extracts the traceback and source code, sending them to the `ai_engine.py`.
5. The AI uses Google Gemini to diagnose the issue and generate a fixed `app.py`.
6. `validator.py` validates the proposed fix using `py_compile`.
7. If validation passes, `watcher.py` creates a backup of the broken `app.py`, replaces it with the fixed version, and triggers Uvicorn to reload the service.

## Running the MVP

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the FastAPI server:
   ```bash
   uvicorn app:app --reload
   ```
3. Start the watcher in a new terminal:
   ```bash
   python watcher.py
   ```
4. Trigger the error by navigating to `http://127.0.0.1:8000/process_data`.
5. Watch the `watcher.py` terminal as it detects the error, diagnoses it, fixes the code, and reloads the server automatically!
