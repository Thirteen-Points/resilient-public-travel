"""B collector contract: durable evidence, review gate and source isolation."""

import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.sources import router as sources_router
from backend.app.services.ingest.collection import SourceCollectionService
from backend.app.services.ingest.hko import HkoFetchError, HkoWarningPoller
from backend.app.services.ingest.mtr_eta import MtrEtaAnomalyPoller


AT = datetime(2026, 10, 6, 0, 20, tzinfo=timezone.utc)


class HkoClientStub:
    def __init__(self, fail_first=False):
        self.fail_first = fail_first
        self.calls = 0

    def fetch_warnsum(self):
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise HkoFetchError("timeout")
        return {"WTS": {"code": "WTS", "name": "雷暴警告", "actionCode": "ISSUE",
                        "updateTime": "2026-10-06T08:00:00+08:00"}}

    def fetch_warning_info(self):
        return {"details": []}

    def endpoint_url(self, kind):
        return "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=" + kind


class MtrClientStub:
    def __init__(self, abnormal=False):
        self.abnormal = abnormal
        self.calls = 0

    def fetch_station(self, code):
        self.calls += 1
        ttnt = 12 if self.abnormal and code in {"TAW", "KOT"} else 2
        return {"status": 1, "isdelay": "N", "curr_time": "2026-10-06 08:20:00",
                "data": {"EAL-" + code: {"UP": [{"ttnt": str(ttnt), "valid": "Y"}], "DOWN": []}}}


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "events.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def build(self, hko=None, mtr=None, **kwargs):
        return SourceCollectionService(self.db, enabled=True, offline_mode=False,
            pollers={"hko": HkoWarningPoller(hko or HkoClientStub()),
                     "mtr": MtrEtaAnomalyPoller(mtr or MtrClientStub())},
            sleeper=lambda _seconds: None, **kwargs)

    def test_hko_signal_draft_and_restart_are_durable(self):
        service = self.build()
        self.assertEqual(service.run_once("hko", at=AT), 1)
        signal = service.signals.list_signals()[0]
        self.assertEqual(signal.provenance, "real")
        queue = service.store.review_queue()
        self.assertEqual(queue[0]["state"], "pending_review")
        self.assertIsNotNone(queue[0]["draft"])
        self.assertEqual(service.events.list_events(), [])
        self.assertEqual(service.run_once("hko", at=AT), 0)
        restarted = self.build()
        self.assertEqual(restarted.run_once("hko", at=AT), 0)
        self.assertEqual(len(restarted.signals.list_signals()), 1)
        status = restarted.status()[0]
        self.assertEqual(status["result"], "no_new_signals")
        self.assertEqual(status["source_time"], "2026-10-06T08:00:00+08:00")

    def test_failure_retry_and_source_isolation(self):
        hko = HkoClientStub(fail_first=True)
        service = self.build(hko=hko)
        self.assertEqual(service.run_once("hko", at=AT), 1)
        self.assertEqual(hko.calls, 2)
        self.assertEqual(service.run_once("mtr", at=AT), 0)
        self.assertIsNone(service.status()[1]["last_error"])

    def test_exhausted_hko_error_is_stale_and_mtr_still_runs(self):
        class DownHko(HkoClientStub):
            def fetch_warnsum(self):
                self.calls += 1
                raise HkoFetchError("timeout")

        down = DownHko()
        service = self.build(hko=down)
        self.assertEqual(service.run_once("hko", at=AT), 0)
        self.assertEqual(down.calls, 3)
        hko_status = service.status()[0]
        self.assertTrue(hko_status["stale"])
        self.assertIn("timeout", hko_status["last_error"])
        self.assertIsNone(hko_status["last_success"])
        self.assertEqual(service.run_once("mtr", at=AT), 0)
        self.assertIsNone(service.status()[1]["last_error"])

    def test_mtr_continuity_and_simulated_replay(self):
        service = self.build(mtr=MtrClientStub(abnormal=True), simulated=True)
        self.assertEqual(service.run_once("mtr", at=AT), 0)
        self.assertEqual(service.run_once("mtr", at=AT), 1)
        self.assertEqual(service.signals.list_signals()[0].provenance, "simulated")
        restarted = self.build(mtr=MtrClientStub(abnormal=True), simulated=True)
        self.assertEqual(restarted.run_once("mtr", at=AT), 0)
        self.assertEqual(len(restarted.signals.list_signals()), 1)
        self.assertEqual(restarted.status()[1]["provenance"], "simulated")

    def test_offline_does_not_touch_network(self):
        client = HkoClientStub()
        service = SourceCollectionService(self.db, enabled=True, offline_mode=True,
            pollers={"hko": HkoWarningPoller(client), "mtr": MtrEtaAnomalyPoller(MtrClientStub())})
        self.assertFalse(service.start())
        self.assertEqual(service.run_once("hko", at=AT), 0)
        self.assertEqual(client.calls, 0)

    def test_start_and_stop_both_source_loops(self):
        touched = threading.Event()

        class ObservedHko(HkoClientStub):
            def fetch_warnsum(self):
                touched.set()
                return super().fetch_warnsum()

        service = self.build(hko=ObservedHko())
        self.assertTrue(service.start())
        self.assertTrue(touched.wait(2))
        service.stop()
        self.assertEqual(service._threads, {})

    def test_failed_write_does_not_lose_observation(self):
        service = self.build()
        service.initialize()
        original = service.store.save_poll
        service.store.save_poll = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk unavailable"))
        with self.assertRaises(OSError):
            service.run_once("hko", at=AT)
        service.store.save_poll = original
        self.assertEqual(service.run_once("hko", at=AT), 1)

    def test_status_is_public_and_queue_requires_reviewer(self):
        service = self.build()
        service.run_once("hko", at=AT)
        app = FastAPI()
        app.state.source_collection = service
        app.state.review_token = "test-reviewer"
        app.include_router(sources_router)
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/sources/status").status_code, 200)
            self.assertEqual(client.get("/api/sources/review-queue").status_code, 401)
            response = client.get("/api/sources/review-queue", headers={"X-Review-Token": "test-reviewer"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["state"], "pending_review")


if __name__ == "__main__":
    unittest.main()
