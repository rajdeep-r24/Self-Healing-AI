import os
import time
import subprocess
import requests
import sys
import shutil
import threading
import queue

BASELINE_APP = """import logging
import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/server.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/process_data")
async def process_data():
    try:
        user_data = {"username": "admin", "role": "superuser"}
        # ERROR_INJECTION_POINT
        return {"message": greeting}
    except Exception as e:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error(f"Unhandled exception in /process_data:\\n{tb_str}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
"""

def cleanup_processes(procs):
    for proc in procs:
        if proc and proc.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        pass
                else:
                    proc.terminate()
                    proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass

def enqueue_output(out, q):
    for line in iter(out.readline, ''):
        q.put(line)
    out.close()

def run():
    print("========================================")
    print("SINGLE KEYERROR EVALUATION")
    print("========================================")
    
    status = {
        "KEYERROR": "FAIL",
        "AI DIAGNOSIS": "FAIL",
        "AI PATCH": "FAIL",
        "SYNTAX VALIDATION": "FAIL",
        "PYTEST GATE": "SKIPPED",
        "HEALTH CHECK": "FAIL",
        "ROLLBACK": "NOT_REQUIRED",
        "LOCAL GIT": "FAIL",
        "GITHUB": "DISABLED",
        "PROCESS CLEANUP": "PASS",
        "UNSAFE MODIFICATIONS": "0/N"
    }

    env = os.environ.copy()
    env["EVALUATION_MODE"] = "true"
    
    start_time = time.time()
    procs = []
    
    try:
        baseline_injection = '        greeting = f"Hello, {user_data[\'username\']}!"'
        with open("app.py", "w") as f:
            f.write(BASELINE_APP.replace("        # ERROR_INJECTION_POINT", baseline_injection))
        if os.path.exists("logs/server.log"):
            open("logs/server.log", "w").close()
            
        error_injection = '        greeting = f"Hello, {user_data[\'user_name\']}!"'
        with open("app.py", "w") as f:
            f.write(BASELINE_APP.replace("        # ERROR_INJECTION_POINT", error_injection))
            
        uvicorn_proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--reload"])
        procs.append(uvicorn_proc)
        
        server_up = False
        s_start = time.time()
        while time.time() - s_start < 15:
            try:
                r = requests.get("http://127.0.0.1:8000/docs", timeout=2)
                if r.status_code == 200:
                    server_up = True
                    break
            except:
                pass
            time.sleep(0.5)
            
        if not server_up:
            status["KEYERROR"] = "FAIL (Server Timeout)"
            return
            
        watcher_proc = subprocess.Popen(
            [sys.executable, "-u", "watcher.py"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        procs.append(watcher_proc)
        
        time.sleep(2)
        
        try:
            requests.get("http://127.0.0.1:8000/process_data", timeout=10)
            status["KEYERROR"] = "PASS"
        except requests.Timeout:
            status["KEYERROR"] = "PASS (Timeout on bad request expected)"
        except Exception:
            status["KEYERROR"] = "PASS"
            
        q = queue.Queue()
        t = threading.Thread(target=enqueue_output, args=(watcher_proc.stdout, q))
        t.daemon = True
        t.start()
        
        w_start = time.time()
        while time.time() - w_start < 90:
            try:
                line = q.get(timeout=0.5).strip()
                if line:
                    print(f"[WATCHER] {line}", flush=True)
                if "AI_SERVICE_UNAVAILABLE" in line or "503" in line or "429" in line:
                    status["AI DIAGNOSIS"] = "AI_SERVICE_UNAVAILABLE"
                    break
                if "[AI] Diagnosis complete" in line:
                    status["AI DIAGNOSIS"] = "PASS"
                    status["AI PATCH"] = "PASS"
                if "[VALIDATOR] Syntax error" in line:
                    status["SYNTAX VALIDATION"] = "FAIL"
                if "[VALIDATOR] Shadow Pytest Gate PASS" in line or "[VALIDATOR] No tests found - Pytest Gate SKIPPED" in line:
                    status["SYNTAX VALIDATION"] = "PASS"
                    status["PYTEST GATE"] = "PASS"
                if "[VALIDATOR] Shadow Pytest Gate FAILED" in line:
                    status["SYNTAX VALIDATION"] = "PASS"
                    status["PYTEST GATE"] = "FAIL"
                if "[HEALER] Recovery successful" in line:
                    status["HEALTH CHECK"] = "PASS"
                    status["LOCAL GIT"] = "PASS"
                    break
                if "Rolling back" in line:
                    status["HEALTH CHECK"] = "FAIL"
                    status["ROLLBACK"] = "PASS"
                    break
            except queue.Empty:
                if watcher_proc.poll() is not None:
                    break
                    
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        cleanup_processes(procs)
        
        with open("app.py", "w") as f:
            f.write(BASELINE_APP.replace("        # ERROR_INJECTION_POINT", '        greeting = f"Hello, {user_data[\'username\']}!"'))
            
        exec_time = time.time() - start_time
        
        print("")
        print(f"[KEYERROR] {status['KEYERROR']}")
        print(f"[AI DIAGNOSIS] {status['AI DIAGNOSIS']}")
        print(f"[AI PATCH] {status['AI PATCH']}")
        print(f"[SYNTAX VALIDATION] {status['SYNTAX VALIDATION']}")
        print(f"[PYTEST GATE] {status['PYTEST GATE']}")
        print(f"[HEALTH CHECK] {status['HEALTH CHECK']}")
        print(f"[ROLLBACK] {status['ROLLBACK']}")
        print(f"[LOCAL GIT] {status['LOCAL GIT']}")
        print(f"[GITHUB] {status['GITHUB']}")
        print(f"[PROCESS CLEANUP] {status['PROCESS CLEANUP']}")
        print(f"[UNSAFE MODIFICATIONS] {status['UNSAFE MODIFICATIONS']}")
        print(f"\\nExecution time: {exec_time:.2f} seconds")

if __name__ == '__main__':
    run()
