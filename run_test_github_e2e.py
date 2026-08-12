import subprocess
import time
import requests
import os
from reset_demo import reset
from dotenv import load_dotenv

def test_github_e2e():
    print("--- Running Test: GitHub End-to-End PR ---")
    reset()
    
    # Load token from .env
    load_dotenv()
    
    print("\n[TEST] Starting watcher...")
    p = subprocess.Popen(["python", "watcher.py"])
    
    print("\n[TEST] Waiting 3 seconds for Uvicorn...")
    time.sleep(3)
    
    print("\n[TEST] Triggering intentional bug...")
    try:
        requests.get("http://127.0.0.1:8000/process_data")
    except Exception:
        pass
        
    print("\n[TEST] Waiting 25 seconds for AI healing & GitHub PR process...")
    time.sleep(25)
    
    print("\n[TEST] Terminating watcher...")
    p.terminate()
    
    # Check if app.py was fixed
    with open("app.py", "r") as f:
        content = f.read()
        if "username" in content:
            print("[TEST] SUCCESS: Local healing worked!")
        else:
            print("[TEST] FAILED: Local healing did NOT work!")
            
    print("\n[TEST] End-to-End test finished. Please verify GitHub PR online.")

if __name__ == "__main__":
    test_github_e2e()
