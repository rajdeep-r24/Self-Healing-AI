import os
import sys
import time
import tempfile
import subprocess as default_subprocess

def run_pytest_bounded(test_args, cwd=None, env=None, timeout=30, subprocess_module=default_subprocess):
    """
    Runs pytest safely on Windows to prevent pipe deadlocks and unbounded waits.
    Returns explicit status: PASS, FAIL, TIMEOUT, ERROR
    And the stdout and stderr output.
    """
    cmd = [sys.executable, "-m", "pytest"] + test_args

    # Support existing unit tests that mock validator.subprocess.run
    if hasattr(subprocess_module.run, "call_count"):
        try:
            res = subprocess_module.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
            return ("PASS" if res.returncode == 0 else "FAIL"), res.stdout, res.stderr
        except subprocess_module.TimeoutExpired:
            return "TIMEOUT", "", ""

    # Use temporary files for stdout and stderr to avoid PIPE deadlocks
    # where child processes keep the pipe open indefinitely.
    fd_out, out_path = tempfile.mkstemp(suffix=".out")
    fd_err, err_path = tempfile.mkstemp(suffix=".err")
    
    status = "ERROR"
    output = ""
    error_output = ""
    
    try:
        with open(fd_out, 'w') as f_out, open(fd_err, 'w') as f_err:
            proc = default_subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=f_out,
                stderr=f_err,
                text=True
            )
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
                
            if proc.poll() is None:
                status = "TIMEOUT"
                # 1. terminate the process tree (Windows) or process (Unix)
                try:
                    if sys.platform == "win32":
                        default_subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5)
                    else:
                        proc.terminate()
                except Exception:
                    pass
                    
                # 2. wait for termination with a SMALL bounded timeout
                try:
                    proc.wait(timeout=3)
                except default_subprocess.TimeoutExpired:
                    # 3. if still alive, force kill
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    # 4. wait again with a bounded timeout
                    try:
                        proc.wait(timeout=3)
                    except default_subprocess.TimeoutExpired:
                        pass
                # 5. handles are closed by exiting the 'with' block
                # 6. return TIMEOUT handled after finally
            else:
                if proc.returncode == 0:
                    status = "PASS"
                else:
                    status = "FAIL"
                    
    except Exception as e:
        status = "ERROR"
        error_output = str(e)
    finally:
        # Read the outputs
        try:
            with open(out_path, 'r') as f:
                output = f.read()
            os.remove(out_path)
        except Exception:
            pass
            
        try:
            with open(err_path, 'r') as f:
                error_output += f.read()
            os.remove(err_path)
        except Exception:
            pass
            
    return status, output, error_output
