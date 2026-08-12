import argparse
import os
import json
import sys

# Add the directory containing watcher.py to sys.path so we can import it
CLI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CLI_DIR)

from watcher import start_watcher

def init_project():
    cwd = os.getcwd()
    print("[SELF-HEALING] Initializing project...")
    print(f"[SELF-HEALING] Project: {cwd}")
    
    # Check git
    if os.path.exists(os.path.join(cwd, ".git")):
        print("[GIT] Repository detected")
    else:
        print("[GIT] No Git repository detected. Git features disabled.")
        
    # Create config
    config_dir = os.path.join(cwd, ".self-healing")
    os.makedirs(config_dir, exist_ok=True)
    
    config_path = os.path.join(config_dir, "config.json")
    config_data = {
        "project_root": ".",
        "log_file": "logs/server.log"
    }
    
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=4)
        
    print("[SELF-HEALING] Configuration created")
    print("[SELF-HEALING] Initialization complete")

def start_project():
    cwd = os.getcwd()
    # While start reads config_path, start_watcher handles parsing it too. We just invoke watcher.
    # We can check if config exists just to warn, but watcher falls back safely.
    config_path = os.path.join(cwd, ".self-healing", "config.json")
    if not os.path.exists(config_path):
        print("[SELF-HEALING] Warning: Project not explicitly initialized with config.json.")
        
    start_watcher(cwd)

def main():
    parser = argparse.ArgumentParser(description="Self-Healing AI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize self-healing in current project")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the self-healing watcher")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_project()
    elif args.command == "start":
        start_project()

if __name__ == "__main__":
    main()
