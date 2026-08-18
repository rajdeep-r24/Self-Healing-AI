import os
import sys
import subprocess
import tempfile
import shutil

def validate_code(new_code: str, target_file_path: str, project_root: str) -> bool:
    """
    Validates the generated Python code using py_compile and pytest in a shadow workspace.
    Returns True if valid, False otherwise.
    """
    try:
        import pathlib
        real_project = pathlib.Path(project_root).resolve()
        real_target = pathlib.Path(target_file_path).resolve()
        
        try:
            if not real_target.is_relative_to(real_project):
                print("[VALIDATOR] Target file outside project boundary.")
                return False
        except AttributeError:
            if os.path.commonpath([str(real_project), str(real_target)]) != str(real_project):
                print("[VALIDATOR] Target file outside project boundary.")
                return False

        # 1. First do a quick syntax check using py_compile
        fd, temp_path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(new_code)
                
            compile_result = subprocess.run(
                [sys.executable, "-m", "py_compile", temp_path],
                capture_output=True,
                text=True
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        if compile_result.returncode != 0:
            print(f"[VALIDATOR] Syntax error in patch:\n{compile_result.stderr}")
            return False

        # 2. Shadow Pytest Gate
        with tempfile.TemporaryDirectory(prefix="shadow_workspace_", ignore_cleanup_errors=True) as shadow_dir:
            # Copy project files, ignoring heavy/unnecessary ones
            ignore_patterns = shutil.ignore_patterns(
                '.git', '.venv', '__pycache__', 'logs', '.self-healing', 'watcher_output.log'
            )
            
            # Python 3.8+ copytree has dirs_exist_ok=True
            shutil.copytree(project_root, shadow_dir, ignore=ignore_patterns, dirs_exist_ok=True)
            
            # Overwrite the target file in the shadow workspace
            rel_target = os.path.relpath(target_file_path, project_root)
            shadow_target = os.path.join(shadow_dir, rel_target)
            
            # Ensure the directory exists just in case
            os.makedirs(os.path.dirname(shadow_target), exist_ok=True)
            with open(shadow_target, 'w') as f:
                f.write(new_code)
                
            # Check if tests exist
            shadow_tests_dir = os.path.join(shadow_dir, "tests")
            has_tests = False
            if os.path.exists(shadow_tests_dir):
                for root, dirs, files in os.walk(shadow_tests_dir):
                    if any(f.startswith("test_") or f.endswith("_test.py") for f in files):
                        has_tests = True
                        break
            
            if not has_tests:
                print("[VALIDATOR] No tests found - Pytest Gate SKIPPED")
                return True

            # Run pytest on the shadow workspace
            shadow_env = os.environ.copy()
            shadow_env.pop("EVALUATION_MODE", None)
            try:
                pytest_result = subprocess.run(
                    [sys.executable, "-m", "pytest", "tests/"],
                    cwd=shadow_dir,
                    env=shadow_env,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            except subprocess.TimeoutExpired:
                print("[VALIDATOR] Pytest timeout.")
                return False
            
            if pytest_result.returncode == 0:
                print("[VALIDATOR] Shadow Pytest Gate PASS")
                return True
            else:
                print(f"[VALIDATOR] Shadow Pytest Gate FAILED in patch:\n{pytest_result.stdout}\n{pytest_result.stderr}")
                return False
            
    except Exception as e:
        print(f"[VALIDATOR] Validation failed with error: {e}")
        return False
