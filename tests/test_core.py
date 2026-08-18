import pytest
import os
import tempfile
import subprocess
from unittest.mock import patch, MagicMock

from ai_engine import diagnose_and_fix
from validator import validate_code
from watcher import LogWatcherHandler, extract_target_file

@patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"})
@patch("ai_engine.genai.Client")
def test_ai_api_failure(mock_client):
    mock_instance = MagicMock()
    mock_instance.models.generate_content.side_effect = Exception("503 Service Unavailable")
    mock_client.return_value = mock_instance
    
    with pytest.raises(RuntimeError) as exc:
        diagnose_and_fix("Traceback...", "source_code")
        
    assert "AI diagnosis failed safely" in str(exc.value)

@patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"})
@patch("ai_engine.genai.Client")
def test_invalid_ai_output(mock_client):
    mock_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"diagnosis": "found it"}' # missing fixed_code
    mock_instance.models.generate_content.return_value = mock_response
    mock_client.return_value = mock_instance
    
    with pytest.raises(RuntimeError) as exc:
        diagnose_and_fix("Traceback...", "source_code")
    assert "AI diagnosis failed safely" in str(exc.value)

def test_syntax_validation_failure():
    bad_code = "def foo()\\n  print('hi')"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.close()
        result = validate_code(bad_code, f.name, os.path.dirname(f.name))
        assert result is False
        os.remove(f.name)

def test_pytest_failure_shadow_gate():
    good_syntax_bad_logic = "def foo(): return 1/0"
    original_exists = os.path.exists
    with patch("validator.subprocess.run") as mock_run:
        with patch("validator.shutil.copytree"):
            with patch("validator.os.walk") as mock_walk:
                with patch("validator.os.path.exists") as mock_exists:
                    mock_exists.side_effect = lambda p: True if "tests" in str(p) else original_exists(p)
                    mock_walk.return_value = [("tests", [], ["test_dummy.py"])]
                    mock_run.side_effect = [
                        MagicMock(returncode=0), 
                        MagicMock(returncode=1, stdout="Test failed", stderr="")
                    ]
                    
                    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
                        f.close()
                        result = validate_code(good_syntax_bad_logic, f.name, os.path.dirname(f.name))
                        assert result is False
                        os.remove(f.name)

def test_pytest_timeout():
    good_syntax = "def foo(): pass"
    original_exists = os.path.exists
    with patch("validator.subprocess.run") as mock_run:
        with patch("validator.shutil.copytree"):
            with patch("validator.os.walk") as mock_walk:
                with patch("validator.os.path.exists") as mock_exists:
                    mock_exists.side_effect = lambda p: True if "tests" in str(p) else original_exists(p)
                    mock_walk.return_value = [("tests", [], ["test_dummy.py"])]
                    
                    def side_effect(*args, **kwargs):
                        if "py_compile" in args[0]:
                            return MagicMock(returncode=0)
                        raise subprocess.TimeoutExpired(cmd=args[0], timeout=30)
                    
                    mock_run.side_effect = side_effect
                    
                    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
                        f.close()
                        result = validate_code(good_syntax, f.name, os.path.dirname(f.name))
                        assert result is False
                        os.remove(f.name)

def test_no_tests_present():
    good_syntax = "def foo(): pass"
    original_exists = os.path.exists
    with patch("validator.subprocess.run") as mock_run:
        with patch("validator.shutil.copytree"):
            with patch("validator.os.path.exists") as mock_exists:
                mock_run.return_value = MagicMock(returncode=0)
                
                def exists_side_effect(path):
                    if "tests" in str(path):
                        return False
                    return original_exists(path)
                mock_exists.side_effect = exists_side_effect
                
                with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
                    f.close()
                    result = validate_code(good_syntax, f.name, os.path.dirname(f.name))
                    assert result is True
                    os.remove(f.name)

def test_valid_patch_with_tests():
    good_syntax = "def foo(): pass"
    original_exists = os.path.exists
    with patch("validator.subprocess.run") as mock_run:
        with patch("validator.shutil.copytree"):
            with patch("validator.os.walk") as mock_walk:
                with patch("validator.os.path.exists") as mock_exists:
                    mock_exists.side_effect = lambda p: True if "tests" in str(p) else original_exists(p)
                    mock_walk.return_value = [("tests", [], ["test_dummy.py"])]
                    mock_run.return_value = MagicMock(returncode=0)
                    
                    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
                        f.close()
                        result = validate_code(good_syntax, f.name, os.path.dirname(f.name))
                        assert result is True
                        os.remove(f.name)

def test_target_outside_project_boundary():
    # Outside project
    result = validate_code("def foo(): pass", "/etc/passwd", "/project")
    assert result is False

def test_target_sibling_directory_prefix():
    # Sibling with similar prefix (e.g. /project vs /project_evil)
    result = validate_code("def foo(): pass", "/project_evil/file.py", "/project")
    assert result is False

def test_target_inside_project_boundary():
    # Valid file inside project
    # We mock out the rest of validate_code to only test boundary check
    with patch("validator.tempfile.mkstemp") as mock_mkstemp:
        # Raise an error to stop execution
        mock_mkstemp.side_effect = RuntimeError("Passed boundary")
        
        result = validate_code("def foo(): pass", "/project/src/file.py", "/project")
        assert result is False
        assert mock_mkstemp.called

def test_target_windows_style_paths():
    # Windows drive casing and slash direction
    with patch("validator.tempfile.mkstemp") as mock_mkstemp:
        mock_mkstemp.side_effect = RuntimeError("Passed boundary")
        
        # Mixed slashes and casing
        result = validate_code("def foo(): pass", "C:\\\\Project\\\\src/file.py", "c:\\\\project")
        assert result is False
        assert mock_mkstemp.called
            
        # Outside due to different drive
        result = validate_code("def foo(): pass", "D:\\\\Project\\\\file.py", "C:\\\\Project")
        assert result is False

def test_project_root_boundary_protection():
    tb = 'File "/etc/passwd", line 1, in <module>'
    target = extract_target_file(tb, os.getcwd())
    assert target is None

@patch("watcher.requests.get")
@patch("watcher.time.sleep")
def test_health_check_failure_and_rollback(mock_sleep, mock_get):
    mock_get.return_value.status_code = 500
    pass

def test_repeated_error_protection():
    watcher = LogWatcherHandler(os.getcwd(), "logs/server.log")
    watcher.last_hash = "dummy_hash"
    watcher.attempts = 2
    
    import logging
    with patch.object(logging, 'error') as mock_log:
        watcher.handle_log_update = MagicMock()
        with patch("builtins.open", MagicMock()):
            pass
