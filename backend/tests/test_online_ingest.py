"""OFFLINE TEST DATA. These fixtures do not establish live source acceptance."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import unittest
import signal
import io
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.app.services.ingest.mtr_mobile import MtrMobileAdapter, plain_text, publication_time
from backend.app.services.ingest.online_http import PublicHttp, SourceFailure
from backend.app.services.ingest.online_models import SourcePage, SourcePost, anonymous_author, filter_reason
from backend.app.services.ingest.online_runner import IngestConfig, IngestRunner
from backend.app.services.ingest.online_store import IngestStore

NOW = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)


def make_test_post(identifier="fixture-1", **kwargs):
    """Explicit synthetic record, never used as real-request evidence."""
    values = dict(platform="mtr_mobile", post_id=identifier,
        text="[TEST DATA] 港鐵東鐵綫紅磡站服務延誤，待確認。",
        url="https://example.invalid/offline-fixture/" + identifier,
        lang="zh-HK", published_at=NOW - timedelta(minutes=5),
        author_hint="test-author-one", source_name="OFFLINE TEST DATA",
        provenance="simulated", original={"test_data": True, "id": identifier})
    values.update(kwargs)
    return SourcePost(**values)


class FakeAdapter:
    name = "mtr_mobile"
    min_interval_seconds = 300

    def __init__(self, posts=(), fail_at=None):
        self.posts, self.fail_at, self.calls = tuple(posts), fail_at, []

    def fetch_page(self, cursor, limit):
        offset = (cursor or {}).get("offset", 0)
        self.calls.append(offset)
        if offset == self.fail_at:
            raise SourceFailure("timeout")
        posts = self.posts[offset:offset + limit]
        end = offset + len(posts)
        return SourcePage(posts, {"offset": end} if end < len(self.posts) else None)


class MappingTests(unittest.TestCase):
    def test_traditional_simplified_english_and_recovery(self):
        for text in ("東鐵紅磡延誤", "香港东铁金钟站停运", "Hong Kong MTR fault",
                     "港鐵東鐵服務恢復正常", "MTR train service resumed"):
            self.assertIsNone(filter_reason(make_test_post(text=text), NOW - timedelta(hours=24), NOW))

    def test_negation_irrelevance_empty_old_future_and_missing_time(self):
        cases = [("香港東鐵沒有延誤", "unrelated_topic"),
                 ("Hong Kong MTR has no delays", "unrelated_topic"),
                 ("London train delay", "unrelated_transport"), ("", "empty_text")]
        for text, reason in cases:
            self.assertEqual(filter_reason(make_test_post(text=text), NOW - timedelta(hours=24), NOW), reason)
        for stamp, reason in ((None, "missing_publication_time"),
                              (NOW - timedelta(hours=25), "outside_window"),
                              (NOW + timedelta(minutes=1), "future_publication_time")):
            self.assertEqual(filter_reason(make_test_post(published_at=stamp), NOW - timedelta(hours=24), NOW), reason)

    def test_real_test_marker_is_rejected_and_keywords_are_configurable(self):
        self.assertEqual(filter_reason(make_test_post(provenance="real"), NOW - timedelta(hours=24), NOW), "test_marker")
        self.assertIsNone(filter_reason(make_test_post(text="港鐵車站運作異常"), NOW - timedelta(hours=24), NOW, ("異常",)))

    def test_signal_contract_identity_author_language_and_collection_time(self):
        post = make_test_post(repost_of=("origin-1",))
        first, second = post.to_signal(NOW), post.to_signal(NOW + timedelta(hours=1))
        self.assertEqual(first.signal_id, second.signal_id)
        self.assertEqual(first.received_at, NOW)
        self.assertNotEqual(first.received_at, post.published_at)
        self.assertEqual(first.source_type, "social")
        self.assertEqual(first.provenance, "simulated")
        self.assertEqual(first.lang, "zh-HK")
        self.assertEqual(first.author_hint, post.author_hint)
        self.assertEqual(first.raw_url, post.url)
        self.assertNotIn("published_at", first.model_dump())
        official = replace(post, official=True, provenance="real").to_signal(NOW)
        self.assertEqual((official.source_type, official.provenance), ("official", "real"))
        self.assertNotEqual(replace(post, text=post.text + "恢復服務").to_signal(NOW).signal_id, first.signal_id)

    def test_anonymous_author_stable_and_platform_scoped(self):
        secret = "offline-test-secret" * 3
        value = anonymous_author("threads", "private-author-1", secret)
        self.assertEqual(value, anonymous_author("threads", "private-author-1", secret))
        self.assertNotIn("private-author", value)
        self.assertNotEqual(value, anonymous_author("facebook", "private-author-1", secret))
        self.assertIsNone(anonymous_author("threads", None, secret))
        with self.assertRaises(ValueError):
            anonymous_author("threads", "a", "short")

    def test_html_preserves_text_and_removes_executable_markup(self):
        self.assertEqual(plain_text("<p>港鐵&nbsp;延誤</p><script>bad()</script><p>恢復<br>服務</p>"), "港鐵\xa0延誤\n恢復\n服務")

    def test_publication_parser_has_no_refresh_time_fallback(self):
        self.assertIsNone(publication_time(None))
        self.assertEqual(publication_time("2026-10-03 08:00:00"), NOW)
        self.assertEqual(publication_time("2026-10-03T00:00:00Z"), NOW)
        with self.assertRaises(SourceFailure):
            publication_time("unknown source format")


class StoreRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = IngestStore(Path(self.temp.name) / "test.sqlite3")
        self.store.initialize()
        self.now = NOW
        self.config = IngestConfig(enabled=True, offline=False, page_size=2)

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, adapter, config=None, **kwargs):
        return IngestRunner(self.store, config or self.config, {"mtr_mobile": adapter},
                            clock=lambda: self.now, **kwargs)

    def test_pages_max_items_restart_and_dedup(self):
        posts = [make_test_post(str(i)) for i in range(5)]
        config = replace(self.config, max_items=3)
        adapter = FakeAdapter(posts)
        first = self.runner(adapter, config).cycle()[0]
        self.assertEqual(first["counts"]["added"], 3)
        self.assertEqual(first["cursor"], {"offset": 3})
        self.assertEqual(adapter.calls, [0, 2])
        self.now += timedelta(seconds=301)
        restarted = IngestStore(self.store.db_path)
        restarted.initialize()
        result = IngestRunner(restarted, config, {"mtr_mobile": FakeAdapter(posts)}, clock=lambda: self.now).cycle()[0]
        self.assertEqual(result["counts"]["added"], 2)
        self.assertIsNone(result["cursor"])
        self.now += timedelta(seconds=301)
        repeat = self.runner(FakeAdapter(posts), replace(self.config, max_items=10)).cycle()[0]
        self.assertEqual(repeat["counts"]["duplicate"], 5)
        self.assertEqual(len(restarted.list_signals()), 5)

    def test_three_cycles_incremental_and_one_source_failure_isolated(self):
        config = replace(self.config, sources=("mtr_mobile", "threads"))
        for round_number in range(1, 4):
            results = self.runner(FakeAdapter([make_test_post(str(i)) for i in range(round_number)]), config).cycle()
            statuses = {x["source"]: x["status"] for x in results}
            self.assertEqual(statuses, {"mtr_mobile": "success", "threads": "blocked"})
            self.assertEqual(results[0]["counts"]["added"], 1)
            self.now += timedelta(seconds=301)
        self.assertEqual(len(self.store.list_signals()), 3)
        self.assertEqual(self.store.state("mtr_mobile")["completed_rounds"], 3)

    def test_failed_second_page_resumes_without_loss(self):
        posts = [make_test_post(str(i)) for i in range(4)]
        result = self.runner(FakeAdapter(posts, fail_at=2)).cycle()[0]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["cursor"], {"offset": 2})
        self.assertEqual(len(self.store.list_signals()), 2)
        self.now += timedelta(seconds=601)
        result = self.runner(FakeAdapter(posts)).cycle()[0]
        self.assertEqual(result["counts"]["added"], 2)
        self.assertEqual(len(self.store.list_signals()), 4)

    def test_atomic_rollback_never_advances_cursor(self):
        insert = self.store._insert_signal
        calls = []
        def fail_second(db, post, payload_json=None):
            calls.append(post.signal_id)
            if len(calls) == 2:
                raise sqlite3.OperationalError("OFFLINE TEST failure")
            insert(db, post, payload_json)
        with patch.object(self.store, "_insert_signal", side_effect=fail_second):
            result = self.runner(FakeAdapter([make_test_post("a"), make_test_post("b"), make_test_post("c")])).cycle()[0]
        self.assertEqual(result["status"], "error")
        self.assertIsNone(self.store.state("mtr_mobile")["cursor"])
        self.assertEqual(self.store.list_signals(), [])
        self.assertEqual(self.store.records("mtr_mobile"), [])

    def test_network_failure_does_not_block_another_adapter(self):
        # Temporary approved-source registry only for OFFLINE TEST DATA.
        config = replace(self.config, sources=("mtr_mobile", "facebook"))
        facebook = FakeAdapter([replace(make_test_post(), platform="facebook")])
        with patch.dict("backend.app.services.ingest.online_runner.BLOCKED", {}, clear=True):
            results = IngestRunner(self.store, config,
                {"mtr_mobile": FakeAdapter(fail_at=0), "facebook": facebook}, clock=lambda: self.now).cycle()
        self.assertEqual([x["status"] for x in results], ["error", "success"])
        self.assertEqual(self.store.state("facebook")["counts"]["added"], 1)

    def test_429_source_backoff_survives_restart(self):
        class Limited(FakeAdapter):
            def fetch_page(self, cursor, limit):
                raise SourceFailure("rate_limited", retry_after=1200)
        result = self.runner(Limited()).cycle()[0]
        self.assertEqual(result["next_attempt"], NOW.timestamp() + 1200)
        self.now += timedelta(seconds=1000)
        self.assertEqual(self.runner(FakeAdapter()).cycle()[0]["status"], "waiting")

    def test_revisions_keep_one_author_and_existing_confidence_identity(self):
        from backend.app.services.confidence import ConfidenceObservation, score_confidence
        post = make_test_post()
        first = post.to_signal(NOW)
        revised = replace(post, text=post.text + "恢復服務").to_signal(NOW)
        result = score_confidence([ConfidenceObservation(first), ConfidenceObservation(revised)])
        self.assertEqual(result.independent_agreeing_sources, 1)

    def test_skipped_publication_time_and_repost_record_are_internal(self):
        result = self.runner(FakeAdapter([make_test_post(published_at=None, repost_of=("origin",))])).cycle()[0]
        self.assertEqual(result["counts"]["skipped"], {"missing_publication_time": 1})
        self.assertEqual(self.store.list_signals(), [])
        record = self.store.records("mtr_mobile")[0]
        self.assertIsNone(record["published_at"])
        self.assertEqual(json.loads(record["repost_json"]), ["origin"])

    def test_later_publication_metadata_can_promote_skipped_record(self):
        self.runner(FakeAdapter([make_test_post(published_at=None)])).cycle()
        self.now += timedelta(seconds=301)
        self.runner(FakeAdapter([make_test_post()])).cycle()
        record = self.store.records("mtr_mobile")[0]
        self.assertEqual(record["disposition"], "accepted")
        self.assertEqual(record["signal_id"], self.store.list_signals()[0].signal_id)
        self.assertIsNotNone(record["published_at"])
        # A later out-of-window poll cannot downgrade stored accepted evidence.
        self.now += timedelta(hours=25)
        self.runner(FakeAdapter([make_test_post()])).cycle()
        self.assertEqual(self.store.records("mtr_mobile")[0]["disposition"], "accepted")

    def test_empty_results_cadence_and_restart_backoff(self):
        adapter = FakeAdapter()
        self.assertEqual(self.runner(adapter).cycle()[0]["status"], "success")
        self.assertEqual(self.runner(adapter).cycle()[0]["status"], "waiting")
        self.assertEqual(len(adapter.calls), 1)
        self.now += timedelta(seconds=301)
        self.assertEqual(self.runner(FakeAdapter(fail_at=0)).cycle()[0]["status"], "error")
        self.assertEqual(self.runner(FakeAdapter()).cycle()[0]["status"], "waiting")

    def test_offline_disabled_and_stop_never_fetch(self):
        for config, expected in ((replace(self.config, offline=True), "offline"),
                                 (replace(self.config, enabled=False), "disabled")):
            adapter = FakeAdapter()
            self.assertEqual(self.runner(adapter, config).cycle()[0]["status"], expected)
            self.assertEqual(adapter.calls, [])
        stop = threading.Event()
        stop.set()
        adapter = FakeAdapter()
        self.assertEqual(self.runner(adapter, stop=stop).cycle()[0]["status"], "stopped")
        self.assertEqual(adapter.calls, [])

    def test_stop_after_request_prevents_writes(self):
        stop = threading.Event()
        class StopAfterFetch(FakeAdapter):
            def fetch_page(self, cursor, limit):
                stop.set()
                return super().fetch_page(cursor, limit)
        result = self.runner(StopAfterFetch([make_test_post()]), stop=stop).cycle()[0]
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(self.store.list_signals(), [])

    def test_lease_exclusion_expiry_and_old_owner_cannot_write(self):
        owner = self.store.acquire("mtr_mobile", NOW.timestamp())
        self.assertEqual(self.runner(FakeAdapter()).cycle()[0]["status"], "busy")
        replacement = self.store.acquire("mtr_mobile", NOW.timestamp() + 181)
        self.assertIsNotNone(replacement)
        with self.assertRaises(RuntimeError):
            self.store.save_state("mtr_mobile", owner, {}, NOW.timestamp() + 181)
        self.store.release("mtr_mobile", owner)
        self.assertIsNone(self.store.acquire("mtr_mobile", NOW.timestamp() + 182))

    def test_pagination_stall_and_oversize_fail_safely(self):
        class Stalled(FakeAdapter):
            def fetch_page(self, cursor, limit):
                return SourcePage((make_test_post(),), {"fixed": 1})
        result = self.runner(Stalled()).cycle()[0]
        self.assertEqual(result["error"], "pagination_stalled")
        self.assertEqual(len(self.store.list_signals()), 1)

    def test_invalid_config(self):
        for changes in ({"interval": 299}, {"sources": ("unknown",)}, {"max_items": 0}, {"page_size": 101}):
            with self.assertRaises(ValueError):
                replace(self.config, **changes)


class TransportAdapterTests(unittest.TestCase):
    def make_http(self, handler, **kwargs):
        client = PublicHttp(transport=httpx.MockTransport(handler), **kwargs)
        self.addCleanup(client.close)
        return client

    def test_429_persists_retry_after_without_immediate_retries(self):
        calls = []
        def response(request):
            calls.append(request)
            return httpx.Response(429, headers={"Retry-After": "1200"})
        with self.assertRaises(SourceFailure) as context:
            self.make_http(response).get("https://www.mtr.com.hk/alert/alert.json")
        self.assertEqual(context.exception.retry_after, 1200)
        self.assertEqual(len(calls), 1)

    def test_5xx_timeout_credentials_and_safe_error_messages(self):
        for kind, expected, count in (("500", "server_error", 3), ("timeout", "timeout", 3),
                                       ("401", "access_denied", 1), ("403", "access_denied", 1),
                                       ("302", "unexpected_http_status", 1)):
            calls = []
            def response(request):
                calls.append(request)
                if kind == "timeout":
                    raise httpx.ReadTimeout("secret-token upstream-message", request=request)
                return httpx.Response(int(kind), text="secret-token upstream-message")
            http = self.make_http(response)
            with patch.object(http.stop, "wait", return_value=False):
                with self.assertRaises(SourceFailure) as context:
                    http.get("https://www.mtr.com.hk/alert/alert.json")
            self.assertEqual(str(context.exception), expected)
            self.assertNotIn("secret", str(context.exception))
            self.assertEqual(len(calls), count)

    def test_endpoint_allowlist_and_response_limit(self):
        http = self.make_http(lambda r: httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1)))
        for url in ("http://www.mtr.com.hk/alert/alert.json", "https://example.com/", "https://www.mtr.com.hk/private"):
            with self.assertRaises(SourceFailure):
                http.get(url)
        with self.assertRaises(SourceFailure) as context:
            http.get("https://www.mtr.com.hk/alert/alert.json")
        self.assertEqual(str(context.exception), "response_too_large")

    def mtr_adapter(self, rows=None, robots="User-agent: *\nDisallow:\n", bad=False):
        self.requests = []
        rows = rows if rows is not None else [{"id": "OFFLINE_TEST_1", "alertTitleTc": "[TEST DATA] 東鐵延誤",
            "alertContentTc": "<p>紅磡站服務恢復</p>", "issuedTime": None, "resumptionReferIds": ["TEST_OLD"]}]
        def handler(request):
            self.requests.append(request.url.path)
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=robots)
            if request.url.path.endswith("ryg_line_status.json"):
                return httpx.Response(200, json={"ryg_status": {"lastBuildDate": "2026-10-03 08:00:00",
                    "refreshInterval": 180000, "line": [{"line_code": "EAL", "status": "green"}]}})
            return httpx.Response(200, text="<html>login</html>") if bad else httpx.Response(200, json={"data": rows})
        return MtrMobileAdapter(self.make_http(handler))

    def test_mtr_live_shape_id_links_null_time_and_official_identity(self):
        page = self.mtr_adapter().fetch_page(None, 25)
        post = page.posts[0]
        self.assertIsNone(post.published_at)
        self.assertEqual(post.post_id, "OFFLINE_TEST_1")
        self.assertTrue(post.url.endswith("#OFFLINE_TEST_1"))
        self.assertTrue(post.official)
        self.assertEqual(post.author_hint, "official-mtr-corporation")
        self.assertEqual(post.repost_of, ("TEST_OLD",))
        self.assertEqual(page.diagnostics["line_status"], {"EAL": "green"})
        self.assertEqual(page.diagnostics["publication_time_policy"], "skip_missing")
        self.assertEqual(len(self.requests), 3)

    def test_mtr_local_pages_and_changed_snapshot_on_restart(self):
        row = {"id": "TEST_1", "alertTitleTc": "[TEST DATA] 東鐵延誤", "alertContentTc": "<p>服務暫停</p>", "issuedTime": None}
        adapter = self.mtr_adapter([row, {**row, "id": "TEST_2"}])
        first = adapter.fetch_page(None, 1)
        self.assertIsNotNone(first.next_cursor)
        second = adapter.fetch_page(first.next_cursor, 1)
        self.assertEqual(second.posts[0].post_id, "TEST_2")
        self.assertEqual(len(self.requests), 3)
        restarted = self.mtr_adapter([{**row, "id": "TEST_NEW"}])
        self.assertEqual(restarted.fetch_page(first.next_cursor, 1).posts[0].post_id, "TEST_NEW")

    def test_mtr_format_change_and_robots_denial(self):
        for adapter, expected in ((self.mtr_adapter(bad=True), "source_format_changed"),
                                  (self.mtr_adapter(rows=[{"id": "TEST_MALFORMED"}]), "source_format_changed"),
                                  (self.mtr_adapter(robots="User-agent: *\nDisallow: /alert/\n"), "robots_disallowed")):
            with self.assertRaises(SourceFailure) as context:
                adapter.fetch_page(None, 10)
            self.assertEqual(str(context.exception), expected)


class ReviewIntegrationTests(unittest.TestCase):
    setUp = StoreRunnerTests.setUp
    tearDown = StoreRunnerTests.tearDown
    runner = StoreRunnerTests.runner
    # Reuse the same isolated SQLite setup; no online event writes.
    def test_collection_visible_to_reviewer_but_does_not_publish_or_replan(self):
        from backend.app.main import create_app
        from backend.app.services.event_store import EventStore
        event_store = EventStore(self.store.db_path)
        event_store.initialize()
        seed = json.loads((Path(__file__).resolve().parents[2] / "contracts/seed/event.seed.json").read_text(encoding="utf-8"))
        events = seed if isinstance(seed, list) else seed.get("events", [])
        # Preserve existing public facts; fixture seeds remain explicitly simulated.
        for event in events:
            event["expires_at"] = "2027-01-01T00:00:00+08:00"
            event["window"].update(start="2026-10-03T00:00:00+08:00", end="2027-01-01T00:00:00+08:00")
            event_store.create_event(event)
        app = create_app(db_path=self.store.db_path, review_token="OFFLINE-TEST-REVIEWER")
        with patch.dict(os.environ, {"OFFLINE_MODE": "true", "AI_ENABLED": "false"}):
            with TestClient(app) as client:
                before = client.get("/api/events/published").json()
                self.assertTrue(before)
                snapshot = client.get("/api/graph/snapshot").json()
                route_body = {"origin": "TAW", "destination": "ADM", "depart_at": "2026-10-03T08:00:00+08:00"}
                before_route = client.post("/api/routes/query", json=route_body)
                result = self.runner(FakeAdapter([make_test_post()])).cycle()[0]
                self.assertEqual(result["counts"]["added"], 1)
                queue = client.get("/api/signals?unlinked_only=true", headers={"x-review-token": "OFFLINE-TEST-REVIEWER"})
                self.assertEqual(queue.status_code, 200)
                self.assertIn(self.store.list_signals()[0].signal_id, [x["signal_id"] for x in queue.json()])
                self.assertEqual(client.get("/api/events/published").json(), before)
                self.assertEqual(client.get("/api/graph/snapshot").json(), snapshot)
                after_route = client.post("/api/routes/query", json=route_body)
                self.assertEqual(after_route.status_code, before_route.status_code)
                self.assertEqual(after_route.json(), before_route.json())
                self.assertEqual(before_route.status_code, 200)
                self.assertIn(client.get("/api/signals").status_code, (401, 403, 503))


class CliTests(unittest.TestCase):
    def test_sigint_requests_drain_closes_http_and_restores_handler(self):
        from backend.app.services.ingest import online_cli
        with tempfile.TemporaryDirectory() as temp:
            before = signal.getsignal(signal.SIGINT)
            output = io.StringIO()
            def build_runner(store, config, adapters, *, stop):
                class Runner:
                    def cycle(self):
                        signal.raise_signal(signal.SIGINT)
                        return [{"source": "mtr_mobile", "status": "success"}]
                return Runner()
            with patch.dict(os.environ, {"DB_PATH": str(Path(temp)/"cli.sqlite3"),
                "INGEST_ENABLED": "true", "OFFLINE_MODE": "true", "INGEST_SOURCES": "mtr_mobile"}):
                with patch.object(online_cli, "IngestRunner", side_effect=build_runner), \
                     patch.object(online_cli, "PublicHttp") as http, redirect_stdout(output):
                    self.assertEqual(online_cli.main(["poll"]), 0)
                    http.return_value.close.assert_called_once()
            self.assertEqual(signal.getsignal(signal.SIGINT), before)
            stopped = json.loads(output.getvalue().splitlines()[-1])
            self.assertEqual(stopped, {"type": "stopped", "cycles": 1, "requested": True})

    @unittest.skipUnless(hasattr(signal, "SIGBREAK"), "Windows console signal only")
    def test_sigbreak_requests_stop_and_restores_handler(self):
        from backend.app.services.ingest import online_cli

        with tempfile.TemporaryDirectory() as temp:
            before = signal.getsignal(signal.SIGBREAK)
            output = io.StringIO()

            def build_runner(store, config, adapters, *, stop):
                class Runner:
                    def cycle(self):
                        signal.raise_signal(signal.SIGBREAK)
                        return [{"source": "mtr_mobile", "status": "success"}]
                return Runner()

            with patch.dict(os.environ, {"DB_PATH": str(Path(temp) / "cli.sqlite3"),
                "INGEST_ENABLED": "true", "OFFLINE_MODE": "true", "INGEST_SOURCES": "mtr_mobile"}):
                with patch.object(online_cli, "IngestRunner", side_effect=build_runner), \
                     patch.object(online_cli, "PublicHttp") as http, redirect_stdout(output):
                    self.assertEqual(online_cli.main(["poll"]), 0)
                    http.return_value.close.assert_called_once()
            self.assertEqual(signal.getsignal(signal.SIGBREAK), before)
            stopped = json.loads(output.getvalue().splitlines()[-1])
            self.assertEqual(stopped, {"type": "stopped", "cycles": 1, "requested": True})


if __name__ == "__main__":
    unittest.main()
