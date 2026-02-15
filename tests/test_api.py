import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    json_data = response.json()
    assert "Welcome" in json_data["message"]
    assert json_data["docs_url"] == "/docs"

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "Bank Statement Intelligence"
    }

def test_analyze_invalid_format():
    # Send a text file instead of PDF
    files = {"file": ("test.txt", b"dummy file content", "text/plain")}
    response = client.post("/api/v1/analyze", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]

def test_analyze_missing_file():
    response = client.post("/api/v1/analyze")
    assert response.status_code == 422 # FastAPI validation error for missing field
