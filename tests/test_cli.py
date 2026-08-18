import os
import json
import subprocess
import tempfile
import unittest
import shutil

CLI_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "self_healing_cli.py"))

class TestSelfHealingCLI(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def run_cli(self, args):
        result = subprocess.run(
            ["python", CLI_SCRIPT] + args,
            capture_output=True,
            text=True
        )
        return result

    def test_init_creates_config(self):
        # Init in a clean directory
        res = self.run_cli(["init"])
        self.assertIn("[SELF-HEALING] Initializing project...", res.stdout)
        self.assertIn("[CONFIG] Created .self-healing/config.json", res.stdout)
        
        config_path = os.path.join(self.test_dir, ".self-healing", "config.json")
        self.assertTrue(os.path.exists(config_path))

    def test_init_existing_config(self):
        # Create a dummy config
        config_dir = os.path.join(self.test_dir, ".self-healing")
        os.makedirs(config_dir)
        config_path = os.path.join(config_dir, "config.json")
        with open(config_path, "w") as f:
            f.write('{"custom": True}')

        # Run init
        res = self.run_cli(["init"])
        self.assertIn("[CONFIG] Existing configuration detected", res.stdout)
        self.assertIn("[CONFIG] Keeping existing configuration", res.stdout)
        
        with open(config_path, "r") as f:
            content = f.read()
        self.assertIn("custom", content)

    def test_status_missing_config(self):
        res = self.run_cli(["status"])
        self.assertIn("Config: Not detected", res.stdout)
        self.assertIn("Log: N/A", res.stdout)

    def test_status_invalid_config(self):
        config_dir = os.path.join(self.test_dir, ".self-healing")
        os.makedirs(config_dir)
        config_path = os.path.join(config_dir, "config.json")
        with open(config_path, "w") as f:
            f.write('{invalid_json}')

        res = self.run_cli(["status"])
        self.assertIn("Log: ERROR (Invalid configuration)", res.stdout)

    def test_status_valid_config(self):
        self.run_cli(["init"])
        res = self.run_cli(["status"])
        self.assertIn("Config: .self-healing/config.json", res.stdout)
        self.assertIn("Log: logs/server.log", res.stdout)

    def test_non_git_directory(self):
        # Temporary directory has no .git folder
        res = self.run_cli(["init"])
        self.assertIn("[GIT] Repository not detected", res.stdout)
        
    def test_start_missing_config(self):
        res = self.run_cli(["start"])
        self.assertIn("[ERROR] Project is not initialized.", res.stdout)

    def test_start_invalid_config(self):
        config_dir = os.path.join(self.test_dir, ".self-healing")
        os.makedirs(config_dir)
        config_path = os.path.join(config_dir, "config.json")
        with open(config_path, "w") as f:
            f.write('{invalid_json}')
            
        res = self.run_cli(["start"])
        self.assertIn("[ERROR] Invalid .self-healing/config.json", res.stdout)

if __name__ == '__main__':
    unittest.main()
