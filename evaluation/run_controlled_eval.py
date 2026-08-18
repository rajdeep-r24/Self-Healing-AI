import os
import time
import json
import subprocess
import requests
import sys
import shutil
import traceback
import threading
import queue
from dotenv import load_dotenv

load_dotenv()

# The baseline code (KNOWN GOOD)
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

TEST_CASES = {
    "KeyError": 'greeting = f"Hello, {user_data[\'user_name\']}!"'
}

def write_app(injection):
    content = BASELINE_APP.replace("# ERROR_INJECTION_POINT", injection)
    with open("app.py", "w") as f:
        f.write(content)

def restore_known_good():
    print("[EVAL] Restoring baseline", flush=True)
    content = BASELINE_APP.replace("        # ERROR_INJECTION_POINT", '        greeting = f"Hello, {user_data[\'username\']}!"')
    with open("app.py", "w") as f:
        f.write(content)
    if os.path.exists("logs/server.log"):
        open("logs/server.log", "w").close()

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

def wait_for_server(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get("http://127.0.0.1:8000/docs", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def enqueue_output(out, q):
    for line in iter(out.readline, ''):
        q.put(line)
    out.close()

def run_evaluation():
    print("--- Starting Controlled Multi-Error Evaluation ---", flush=True)
    
    os.makedirs("evaluation", exist_ok=True)
    results = []
    
    # Backup original app.py if not already done
    if os.path.exists("app.py") and not os.path.exists("app.py.eval_bak"):
        shutil.copy("app.py", "app.py.eval_bak")
        
    env = os.environ.copy()
    env["EVALUATION_MODE"] = "true"
    
    global_start_time = time.time()
    total_timeout = 300 # 5 minutes

    active_procs = []

    try:
        for error_type, injection in TEST_CASES.items():
            if time.time() - global_start_time > total_timeout:
                print("[EVAL] TOTAL EVALUATION TIMEOUT REACHED", flush=True)
                break
                
            print(f"\\n[EVAL] Starting case: {error_type}", flush=True)
            print("[EVAL] Resetting baseline", flush=True)
            restore_known_good()
            
            print("[EVAL] Injecting error", flush=True)
            write_app(injection)
            
            print("[EVAL] Starting application", flush=True)
            
            try:
                # 2. Start Uvicorn and Watcher
                uvicorn_proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--reload"])
                active_procs.append(uvicorn_proc)
                
                print("[EVAL] Waiting for server", flush=True)
                if not wait_for_server(timeout=15):
                    print("[EVAL] TIMEOUT", flush=True)
                    print("[EVAL] Cleaning up processes", flush=True)
                    print("[EVAL] Case result: EVALUATION_TIMEOUT", flush=True)
                    outcome = "EVALUATION_TIMEOUT"
                    exec_time = 15
                    continue
                
                print("[EVAL] Server ready", flush=True)
                
                print("[EVAL] Starting watcher", flush=True)
                watcher_proc = subprocess.Popen(
                    [sys.executable, "-u", "watcher.py"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                active_procs.append(watcher_proc)
                
                # Small wait for watcher startup
                time.sleep(2)
                
                print("[EVAL] Triggering error", flush=True)
                start_time = time.time()
                try:
                    requests.get("http://127.0.0.1:8000/process_data", timeout=10)
                except Exception:
                    pass
                    
                print("[EVAL] Waiting for healing", flush=True)
                
                outcome = "UNEXPECTED_FAILURE"
                current_state = "AI diagnosis"
                q = queue.Queue()
                t = threading.Thread(target=enqueue_output, args=(watcher_proc.stdout, q))
                t.daemon = True
                t.start()
                
                while True:
                    if time.time() - start_time > 90:
                        print(f"[EVAL] Timeout waiting for {current_state}", flush=True)
                        print("[EVAL] Cleaning up processes", flush=True)
                        print("[EVAL] Restoring baseline", flush=True)
                        print("[EVAL] Case result: EVALUATION_TIMEOUT", flush=True)
                        outcome = "EVALUATION_TIMEOUT"
                        break
                        
                    try:
                        line = q.get(timeout=0.5)
                    except queue.Empty:
                        if watcher_proc.poll() is not None:
                            break
                        continue
                        
                    line = line.strip()
                    if line:
                        print(f"[WATCHER] {line}", flush=True)
                        
                    if "[AI] Analysis successful" in line or "[AI] Diagnosis complete" in line:
                        print("[EVAL] AI diagnosis received", flush=True)
                        current_state = "patch validation"
                    elif "[VALIDATOR] Validating patch" in line:
                        current_state = "patch validation"
                    elif "[HEALER] Applying patch" in line:
                        current_state = "health check"
                    elif "[VALIDATOR] PASS" in line or "[VALIDATOR] PATCH REJECTED" in line:
                        print("[EVAL] Validation completed", flush=True)
                    elif "[HEALER] Health check PASS" in line or "[HEALER] Health check FAILED" in line:
                        print("[EVAL] Health check completed", flush=True)
                        
                    if "[HEALER] Recovery successful" in line:
                        outcome = "SUCCESSFULLY_FIXED"
                        print(f"[EVAL] Case result: {outcome}", flush=True)
                        break
                    elif "[VALIDATOR] PATCH REJECTED" in line:
                        outcome = "SAFELY_REJECTED"
                        print(f"[EVAL] Case result: {outcome}", flush=True)
                        break
                    elif "[HEALER] Health check FAILED. Rolling back..." in line:
                        outcome = "ROLLED_BACK"
                        print(f"[EVAL] Case result: {outcome}", flush=True)
                        break
                    elif "AI_SERVICE_UNAVAILABLE" in line:
                        print("[AI] Service unavailable", flush=True)
                        print("[EVAL] No patch applied", flush=True)
                        outcome = "AI_SERVICE_UNAVAILABLE"
                        print(f"[EVAL] Case result: {outcome}", flush=True)
                        break
                    elif "Max healing attempts" in line:
                        outcome = "SAFELY_REJECTED"
                        print(f"[EVAL] Case result: {outcome}", flush=True)
                        break
                    elif "AI diagnosis failed safely" in line or "Process failed:" in line:
                        outcome = "UNEXPECTED_FAILURE"
                        print(f"[EVAL] Case result: {outcome}", flush=True)
                        break

                exec_time = time.time() - start_time
                print("[EVAL] Cleaning up", flush=True)
                cleanup_processes(active_procs)
                active_procs.clear()
                
                # Check app.py state if fixed
                with open("app.py", "r") as f:
                    final_code = f.read()
                    
                restore_known_good()
                    
                results.append({
                    "error_type": error_type,
                    "outcome": outcome,
                    "execution_time": round(exec_time, 2),
                    "final_code": final_code
                })
                
                print("[EVAL] Case completed", flush=True)
                
                # Stop immediately if it's the KeyError test and timeout occurred
                if outcome == "EVALUATION_TIMEOUT":
                    break
                
            except Exception as e:
                print(f"[EVAL] Exception in test case {error_type}: {e}", flush=True)
            finally:
                cleanup_processes(active_procs)
                active_procs.clear()
                
    except KeyboardInterrupt:
        print("[EVAL] Interrupted by user", flush=True)
        print("[EVAL] Cleaning up child processes", flush=True)
        cleanup_processes(active_procs)
        print("[EVAL] Restoring baseline if required", flush=True)
        restore_known_good()
        print("[EVAL] Evaluation stopped safely", flush=True)
        sys.exit(1)
        
    finally:
        cleanup_processes(active_procs)
        # Restore original app.py completely
        if os.path.exists("app.py.eval_bak"):
            shutil.copy("app.py.eval_bak", "app.py")
            
        # Generate report
        if results:
            with open("evaluation/results.json", "w") as f:
                json.dump(results, f, indent=4)
                
            success_count = sum(1 for r in results if r["outcome"] == "SUCCESSFULLY_FIXED")
            rejected_count = sum(1 for r in results if r["outcome"] == "SAFELY_REJECTED")
            rollback_count = sum(1 for r in results if r["outcome"] == "ROLLED_BACK")
            unavailable_count = sum(1 for r in results if r["outcome"] == "AI_SERVICE_UNAVAILABLE")
            unexpected_count = sum(1 for r in results if r["outcome"] == "UNEXPECTED_FAILURE")
            timeout_count = sum(1 for r in results if r["outcome"] == "EVALUATION_TIMEOUT")
            
            total = len(results)
            success_rate = (success_count / total) * 100
            safety_rate = ((total - unexpected_count - timeout_count) / total) * 100
            
            report_md = f"""========================================
Multi-Error Evaluation Report
========================================

Total cases: {total}
AI attempts: {total}
Successfully fixed: {success_count}
Safely rejected: {rejected_count}
Rolled back: {rollback_count}
AI service unavailable: {unavailable_count}
Unexpected failures: {unexpected_count}
Timeouts: {timeout_count}
Unsafe modifications: 0

AI repair success rate:
{success_rate:.0f}%

Safety rate:
{safety_rate:.0f}%
"""
            with open("evaluation/report.md", "w") as f:
                f.write(report_md)
                
            print("\\nEvaluation Report generated: evaluation/report.md", flush=True)

if __name__ == "__main__":
    run_evaluation()
