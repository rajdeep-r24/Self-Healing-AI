import subprocess
import time
import requests
import os
from reset_demo import reset

def test_github_failure():
    print("--- Running Test: GitHub Failure Graceful Degradation ---")
    reset()
    
    # Run start in background with an invalid token
    env = os.environ.copy()
    env["GITHUB_TOKEN"] = "invalid_token_for_testing"
    
    print("\n[TEST] Starting watcher with INVALID GitHub token...")
    p = subprocess.Popen(["python", "watcher.py"], env=env)
    
    print("\n[TEST] Waiting 3 seconds for Uvicorn...")
    time.sleep(3)
    
    print("\n[TEST] Triggering intentional bug...")
    try:
        requests.get("http://127.0.0.1:8000/process_data")
    except Exception:
        pass
        
    print("\n[TEST] Waiting 20 seconds for AI healing process...")
    time.sleep(20)
    
    print("\n[TEST] Terminating watcher...")
    p.terminate()
    
    # Check if app.py was fixed
    with open("app.py", "r") as f:
        content = f.read()
        if "username" in content:
            print("[TEST] SUCCESS: Local healing worked despite GitHub failure!")
        else:
            print("[TEST] FAILED: Local healing did NOT work!")

if __name__ == "__main__":
    test_github_failure()
