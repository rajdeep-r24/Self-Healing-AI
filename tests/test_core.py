import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Import existing tests to ensure full test suite coverage in test_core
from tests.test_cli import TestSelfHealingCLI
from tests.test_fallback import (
    test_fallback_case_a,
    test_fallback_case_b,
    test_fallback_case_c,
    test_fallback_case_d,
)
from tests.test_app import test_process_data
from watcher import perform_health_check

class TestHealthCheckAndDemoMode(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_health_check_fast_pass(self, mock_urlopen):
        # Immediate HTTP 200 response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        result = perform_health_check("http://127.0.0.1:8000/process_data", max_wait=2.0, interval=0.1)
        self.assertTrue(result)

    @patch("urllib.request.urlopen")
    def test_health_check_timeout(self, mock_urlopen):
        # Continuous connection failure
        mock_urlopen.side_effect = Exception("Connection refused")
        
        result = perform_health_check("http://127.0.0.1:8000/process_data", max_wait=0.2, interval=0.05)
        self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
