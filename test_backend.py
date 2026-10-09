import sqlite3
import os
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure test DB is clean
from backend.main import app
from backend.database import DB_PATH, SCHEMA_PATH, ensure_database

client = TestClient(app)

def setup_module(module):
    """Ensure database exists and is loaded with schema before tests."""
    ensure_database()

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"

def test_list_clients():
    response = client.get("/api/v1/clients")
    assert response.status_code == 200
    clients = response.json()
    assert len(clients) >= 5
    client_ids = [c["client_id"] for c in clients]
    assert "CL-1001" in client_ids

def test_auto_approve_claim():
    # Submit a standard carrier fault under $2,500 for CL-1001
    claim_payload = {
        "order_id": "TEST-AUTO-01",
        "tracking_number": "TRK-TEST-AUTO-01",
        "client_id": "CL-1001",
        "declared_value": 5000.0,
        "claim_amount": 1200.0,
        "delay_cause": "CARRIER_FAULT",
        "notes": "Driver breakdown test scenario",
    }
    response = client.post("/api/v1/claims/submit", json=claim_payload)
    assert response.status_code == 201
    order = response.json()
    assert order["claim_status"] == "AUTO_APPROVE"
    assert "AUTO_APPROVE" in order["claim_status"]
    assert "CARRIER_FAULT" in order["delay_cause"]

def test_audit_flag_high_value():
    # Carrier fault but claim exceeds $2,500 threshold
    claim_payload = {
        "order_id": "TEST-AUDIT-01",
        "tracking_number": "TRK-TEST-AUDIT-01",
        "client_id": "CL-1002",
        "declared_value": 25000.0,
        "claim_amount": 5500.0,
        "delay_cause": "CARRIER_FAULT",
        "notes": "Large machinery damage",
    }
    response = client.post("/api/v1/claims/submit", json=claim_payload)
    assert response.status_code == 201
    order = response.json()
    assert order["claim_status"] == "FLAG_FOR_AUDIT"

def test_reject_weather_delay():
    # Standard client weather delay
    claim_payload = {
        "order_id": "TEST-REJECT-01",
        "tracking_number": "TRK-TEST-REJECT-01",
        "client_id": "CL-1004",
        "declared_value": 8000.0,
        "claim_amount": 1500.0,
        "delay_cause": "WEATHER_FORCE_MAJEURE",
        "notes": "Severe blizzard delay",
    }
    response = client.post("/api/v1/claims/submit", json=claim_payload)
    assert response.status_code == 201
    order = response.json()
    assert order["claim_status"] == "REJECT"

def test_audit_review_override():
    # Override the flagged audit order
    review_payload = {
        "decision": "AUTO_APPROVE",
        "reviewer_notes": "Senior director manual waiver granted after reviewing sensor telematics.",
    }
    response = client.patch("/api/v1/claims/TEST-AUDIT-01/review", json=review_payload)
    assert response.status_code == 200
    order = response.json()
    assert order["claim_status"] == "AUTO_APPROVE"
    assert "Senior director manual waiver" in order["ai_justification"]

def test_metrics_endpoint():
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert metrics["total_claims"] >= 5
    assert "sla_compliance_rate" in metrics

if __name__ == "__main__":
    setup_module(None)
    test_health()
    test_list_clients()
    test_auto_approve_claim()
    test_audit_flag_high_value()
    test_reject_weather_delay()
    test_audit_review_override()
    test_metrics_endpoint()
    print("ALL TESTS PASSED SUCCESSFULLY!")
