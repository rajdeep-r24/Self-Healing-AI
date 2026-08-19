import os
import time
import hashlib
import logging
import subprocess
import uuid
import argparse
import json
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ai_engine import diagnose_and_fix
from validator import validate_code
from git_module import local_commit_fix, github_push_and_pr

logging.basicConfig(level=logging.INFO, format="%(message)s")

MAX_ATTEMPTS = 2

def get_config(project_root):
    config_path = os.path.join(project_root, ".self-healing", "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[CONFIG] Error reading config: {e}")
    return {}

def extract_target_file(traceback_text, project_root):
    # Find all file paths in the traceback
    matches = re.findall(r'File "([^"]+)"', traceback_text)
    for match in reversed(matches):
        # Normalize paths
        abs_match = os.path.abspath(match)
        abs_root = os.path.abspath(project_root)
        
        # Check if the file is inside the project root
        try:
            if os.path.commonpath([abs_match, abs_root]) == abs_root:
                if os.path.exists(abs_match):
                    return abs_match
        except ValueError:
            pass # Paths are on different drives
    return None


class LogWatcherHandler(FileSystemEventHandler):
    def __init__(self, project_root, log_file):
        super().__init__()
        self.project_root = project_root
        self.log_file = log_file
        self.last_hash = None
        self.attempts = 0
        self.processing = False
        log_path = os.path.join(self.project_root, self.log_file)
        if os.path.exists(log_path):
            self.last_pos = os.path.getsize(log_path)
        else:
            self.last_pos = 0
        
    def on_modified(self, event):
        # We only care about the server log
        norm_src = event.src_path.replace('\\', '/')
        norm_log = self.log_file.replace('\\', '/')
        if not norm_src.endswith(norm_log):
            return
            
        if self.processing:
            return
            
        self.processing = True
        try:
            self.handle_log_update()
        finally:
            self.processing = False

    def handle_log_update(self):
        log_path = os.path.join(self.project_root, self.log_file)
        if not os.path.exists(log_path):
            return
            
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(0, os.SEEK_END)
            current_size = f.tell()
            
            if current_size < self.last_pos:
                self.last_pos = 0
                self.last_hash = None
                
            if current_size == self.last_pos:
                return
                
            f.seek(self.last_pos)
            content = f.read()
            self.last_pos = f.tell()
            
        if "Traceback" not in content:
            return
            
        tracebacks = content.split("Traceback (most recent call last):")
        if len(tracebacks) <= 1:
            return
            
        latest_tb = "Traceback (most recent call last):" + tracebacks[-1]
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
        
        target_file = extract_target_file(latest_tb, self.project_root)
        if not target_file:
            print("[SAFETY] Target file outside project root or could not be determined")
            print("[HEALER] Patch rejected")
            return
            
        try:
            with open(target_file, "r") as f:
                source_code = f.read()
                
            result = diagnose_and_fix(latest_tb, source_code)
            print("[AI] Diagnosis complete")
            
            fixed_code = result['fixed_code']
            
            print("[VALIDATOR] Validating patch...")
            if validate_code(fixed_code):
                print("[VALIDATOR] PASS")
                print("[HEALER] Applying patch...")
                
                with open(f"{target_file}.bak", "w") as f:
                    f.write(source_code)
                    
                with open(target_file, "w") as f:
                    f.write(fixed_code)
                    
                print("[SERVER] Reload triggered")
                
                branch_name = local_commit_fix(self.project_root, target_file)
                if branch_name:
                    github_push_and_pr(self.project_root, branch_name, target_file, result['explanation'])
                    
                print("[HEALER] Recovery successful")
                
                self.attempts = 0
            else:
                print("[VALIDATOR] PATCH REJECTED")
                
        except Exception as e:
            if "AI diagnosis failed safely" in str(e):
                print("[HEALER] AI diagnosis failed safely")
                print("[HEALER] No source code modified")
            else:
                print(f"[HEALER] Process failed: {e}")

def start_watcher(project_root):
    print("[WATCHER] Project detected")
    config = get_config(project_root)
    log_file = config.get("log_file", "logs/server.log")
    
    log_path = os.path.join(project_root, log_file)
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    if not os.path.exists(log_path):
        open(log_path, 'a').close()
        
    event_handler = LogWatcherHandler(project_root, log_file)
    observer = Observer()
    
    # Watch the log directory specifically
    watch_dir = log_dir if log_dir else project_root
    observer.schedule(event_handler, path=watch_dir, recursive=False)
    observer.start()
    
    print("[WATCHER] Log monitoring started")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=".", help="Project root path")
    args = parser.parse_args()
    
    start_watcher(os.path.abspath(args.project))
