import argparse
import os
import json
import sys
import subprocess

# Add the directory containing watcher.py to sys.path so we can import it
CLI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CLI_DIR)

from watcher import start_watcher

def get_config_path(cwd):
    return os.path.join(cwd, ".self-healing", "config.json")

def load_config(config_path):
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None

def is_git_available():
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def init_project():
    cwd = os.getcwd()
    print("[SELF-HEALING] Initializing project...")
    print(f"[PROJECT] {cwd}")
    
    # Check git
    git_repo_detected = os.path.exists(os.path.join(cwd, ".git"))
    if is_git_available() and git_repo_detected:
        print("[GIT] Repository detected")
    else:
        print("[GIT] Repository not detected")
        print("[GIT] Git-based repair features may be unavailable")
        
    config_dir = os.path.join(cwd, ".self-healing")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "config.json")
    
    if os.path.exists(config_path):
        print("[CONFIG] Existing configuration detected")
        print("[CONFIG] Keeping existing configuration")
        print("[SELF-HEALING] Initialization complete")
        return
        
    config_data = {
        "project_root": ".",
        "log_file": "logs/server.log",
        "health_check_url": "http://127.0.0.1:8000/process_data"
    }
    
    try:
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=4)
        print("[CONFIG] Created .self-healing/config.json")
    except Exception as e:
        print(f"[ERROR] Could not create configuration: {e}")
        return
        
    print("[SELF-HEALING] Initialization complete")

def start_project():
    cwd = os.getcwd()
    config_path = get_config_path(cwd)
    
    if not os.path.exists(config_path):
        print("[ERROR] Project is not initialized.")
        print("Run: self-healing init")
        return
        
    config = load_config(config_path)
    if config is None:
        print("[ERROR] Invalid .self-healing/config.json")
        print("Please run `python self_healing_cli.py init` or fix the configuration.")
        return
        
    print("[SELF-HEALING] Starting...")
    print(f"[PROJECT] {cwd}")
    print("[CONFIG] Configuration loaded")
    
    log_file = config.get("log_file", "logs/server.log")
    
    # Path traversal protection
    log_file_norm = os.path.normpath(log_file)
    if log_file_norm.startswith("..") or os.path.isabs(log_file_norm):
        print("[ERROR] Invalid log_file path in config. Path must be relative to project root and safely contained within it.")
        return
        
    log_path = os.path.join(cwd, log_file)
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        
    print("[WATCHER] Monitoring started")
    start_watcher(cwd)

def status_project():
    cwd = os.getcwd()
    config_path = get_config_path(cwd)
    
    print("[SELF-HEALING] Project Status\\n")
    print(f"Project: {cwd}")
    
    git_repo_detected = os.path.exists(os.path.join(cwd, ".git"))
    print(f"Git: {'Detected' if git_repo_detected else 'Not detected'}")
    
    config_exists = os.path.exists(config_path)
    print(f"Initialized: {'Yes' if config_exists else 'No'}")
    
    if config_exists:
        print("Config: .self-healing/config.json")
        config = load_config(config_path)
        if config is None:
            print("Log: ERROR (Invalid configuration)")
        else:
            log_file = config.get("log_file", "Not specified")
            print(f"Log: {log_file}")
    else:
        print("Config: Not detected")
        print("Log: N/A")

def main():
    parser = argparse.ArgumentParser(description="Self-Healing AI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    init_parser = subparsers.add_parser("init", help="Initialize self-healing in current project")
    start_parser = subparsers.add_parser("start", help="Start the self-healing watcher")
    status_parser = subparsers.add_parser("status", help="Show the current status of self-healing configuration")
    
    try:
        args = parser.parse_args()
    except SystemExit:
        # Avoid crashing with raw traces on help or invalid args
        return
        
    try:
        if args.command == "init":
            init_project()
        elif args.command == "start":
            start_project()
        elif args.command == "status":
            status_project()
    except KeyboardInterrupt:
        print("\\n[SELF-HEALING] Operation cancelled by user.")
    except Exception as e:
        print(f"\\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
