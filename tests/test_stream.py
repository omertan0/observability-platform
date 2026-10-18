"""SSE protokolü, commit sonrası bildirim ve bağlantı toparlama kontrolleri.

API/Redis/worker/DB açıkken ve başka veri üretimi yokken çalıştırılır.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import AsyncMock, patch
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from uuid import uuid4

from test_backend import BASE_URL, request
from celery_app import celery_app
from database import get_connection
from psycopg import OperationalError
from streams import log_events, logs_revision
from tasks import insert_record


def next_event(response):
    fields = {}
    while True:
        line = response.readline()
        if not line:
            raise AssertionError("SSE bağlantısı beklenmedik biçimde kapandı")
        line = line.decode("utf-8").rstrip("\r\n")
        if not line:
            if "event" in fields:
                fields["data"] = json.loads(fields["data"])
                return fields
            fields = {}
        elif not line.startswith(":"):
            key, _, value = line.partition(":")
            fields[key] = value.lstrip()


class StreamChecks(unittest.TestCase):
    def setUp(self):
        self.service = "qa-stream-" + uuid4().hex
        self.task_ids = []

    def tearDown(self):
        with get_connection() as conn:
            conn.execute("DELETE FROM alerts WHERE service = %s", (self.service,))
            conn.execute("DELETE FROM alert_states WHERE service = %s", (self.service,))
            conn.execute("DELETE FROM logs WHERE service = %s", (self.service,))
            if self.task_ids:
                conn.execute("DELETE FROM processed_tasks WHERE task_id = ANY(%s::uuid[])", (self.task_ids,))
        for task_id in self.task_ids:
            celery_app.AsyncResult(task_id).forget()

    def body(self):
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "service": self.service,
                "level": "INFO", "message": "SSE kontrol kaydı", "tags": {"test": "stream"}}

    def connect(self, revision=None, params=None):
        headers = {"Accept": "text/event-stream"}
        if revision:
            headers["Last-Event-ID"] = revision
        query = "?" + urlencode(params) if params else ""
        return urlopen(Request(BASE_URL + "/stream/logs" + query, headers=headers), timeout=12)

    def test_01_headers_and_initial_snapshot(self):
        with self.connect() as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(response.headers["Content-Type"].startswith("text/event-stream"))
            self.assertEqual(response.headers["Cache-Control"], "no-cache")
            self.assertEqual(response.readline().strip(), b"retry: 3000")
            event = next_event(response)
            self.assertEqual(event["event"], "logs_changed")
            self.assertEqual(len(event["id"]), 64)
            self.assertEqual(event["data"]["revision"], event["id"])

    def test_02_uncommitted_row_hidden_and_reconnect_resync(self):
        with self.connect() as response, ThreadPoolExecutor(max_workers=1) as executor:
            initial = next_event(response)
            with get_connection() as conn:
                body = {**self.body(), "received_at": datetime.now(timezone.utc).isoformat()}
                insert_record(conn, "log", body)
                pending = executor.submit(next_event, response)
                # En az bir 2 saniyelik DB kontrolü geçer; commit öncesi olay oluşmamalı.
                with self.assertRaises(TimeoutError):
                    pending.result(timeout=2.6)
            committed = pending.result(timeout=8)
            self.assertEqual(committed["event"], "logs_changed")
            self.assertNotEqual(committed["id"], initial["id"])
        with self.connect(committed["id"]) as response:
            replay = next_event(response)
            self.assertEqual(replay["id"], committed["id"])

    def test_03_api_queue_commit_and_notification(self):
        with self.connect() as response:
            initial = next_event(response)
            code, result = request("POST", "/logs", self.body())
            self.assertEqual(code, 202)
            self.task_ids.append(result["task_id"])
            changed = next_event(response)
            self.assertEqual(changed["event"], "logs_changed")
            self.assertNotEqual(changed["id"], initial["id"])
            code, saved = request("GET", "/logs", params={"service": self.service})
            self.assertEqual(code, 200)
            self.assertEqual(len(saved["items"]), 1)
            self.assertEqual(saved["items"][0]["message"], "SSE kontrol kaydı")

    def test_06_filtered_stream_outside_global_window_and_pagination(self):
        now = datetime.now(timezone.utc)
        with get_connection() as conn:
            for _ in range(23):
                insert_record(conn, "log", {**self.body(), "level": "WARN", "message": "background",
                                             "timestamp": now.isoformat(), "received_at": now.isoformat()})
            insert_record(conn, "log", {**self.body(), "message": "needle first",
                                         "timestamp": (now - timedelta(hours=1)).isoformat(), "received_at": now.isoformat()})
        params = {"service": self.service, "level": "INFO", "q": "needle", "tags": '{"test":"stream"}',
                  "start": (now - timedelta(hours=2)).isoformat(), "end": (now + timedelta(hours=1)).isoformat()}
        with self.connect(params=params) as response, ThreadPoolExecutor(max_workers=1) as executor:
            initial = next_event(response)
            pending = executor.submit(next_event, response)
            # Yanlış seviyedeki yeni kayıt filtreli akışı değiştirmemeli.
            with get_connection() as conn:
                insert_record(conn, "log", {**self.body(), "level": "WARN", "message": "needle excluded",
                                             "timestamp": (now + timedelta(seconds=1)).isoformat(), "received_at": now.isoformat()})
            with self.assertRaises(TimeoutError):
                pending.result(timeout=2.6)
            global_before = logs_revision()
            with get_connection() as conn:
                insert_record(conn, "log", {**self.body(), "message": "needle second",
                                             "timestamp": (now - timedelta(minutes=10)).isoformat(), "received_at": now.isoformat()})
            self.assertEqual(logs_revision(), global_before)
            changed = pending.result(timeout=8)
            self.assertNotEqual(changed["id"], initial["id"])
        code, filtered = request("GET", "/logs", params=params)
        self.assertEqual(code, 200)
        self.assertEqual([row["message"] for row in filtered["items"]], ["needle second", "needle first"])
        _, first_page = request("GET", "/logs", params={"service": self.service, "limit": 20})
        _, second_page = request("GET", "/logs", params={"service": self.service, "limit": 20, "offset": first_page["next_offset"]})
        self.assertEqual(len(first_page["items"]), 20)
        self.assertEqual(len(second_page["items"]), 6)
        self.assertFalse(second_page["has_more"])
        self.assertFalse({row["id"] for row in first_page["items"]} & {row["id"] for row in second_page["items"]})

    def test_07_twenty_first_row_updates_next_page_flag(self):
        now = datetime.now(timezone.utc)
        with get_connection() as conn:
            for _ in range(20):
                insert_record(conn, "log", {**self.body(), "timestamp": now.isoformat(), "received_at": now.isoformat()})
        _, before = request("GET", "/logs", params={"service": self.service})
        self.assertFalse(before["has_more"])
        with self.connect(params={"service": self.service}) as response:
            initial = next_event(response)
            with get_connection() as conn:
                insert_record(conn, "log", {**self.body(), "timestamp": (now - timedelta(hours=1)).isoformat(),
                                             "received_at": now.isoformat()})
            changed = next_event(response)
            self.assertNotEqual(changed["id"], initial["id"])
        _, after = request("GET", "/logs", params={"service": self.service})
        self.assertEqual(before["items"], after["items"])
        self.assertTrue(after["has_more"])

    def test_08_stream_filter_validation_before_headers(self):
        for params in ({"level": "TRACE"}, {"q": " "}, {"tags": "[]"},
                       {"start": "2026-10-18T15:00:00Z", "end": "2026-10-18T14:00:00Z"},
                       {"start": "2026-10-18T14:00:00"}):
            with self.subTest(params=params):
                self.assertEqual(request("GET", "/stream/logs", params=params)[0], 422)


class StreamRecoveryChecks(unittest.IsolatedAsyncioTestCase):
    async def test_04_database_error_recovers_without_duplicate_events(self):
        fake_request = type("Request", (), {"is_disconnected": AsyncMock(return_value=False)})()
        with patch("streams.POLL_SECONDS", 0), patch("streams.HEARTBEAT_SECONDS", 3600), \
                patch("streams.logs_revision", side_effect=[OperationalError("test"), "a", "a", "b"]):
            generator = log_events(fake_request)
            try:
                self.assertIn("retry: 3000", await anext(generator))
                self.assertIn("event: stream_status", await anext(generator))
                self.assertIn('"revision": "a"', await anext(generator))
                self.assertIn('"revision": "b"', await anext(generator))
            finally:
                await generator.aclose()

    async def test_05_disconnect_stops_database_checks(self):
        fake_request = type("Request", (), {"is_disconnected": AsyncMock(return_value=True)})()
        with patch("streams.logs_revision") as revision:
            generator = log_events(fake_request)
            await anext(generator)
            with self.assertRaises(StopAsyncIteration):
                await anext(generator)
            revision.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
