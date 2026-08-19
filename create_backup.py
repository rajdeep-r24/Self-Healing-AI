import os
import zipfile
import shutil
from datetime import datetime

def create_backup_zip():
    project_root = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(project_root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"Enterprise-Self-Healing-AI-v1.0-Backup-{timestamp}.zip"
    zip_path = os.path.join(parent_dir, zip_name)

    exclude_dirs = {".venv", ".git", ".pytest_cache", "__pycache__", "temp_test_dir"}
    exclude_files = {".env"} # Exclude active secrets from archive for security; .env.example is included

    print(f"[BACKUP] Creating clean portable archive: {zip_name}...")
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file in exclude_files:
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, project_root)
                zipf.write(full_path, rel_path)

    print(f"[SUCCESS] Portable Backup ZIP created at:\n  {zip_path}")
    return zip_path

if __name__ == "__main__":
    create_backup_zip()
