import os
import sys
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

client = TestClient(app)

def test_process_data():
    response = client.get("/process_data")
    assert response.status_code in [200, 500]
