import subprocess
import time
import requests
import os
from reset_demo import reset

def test_a_cli():
    print("--- Running Test A with CLI ---")
    reset()
    
    # Run init
    print("\n[TEST] Running 'self-healing init'")
    subprocess.run(["..\\self-healing.bat", "init"], shell=True)
    
    print("\n[TEST] Waiting 3 seconds for Uvicorn...")
    time.sleep(3)
    
    # Run start in background
    print("\n[TEST] Starting 'self-healing start' in background...")
    p = subprocess.Popen(["..\\self-healing.bat", "start"], shell=True)
    
    # Give watcher a second to boot up
    time.sleep(2)
    
    print("\n[TEST] Triggering intentional bug...")
    try:
        requests.get("http://127.0.0.1:8000/process_data")
    except Exception as e:
        print(f"Request failed (expected): {e}")
        
    print("\n[TEST] Waiting 15 seconds for AI healing process...")
    time.sleep(15)
    
    print("\n[TEST] Terminating watcher...")
    p.terminate()
    print("Test A CLI Complete")

if __name__ == "__main__":
    test_a_cli()
