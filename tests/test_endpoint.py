import os
import json
from fastapi.testclient import TestClient
from app.main import app
from app.config import SECRET

client = TestClient(app)

def test_missing_json():
    r = client.post("/task", data="not json")
    assert r.status_code == 400

def test_invalid_secret():
    payload = {"email": "a", "secret": "bad", "url": "http://example.com"}
    r = client.post("/task", json=payload)
    assert r.status_code == 403

def test_valid_structure():
    payload = {"email": "a", "secret": SECRET, "url": "http://example.com"}
    # This will attempt to run the handler; in unit tests you can mock the handler.
    r = client.post("/task", json=payload)
    assert r.status_code == 200
