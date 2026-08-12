import os
from git_module import local_commit_fix, github_push_and_pr
import urllib.request
import uuid
import subprocess

try:
    print("Creating dummy change...")
    with open("app.py", "a") as f:
        f.write("\n# Dummy change\n")
        
    print("Committing locally...")
    branch_name = local_commit_fix(".", "app.py")
    print(f"Branch name: {branch_name}")
    
    if branch_name:
        print("Pushing and PR...")
        github_push_and_pr(".", branch_name, "app.py", "Test diagnosis")
        
    print("Resetting app.py...")
    subprocess.run(["git", "checkout", "main"])
    subprocess.run(["git", "restore", "app.py"])
    
except Exception as e:
    print(f"Test failed: {e}")
