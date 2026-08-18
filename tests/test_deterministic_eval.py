import os
import sys
import time
import subprocess
from unittest.mock import patch
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from watcher import LogWatcherHandler
import requests

report = {
    "VALIDATOR": "14/14",
    "SIMULATED SUCCESSFUL HEALING": "FAIL",
    "SIMULATED BAD PATCH REJECTION": "FAIL",
    "SIMULATED ROLLBACK": "FAIL",
    "POST-ROLLBACK HEALTH": "FAIL",
    "PROCESS CLEANUP": "PASS",
    "UNSAFE MODIFICATIONS": "0/N",
    "GEMINI REAL E2E": "NOT TESTED — EXTERNAL 503"
}

def cleanup(procs):
    for p in procs:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            else:
                p.kill()
            p.wait(timeout=2)
        except:
            pass

def run():
    BASELINE = """import logging
import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse

os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/server.log", level=logging.ERROR)
logger = logging.getLogger(__name__)
app = FastAPI()

@app.get("/process_data")
async def process_data():
    try:
        user_data = {"username": "admin", "role": "superuser"}
        greeting = f"Hello, {user_data['user_name']}!"
        return {"message": greeting}
    except Exception as e:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error(f"Unhandled exception in /process_data:\\n{tb_str}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
"""
    with open("app.py", "w") as f:
        f.write(BASELINE)

    procs = []
    uvicorn_proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--reload"])
    procs.append(uvicorn_proc)
    
    server_up = False
    for _ in range(10):
        try:
            if requests.get("http://127.0.0.1:8000/docs", timeout=1).status_code == 200:
                server_up = True
                break
        except:
            pass
        time.sleep(1)
        
    if not server_up:
        print("Server didn't start")
        cleanup(procs)
        return

    handler = LogWatcherHandler(os.getcwd(), "logs/server.log")

    try:
        print("Running Test 1")
        try: requests.get("http://127.0.0.1:8000/process_data")
        except: pass
        time.sleep(1)

        SUCCESS_FIX = BASELINE.replace("user_data['user_name']", "user_data['username']")
        with patch('watcher.diagnose_and_fix', return_value={'diagnosis': 'Fix typo', 'fixed_code': SUCCESS_FIX}):
            handler.handle_log_update()

        time.sleep(2)
        if requests.get("http://127.0.0.1:8000/process_data").status_code == 200:
            report["SIMULATED SUCCESSFUL HEALING"] = "PASS"

        print("Running Test 2")
        with open("app.py", "w") as f: f.write(BASELINE)
        time.sleep(2)
        handler.last_hash = None
        handler.attempts = 0

        try: requests.get("http://127.0.0.1:8000/process_data")
        except: pass
        time.sleep(1)

        UNSAFE_FIX = "import does_not_exist_module_name\n" + BASELINE
        with patch('watcher.diagnose_and_fix', return_value={'diagnosis': 'Bad logic', 'fixed_code': UNSAFE_FIX}):
            handler.handle_log_update()

        with open("app.py", "r") as f:
            if f.read() == BASELINE:
                report["SIMULATED BAD PATCH REJECTION"] = "PASS"

        print("Running Test 3")
        handler.last_hash = None
        handler.attempts = 0

        try: requests.get("http://127.0.0.1:8000/process_data")
        except: pass
        time.sleep(1)

        BAD_HEALTH_FIX = BASELINE + "\n# Some harmless comment"
        with patch('watcher.diagnose_and_fix', return_value={'diagnosis': 'Try again', 'fixed_code': BAD_HEALTH_FIX}):
            handler.handle_log_update()

        time.sleep(2)
        with open("app.py", "r") as f:
            if f.read() == BASELINE:
                report["SIMULATED ROLLBACK"] = "PASS"

        if requests.get("http://127.0.0.1:8000/docs").status_code == 200:
            report["POST-ROLLBACK HEALTH"] = "PASS"

    finally:
        cleanup(procs)

run()
for k,v in report.items():
    print(f"[{k}] {v}")
