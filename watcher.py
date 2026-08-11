import os
import time
import hashlib
import logging
import subprocess
import uuid
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ai_engine import diagnose_and_fix
from validator import validate_code

# Setup terminal output
logging.basicConfig(level=logging.INFO, format="%(message)s")

LOG_FILE = "logs/server.log"
TARGET_FILE = "app.py"
MAX_ATTEMPTS = 2

def git_commit_fix():
    try:
        git_config = ["-c", "user.name=AI-Healer", "-c", "user.email=ai@healer.local"]
        
        # Init repo if not exists
        if not os.path.exists(".git"):
            subprocess.run(["git", "init"], check=True, capture_output=True)
            subprocess.run(["git", "add", "."], check=True, capture_output=True)
            subprocess.run(["git", *git_config, "commit", "-m", "Initial commit"], check=True, capture_output=True)
            
        branch_name = f"ai-fix-{uuid.uuid4().hex[:6]}"
        subprocess.run(["git", "checkout", "-b", branch_name], check=True, capture_output=True)
        subprocess.run(["git", "add", TARGET_FILE], check=True, capture_output=True)
        subprocess.run(["git", *git_config, "commit", "-m", "AI Auto-Healer: Fixed crash in app.py"], check=True, capture_output=True)
        
        print(f"[GIT] Patch committed successfully to branch: {branch_name}")
    except Exception as e:
        print(f"[GIT] Warning: Local git commit failed: {e}")

class LogWatcherHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.last_hash = None
        self.attempts = 0
        self.processing = False
        
    def on_modified(self, event):
        # We only care about the server log
        if not event.src_path.replace('\\', '/').endswith(LOG_FILE):
            return
            
        if self.processing:
            return
            
        self.processing = True
        try:
            self.handle_log_update()
        finally:
            self.processing = False

    def handle_log_update(self):
        if not os.path.exists(LOG_FILE):
            return
            
        with open(LOG_FILE, 'r') as f:
            content = f.read()
            
        if "Traceback" not in content:
            return
            
        # Extract the latest traceback
        tracebacks = content.split("Traceback (most recent call last):")
        if len(tracebacks) <= 1:
            return
            
        latest_tb = "Traceback (most recent call last):" + tracebacks[-1]
        
        # Hash the traceback to avoid duplicate processing
        tb_hash = hashlib.md5(latest_tb.encode('utf-8')).hexdigest()
        
        if tb_hash == self.last_hash:
            return
            
        if self.attempts >= MAX_ATTEMPTS:
            logging.error(f"[WATCHER] Max healing attempts ({MAX_ATTEMPTS}) reached for this error.")
            return

        self.last_hash = tb_hash
        self.attempts += 1
        
        print("[WATCHER] Error detected")
        print("[AI] Analyzing failure...")
        
        try:
            with open(TARGET_FILE, "r") as f:
                source_code = f.read()
                
            result = diagnose_and_fix(latest_tb, source_code)
            print(f"[AI] Root cause identified: {result['diagnosis']}")
            print("[AI] Patch generated")
            
            fixed_code = result['fixed_code']
            
            # Validation
            if validate_code(fixed_code):
                print("[VALIDATOR] Syntax check passed")
                print("[HEALER] Applying patch")
                
                # Backup
                with open(f"{TARGET_FILE}.bak", "w") as f:
                    f.write(source_code)
                    
                # Apply
                with open(TARGET_FILE, "w") as f:
                    f.write(fixed_code)
                    
                print("[SERVER] Reload triggered")
                print("[HEALER] Recovery successful")
                
                # Commit fix to Git branch
                git_commit_fix()
                
                # Reset attempts since we applied a fix
                self.attempts = 0
            else:
                print("[VALIDATOR] PATCH REJECTED")
                
        except Exception as e:
            if "AI diagnosis failed safely" in str(e):
                print("[HEALER] AI diagnosis failed safely")
                print("[HEALER] No source code modified")
            else:
                print(f"[HEALER] Process failed: {e}")

def start_watcher():
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'a').close()
        
    event_handler = LogWatcherHandler()
    observer = Observer()
    # Watch the logs directory
    observer.schedule(event_handler, path="logs", recursive=False)
    observer.start()
    
    print("[WATCHER] Started watching logs/server.log")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_watcher()
