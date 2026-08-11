import os
import subprocess
import tempfile

def validate_code(new_code: str) -> bool:
    """
    Validates the generated Python code using py_compile.
    Returns True if valid, False otherwise.
    """
    try:
        # Create a temporary file to check syntax
        fd, temp_path = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, 'w') as f:
            f.write(new_code)
            
        # Run py_compile
        result = subprocess.run(
            ["python", "-m", "py_compile", temp_path],
            capture_output=True,
            text=True
        )
        
        # Cleanup
        os.remove(temp_path)
        
        if result.returncode == 0:
            return True
        else:
            print(f"[VALIDATOR] Syntax error in patch:\n{result.stderr}")
            return False
            
    except Exception as e:
        print(f"[VALIDATOR] Validation failed with error: {e}")
        return False
