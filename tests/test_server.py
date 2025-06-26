import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Voice Agent API is running."}
