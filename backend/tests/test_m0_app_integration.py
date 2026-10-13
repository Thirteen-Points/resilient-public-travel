from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.app.main import create_app, runtime


def test_b_signal_intake_and_c_wheelchair_route_share_the_integrated_app():
    assert runtime.engine is not None, runtime.error
    root = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix=".m0-signal-test-", dir=root) as temp_dir:
        app = create_app(db_path=Path(temp_dir) / "integration.sqlite3")
        with TestClient(app) as client:
            health = client.get("/api/health")
            assert health.status_code == 200
            assert health.json()["components"]["signals"] == "ready"

            submitted = client.post(
                "/api/signals",
                json={"raw_text": "M0 integration test signal", "lang": "en"},
            )
            assert submitted.status_code == 202
            assert submitted.json()["signal_id"]

            routes = client.post(
                "/api/routes/query",
                json={
                    "origin": "TAW",
                    "destination": "ADM",
                    "depart_at": "2026-09-22T08:20:00+08:00",
                    "profile": {"mobility": "wheelchair"},
                },
            )
            assert routes.status_code == 200
            result = routes.json()
            assert result
            assert all(
                leg["accessible"] and leg["mode"] != "MINIBUS"
                for route in result
                for leg in route["legs"]
            )
            assert all(
                any("MTR and buses are assumed usable" in warning for warning in route["warnings"])
                for route in result
            )
