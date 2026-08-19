import pytest
import os
from unittest.mock import patch, MagicMock
from ai_engine import diagnose_and_fix

# CASE A: Primary 503, Fallback valid
@patch.dict(os.environ, {"GEMINI_API_KEY": "dummy", "SELF_HEALING_DEMO_MODE": "true"})
@patch("ai_engine.genai.Client")
def test_fallback_case_a(mock_client):
    mock_instance = MagicMock()
    mock_response_valid = MagicMock()
    mock_response_valid.text = '{"diagnosis": "foo", "fixed_code": "bar"}'
    
    mock_instance.models.generate_content.side_effect = [
        Exception("503 Service Unavailable"),
        mock_response_valid
    ]
    mock_client.return_value = mock_instance
    
    res = diagnose_and_fix("traceback", "code")
    assert res["diagnosis"] == "foo"
    assert res["fixed_code"] == "bar"

# CASE B: Primary 503, Fallback 503
@patch.dict(os.environ, {"GEMINI_API_KEY": "dummy", "SELF_HEALING_DEMO_MODE": "true"})
@patch("ai_engine.genai.Client")
def test_fallback_case_b(mock_client):
    mock_instance = MagicMock()
    
    mock_instance.models.generate_content.side_effect = [
        Exception("503 Service Unavailable"),
        Exception("503 Service Unavailable")
    ]
    mock_client.return_value = mock_instance
    
    with pytest.raises(RuntimeError) as exc:
        diagnose_and_fix("traceback", "code")
        
    assert "AI_SERVICE_UNAVAILABLE" in str(exc.value)

# CASE C: Primary timeout, Fallback valid
@patch.dict(os.environ, {"GEMINI_API_KEY": "dummy", "SELF_HEALING_DEMO_MODE": "true"})
@patch("ai_engine.genai.Client")
def test_fallback_case_c(mock_client):
    mock_instance = MagicMock()
    mock_response_valid = MagicMock()
    mock_response_valid.text = '{"diagnosis": "foo2", "fixed_code": "bar2"}'
    
    mock_instance.models.generate_content.side_effect = [
        Exception("Timeout error"),
        mock_response_valid
    ]
    mock_client.return_value = mock_instance
    
    res = diagnose_and_fix("traceback", "code")
    assert res["diagnosis"] == "foo2"

# CASE D: Both models malformed -> safe rejection
@patch.dict(os.environ, {"GEMINI_API_KEY": "dummy", "SELF_HEALING_DEMO_MODE": "true"})
@patch("ai_engine.genai.Client")
def test_fallback_case_d(mock_client):
    mock_instance = MagicMock()
    mock_response_invalid = MagicMock()
    mock_response_invalid.text = 'not json'
    
    mock_instance.models.generate_content.side_effect = [
        mock_response_invalid,
        mock_response_invalid
    ]
    mock_client.return_value = mock_instance
    
    with pytest.raises(RuntimeError) as exc:
        diagnose_and_fix("traceback", "code")
        
    assert "AI diagnosis failed safely" in str(exc.value)
