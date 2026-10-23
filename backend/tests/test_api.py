import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    init_db()

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database_ok" in data
    assert data["database_ok"] is True

def test_load_demo_project(client: TestClient):
    resp = client.post("/api/demo/load")
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "demo" in data["source_type"]
    assert len(data["dependencies"]) >= 4

    project_id = data["id"]

    # Verify project can be queried
    get_resp = client.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 200
    p_data = get_resp.json()
    assert p_data["name"] == data["name"]

def test_scan_lifecycle_and_report(client: TestClient):
    # 1. Load demo project
    demo_resp = client.post("/api/demo/load")
    assert demo_resp.status_code == 201
    project_id = demo_resp.json()["id"]

    # 2. Start scan
    scan_resp = client.post(f"/api/projects/{project_id}/scans")
    assert scan_resp.status_code == 202
    scan_id = scan_resp.json()["scan_id"]

    # 3. Poll scan status
    status_resp = client.get(f"/api/scans/{scan_id}")
    assert status_resp.status_code == 200
    s_data = status_resp.json()
    assert s_data["scan_id"] == scan_id
    assert s_data["status"] in ("pending", "parsing", "scanning_code", "fetching_releases", "fetching_advisories", "indexing", "retrieving", "analyzing", "completed")

    # 4. In synchronous test execution, let's execute the scan worker directly or verify report
    from app.services.scan_service import run_project_scan
    from app.db import get_db
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT local_path FROM projects WHERE id = ?;", (project_id,))
        local_path = cursor.fetchone()["local_path"]

    run_project_scan(scan_id, project_id, local_path)

    # 5. Check report
    report_resp = client.get(f"/api/scans/{scan_id}/report")
    assert report_resp.status_code == 200
    rep_data = report_resp.json()
    assert rep_data["scan_id"] == scan_id
    assert rep_data["status"] == "completed"
    assert "findings" in rep_data
    assert len(rep_data["findings"]) >= 1

    # Check finding details, evidence, and explainability
    first_finding = rep_data["findings"][0]
    fid = first_finding["id"]

    ev_resp = client.get(f"/api/findings/{fid}/evidence")
    assert ev_resp.status_code == 200
    assert ev_resp.json()["finding_id"] == fid

    ex_resp = client.get(f"/api/findings/{fid}/explain")
    assert ex_resp.status_code == 200
    assert "retrieval_scores" in ex_resp.json()

    # 6. Test Ask Q&A
    ask_resp = client.post(f"/api/projects/{project_id}/ask", json={"question": "Does Pydantic affect our service?"})
    assert ask_resp.status_code == 200
    assert "answer" in ask_resp.json()

    # 7. Test Markdown and JSON exports
    md_resp = client.get(f"/api/scans/{scan_id}/export/markdown")
    assert md_resp.status_code == 200
    assert "# StackSignal Impact Analysis Report" in md_resp.text

    json_resp = client.get(f"/api/scans/{scan_id}/export/json")
    assert json_resp.status_code == 200
    assert json_resp.json()["scan_id"] == scan_id
