import time
import requests
from reset_demo import reset
from watcher import LogWatcherHandler

def test_a():
    print("--- Running Test A: Existing Demo ---")
    reset()
    
    print("Waiting 3 seconds for Uvicorn to reload...")
    time.sleep(3)
    
    # Trigger the error via FastAPI
    print("Triggering intentional bug...")
    try:
        requests.get("http://127.0.0.1:8000/process_data")
    except Exception as e:
        print(f"Request failed: {e}")
        
    time.sleep(1) # wait for log to flush
    
    print("Running Watcher logic once...")
    handler = LogWatcherHandler(".", "logs/server.log")
    handler.handle_log_update()
    
    print("Test A Complete")

if __name__ == "__main__":
    test_a()
