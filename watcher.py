import os
import time
import hashlib
import logging
import subprocess
import uuid
import argparse
import json
import re
import urllib.request
from urllib.error import URLError, HTTPError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ai_engine import diagnose_and_fix
from validator import validate_code
from git_module import local_commit_fix, github_push_and_pr
from bounded_pytest import run_pytest_bounded
from tui_dashboard import get_dashboard

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

def perform_health_check(health_url, max_wait=8.0, interval=0.5, timeout=1.5, dashboard=None):
    """
    Performs short-polling HTTP health check immediately after patch.
    Polls every 0.5 seconds for up to 8.0 seconds.
    Returns True immediately on HTTP 200, False on timeout.
    """
    print("[HEALTH] Checking...")
    if dashboard:
        dashboard.update_activity(f"Polling {health_url} (every 0.5s)...")
    start_time = time.time()
    attempt = 1
    while time.time() - start_time < max_wait:
        try:
            if dashboard:
                dashboard.update_activity(f"Health check attempt #{attempt} on {health_url}...")
            req = urllib.request.Request(health_url, headers={"User-Agent": "Self-Healing-Watcher"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    elapsed = time.time() - start_time
                    print(f"[HEALTH] PASS ({elapsed:.1f}s)")
                    return True
        except Exception:
            # Server not yet ready or returning error
            pass
        attempt += 1
        time.sleep(interval)

    elapsed = time.time() - start_time
    print(f"[HEALTH] TIMEOUT ({elapsed:.1f}s)")
    return False


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
        
        is_demo = os.getenv("SELF_HEALING_DEMO_MODE", "").lower() in ("true", "1", "yes")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.dashboard = get_dashboard(project_root, log_file, is_demo_mode=is_demo, model_name=model)
        
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

        start_total = time.time()
        self.last_hash = tb_hash
        self.attempts += 1
        
        target_file = extract_target_file(latest_tb, self.project_root)
        err_match = re.search(r'([A-Za-z0-9_]+Error:[^\n]+)', latest_tb)
        err_desc = err_match.group(1) if err_match else "Exception"

        print("[WATCHER] Error detected")
        print("[AI] Analyzing...")

        if self.dashboard and target_file:
            self.dashboard.start_repair(err_desc, target_file)
        
        if not target_file:
            print("[SAFETY] Target file outside project root or could not be determined")
            print("[HEALER] Patch rejected")
            if self.dashboard:
                self.dashboard.finish_repair(success=False, summary_msg="Target file outside project root")
            return
            
        try:
            with open(target_file, "r") as f:
                source_code = f.read()
                
            if self.dashboard:
                self.dashboard.set_stage_active("ai", "Querying Gemini API for root cause & patch...", est_time="3-6s")

            start_ai = time.time()
            result = diagnose_and_fix(latest_tb, source_code)
            ai_duration = time.time() - start_ai
            print(f"[AI] Diagnosis complete ({ai_duration:.1f}s)")
            
            if self.dashboard:
                self.dashboard.set_stage_complete("ai", success=True, info_msg="Patch generated", duration=ai_duration)
            
            fixed_code = result['fixed_code']
            
            if self.dashboard:
                self.dashboard.set_stage_active("validator", "Checking AST syntax with py_compile...")

            if not validate_code(fixed_code):
                print("[VALIDATOR] PATCH REJECTED")
                print("[HEALER] Patch rejected")
                if self.dashboard:
                    self.dashboard.set_stage_complete("validator", success=False, info_msg="Syntax Error")
                    self.dashboard.finish_repair(success=False, summary_msg="Syntax validation failed")
                return
            print("[VALIDATOR] PASS")
            if self.dashboard:
                self.dashboard.set_stage_complete("validator", success=True, info_msg="Syntax valid")

            # Pytest bounded check for project test suite safety
            if self.dashboard:
                self.dashboard.set_stage_active("pytest", "Executing test suite safety shield...")

            test_target = "tests/test_app.py" if os.path.exists(os.path.join(self.project_root, "tests", "test_app.py")) else "tests"
            test_status, _, _ = run_pytest_bounded([test_target, "-q"], cwd=self.project_root, timeout=5)
            if test_status != "PASS":
                print(f"[TEST] FAIL ({test_status})")
                print("[HEALER] Patch rejected")
                if self.dashboard:
                    self.dashboard.set_stage_complete("pytest", success=False, info_msg=f"Pytest {test_status}")
                    self.dashboard.finish_repair(success=False, summary_msg="Pytest shield rejected patch")
                return
            print("[TEST] PASS")
            if self.dashboard:
                self.dashboard.set_stage_complete("pytest", success=True, info_msg="Regression tests passed")

            print("[HEALER] Applying patch")
            if self.dashboard:
                self.dashboard.set_stage_active("patch", f"Backing up and patching {os.path.basename(target_file)}...")

            bak_path = f"{target_file}.bak"
            with open(bak_path, "w") as f:
                f.write(source_code)
                
            with open(target_file, "w") as f:
                f.write(fixed_code)

            if self.dashboard:
                self.dashboard.set_stage_complete("patch", success=True, info_msg=f"Patched {os.path.basename(target_file)}")
                
            # Configurable health check
            config = get_config(self.project_root)
            health_url = config.get("health_check_url", "http://127.0.0.1:8000/process_data")
            
            if self.dashboard:
                self.dashboard.set_stage_active("health", f"Polling {health_url}...", est_time="0.5-2s")

            health_passed = perform_health_check(health_url, max_wait=8.0, interval=0.5, timeout=1.5, dashboard=self.dashboard)
            if not health_passed:
                print("[ROLLBACK] Restoring original file...")
                with open(bak_path, "r") as f:
                    orig_code = f.read()
                with open(target_file, "w") as f:
                    f.write(orig_code)
                print("[HEALER] Rollback complete. Patch rejected.")
                if self.dashboard:
                    self.dashboard.set_stage_complete("health", success=False, info_msg="Timeout (8s)")
                    self.dashboard.finish_repair(success=False, summary_msg="Health check failed. Code rolled back.")
                return
            
            if self.dashboard:
                self.dashboard.set_stage_complete("health", success=True, info_msg="HTTP 200 OK")

            if self.dashboard:
                self.dashboard.set_stage_active("git", "Creating git fix branch & creating PR...")

            branch_name = local_commit_fix(self.project_root, target_file)
            if branch_name:
                github_push_and_pr(self.project_root, branch_name, target_file, result.get('explanation', result.get('diagnosis', '')))
                if self.dashboard:
                    self.dashboard.set_stage_complete("git", success=True, info_msg=f"Branch: {branch_name}")
            else:
                if self.dashboard:
                    self.dashboard.set_stage_complete("git", success=True, info_msg="Local Git fix complete")
                
            total_duration = time.time() - start_total
            print(f"[HEALER] Recovery successful ({total_duration:.1f}s)")
            if self.dashboard:
                self.dashboard.finish_repair(success=True, summary_msg=f"Fixed {err_desc} in {os.path.basename(target_file)}")
            
            self.attempts = 0
            
        except Exception as e:
            if "AI diagnosis failed safely" in str(e):
                print("[HEALER] AI diagnosis failed safely")
                print("[HEALER] No source code modified")
                if self.dashboard:
                    self.dashboard.set_stage_complete("ai", success=False, info_msg="AI unavailable")
                    self.dashboard.finish_repair(success=False, summary_msg="AI diagnosis failed safely")
            else:
                print(f"[HEALER] Process failed: {e}")
                if self.dashboard:
                    self.dashboard.finish_repair(success=False, summary_msg=f"Error: {e}")

def start_watcher(project_root):
    config = get_config(project_root)
    log_file = config.get("log_file", "logs/server.log")
    
    log_path = os.path.join(project_root, log_file)
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    if not os.path.exists(log_path):
        open(log_path, 'a').close()
        
    is_demo = os.getenv("SELF_HEALING_DEMO_MODE", "").lower() in ("true", "1", "yes")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    dashboard = get_dashboard(project_root, log_file, is_demo_mode=is_demo, model_name=model)
    dashboard.print_banner()

    print("[WATCHER] Project detected")
    event_handler = LogWatcherHandler(project_root, log_file)
    observer = Observer()
    
    # Watch the log directory specifically
    watch_dir = log_dir if log_dir else project_root
    observer.schedule(event_handler, path=watch_dir, recursive=False)
    observer.start()
    
    print("[WATCHER] Log monitoring started")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=".", help="Project root path")
    args = parser.parse_args()
    
    start_watcher(os.path.abspath(args.project))
