"""HTTP interface and CSV export smoke tests."""
import csv

from fastapi.testclient import TestClient

from agents.api import app
from cli import main


client = TestClient(app)


def test_home_serves_functional_browser_entry():
    html = client.get("/")
    assert html.status_code == 200
    assert "MELD 3.0" in html.text
    assert 'src="./calculator.js"' in html.text
    js = client.get("/calculator.js")
    assert js.status_code == 200
    assert "function calculate" in js.text


def test_api_calculation_and_invalid_inputs():
    values = {
        "bilirubin": 2.5, "inr": 1.8, "creatinine": 1.5,
        "sodium": 135, "albumin": 3.2, "female": False,
    }
    response = client.post("/api/calculate", json=values)
    assert response.status_code == 200
    assert response.json()["meld_3"] == 22
    assert response.json()["meld_na"] == 21
    assert client.post(
        "/api/calculate", json={**values, "sodium": -4}
    ).status_code == 422
    assert client.get("/health").status_code == 200


def test_audit_endpoint_rejects_obvious_identifier():
    response = client.post("/api/audit", json={
        "task_id": "MRN-991100",
        "target_identifier": "KEY-TEST",
        "primary_metric": 9,
    })
    assert response.status_code == 400


def test_batch_missing_lab_is_error_not_imputed(tmp_path):
    source = tmp_path / "input.csv"
    result = tmp_path / "output.csv"
    with source.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["patient_id", "bilirubin", "creatinine", "inr", "sodium"])
        writer.writerow(["=HYPERLINK(1)", "2.5", "", "1.8", "135"])
    assert main(["batch", "--input", str(source), "--output", str(result)]) == 0
    with result.open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["meld"] == "ERROR"
    assert "Missing required" in row["priority"]
    assert row["patient_id"].startswith("'=")
