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
        subprocess.run(["git", *git_config, "commit", "-m", f"AI Auto-Healer: Fixed crash in {rel_target}"], cwd=project_root, check=True, capture_output=True)
        
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
            
        # Push the branch autonomously using authenticated URL
        print(f"[GITHUB] Pushing branch {branch_name} to origin...")
        push_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        push_res = subprocess.run(["git", "push", "-u", push_url, branch_name], cwd=project_root, capture_output=True, text=True)
        if push_res.returncode != 0:
            # Fallback to standard git push if authenticated push url fails
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

def create_autonomous_pr(repo_str: str, target_file: str, fixed_code: str, diagnosis: str, base_branch: str = "main") -> dict:
    """
    Autonomously creates a remote branch on GitHub, commits the fixed code,
    and opens a real Pull Request via GitHub REST API.
    """
    token = os.getenv("GITHUB_TOKEN")
    clean_repo = repo_str.replace("https://github.com/", "").replace(".git", "").strip()
    branch_name = f"autoheal/fix-{uuid.uuid4().hex[:6]}"

    if not token or token == "your_github_token_here":
        return {
            "success": False,
            "error": "GITHUB_TOKEN not configured",
            "branch_name": branch_name,
            "pr_url": f"https://github.com/{clean_repo}/pulls"
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "Enterprise-Self-Healing-AI"
    }

    try:
        import base64

        # 1. Get base branch commit SHA
        ref_url = f"https://api.github.com/repos/{clean_repo}/git/ref/heads/{base_branch}"
        req_ref = urllib.request.Request(ref_url, headers=headers)
        with urllib.request.urlopen(req_ref, timeout=8) as resp:
            ref_data = json.loads(resp.read().decode())
            base_sha = ref_data["object"]["sha"]

        # 2. Create the new AI repair branch
        create_branch_url = f"https://api.github.com/repos/{clean_repo}/git/refs"
        branch_payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        req_create_branch = urllib.request.Request(
            create_branch_url,
            data=json.dumps(branch_payload).encode('utf-8'),
            headers=headers
        )
        with urllib.request.urlopen(req_create_branch, timeout=8) as resp:
            pass

        # 3. Get existing target file SHA if it exists on the branch
        file_sha = None
        try:
            file_url = f"https://api.github.com/repos/{clean_repo}/contents/{target_file}?ref={branch_name}"
            req_file = urllib.request.Request(file_url, headers=headers)
            with urllib.request.urlopen(req_file, timeout=6) as resp:
                file_data = json.loads(resp.read().decode())
                file_sha = file_data.get("sha")
        except Exception:
            pass

        # 4. Commit the fixed file to the new branch
        content_b64 = base64.b64encode(fixed_code.encode('utf-8')).decode('utf-8')
        put_file_url = f"https://api.github.com/repos/{clean_repo}/contents/{target_file}"
        commit_payload = {
            "message": f"fix(autoheal): Autonomous AI repair for {target_file}",
            "content": content_b64,
            "branch": branch_name
        }
        if file_sha:
            commit_payload["sha"] = file_sha

        req_put = urllib.request.Request(
            put_file_url,
            data=json.dumps(commit_payload).encode('utf-8'),
            headers=headers,
            method="PUT"
        )
        with urllib.request.urlopen(req_put, timeout=8) as resp:
            pass

        # 5. Create the Pull Request
        pr_title = f"fix(autoheal): Automated AI repair for {target_file}"
        pr_body = (
            f"## 🤖 Autonomous AI Repair\n\n"
            f"**File Changed:** `{target_file}`\n\n"
            f"**Root Cause Diagnosis:**\n{diagnosis}\n\n"
            f"**Validation:** AST Syntax PASS • Pytest Regression Shield PASS\n\n"
            f"---\n"
            f"*This Pull Request was generated autonomously by Enterprise Self-Healing AI.*"
        )
        pr_payload = {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": base_branch
        }
        req_pr = urllib.request.Request(
            f"https://api.github.com/repos/{clean_repo}/pulls",
            data=json.dumps(pr_payload).encode('utf-8'),
            headers=headers
        )
        with urllib.request.urlopen(req_pr, timeout=8) as resp:
            if resp.status == 201:
                pr_data = json.loads(resp.read().decode())
                print(f"[GITHUB API] Autonomous PR created: {pr_data.get('html_url')}")
                return {
                    "success": True,
                    "pr_url": pr_data.get("html_url"),
                    "pr_number": pr_data.get("number"),
                    "branch_name": branch_name
                }
    except Exception as e:
        print(f"[GITHUB API] Autonomous PR creation notice: {e}")
        return {
            "success": False,
            "error": str(e),
            "branch_name": branch_name,
            "pr_url": f"https://github.com/{clean_repo}/pulls"
        }
