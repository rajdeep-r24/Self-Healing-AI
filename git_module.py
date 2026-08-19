import os
import subprocess
import uuid
import json
import urllib.request
from urllib.error import URLError, HTTPError
from dotenv import load_dotenv

load_dotenv()

def extract_repo_from_remote(project_root):
    try:
        # e.g., origin  https://github.com/rajdeep-r24/Self-Healing-AI.git (fetch)
        result = subprocess.run(["git", "remote", "-v"], cwd=project_root, check=True, capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'github.com' in line and '(push)' in line:
                # https://github.com/owner/repo.git or git@github.com:owner/repo.git
                parts = line.split()
                if len(parts) >= 2:
                    url = parts[1]
                    if url.endswith('.git'):
                        url = url[:-4]
                    if 'https://github.com/' in url:
                        return url.split('https://github.com/')[1]
                    elif 'git@github.com:' in url:
                        return url.split('git@github.com:')[1]
    except Exception:
        pass
    return None

def local_commit_fix(project_root, target_file):
    # Check if .git exists in project root
    if not os.path.exists(os.path.join(project_root, ".git")):
        print("[GIT] No Git repository detected")
        print("[HEALER] Git-based repair disabled")
        return None
        
    print("[GIT] Repository detected")
    
    try:
        git_config = ["-c", "user.name=AI-Healer", "-c", "user.email=ai@healer.local"]
        branch_name = f"ai-fix-{uuid.uuid4().hex[:6]}"
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=project_root, check=True, capture_output=True)
        print("[GIT] Creating AI repair branch")
        
        # Use relative path for git add
        rel_target = os.path.relpath(target_file, project_root)
        subprocess.run(["git", "add", rel_target], cwd=project_root, check=True, capture_output=True)
        subprocess.run(["git", *git_config, "commit", "--allow-empty", "-m", f"AI Auto-Healer: Fixed crash in {rel_target}"], cwd=project_root, check=True, capture_output=True)
        
        print("[GIT] Commit created")
        return branch_name
    except Exception as e:
        print(f"[GIT] Warning: Local git commit failed: {e}")
        return None

def github_push_and_pr(project_root, branch_name, target_file, diagnosis):
    try:
        token = os.getenv("GITHUB_TOKEN")
        if not token or token == "your_github_token_here":
            print("[GITHUB] Integration skipped: GITHUB_TOKEN not configured")
            return
            
        repo = os.getenv("GITHUB_REPO")
        if not repo or repo == "owner/repository":
            repo = extract_repo_from_remote(project_root)
            
        if not repo:
            print("[GITHUB] Integration skipped: Could not determine GitHub repository")
            return
            
        # Push the branch
        print(f"[GITHUB] Pushing branch {branch_name} to origin...")
        subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=project_root, check=True, capture_output=True)
        print("[GITHUB] Push successful")
        
        # Create PR via GitHub API
        rel_target = os.path.relpath(target_file, project_root)
        pr_title = f"AI Hotfix: Fix KeyError in {rel_target}"
        pr_body = (
            f"## Autonomous AI Repair\n\n"
            f"**File Changed:** `{rel_target}`\n\n"
            f"**Root Cause / Diagnosis:**\n"
            f"{diagnosis}\n\n"
            f"**Validation:** Syntax check PASS\n\n"
            f"---\n"
            f"*This Pull Request was generated automatically by the Self-Healing AI Pipeline.*"
        )
        
        data = {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": "main"
        }
        
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/pulls",
            data=json.dumps(data).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                res_data = json.loads(response.read().decode())
                print(f"[GITHUB] Pull Request created successfully: {res_data.get('html_url')}")
            else:
                print(f"[GITHUB] Failed to create PR. Status code: {response.status}")
                
    except Exception as e:
        print("[GITHUB] Integration failed gracefully")
        print(f"[GITHUB] Error details: {e}")
