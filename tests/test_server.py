import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    # The root endpoint now returns HTML, not JSON
    assert "Voice Agent Chat API" in response.text
    assert "API Status" in response.text
