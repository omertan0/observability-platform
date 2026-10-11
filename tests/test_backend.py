"""Çalışan API, Redis, Celery ve PostgreSQL üzerinde işlevsel kontroller.

Çalıştırma: python -m unittest discover -s tests -v
Testler kendilerine ait servisleri oluşturur ve sonunda yalnızca bu verileri temizler.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from database import get_connection
from tasks import save_record, save_records
from celery_app import celery_app

BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:8000")


def request(method, path, body=None, params=None):
    if params:
        path += "?" + urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = Request(BASE_URL + path, data=data, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def wait_for(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.15)
    raise AssertionError("Worker beklenen sonucu 20 saniye içinde üretmedi")


class BackendChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.services, cls.rule_ids, cls.task_ids = [], [], []
        code, body = request("GET", "/ready")
        if code != 200:
            raise RuntimeError(f"API/Redis/DB hazır değil: {body}")

    @classmethod
    def tearDownClass(cls):
        # Kullanıcının önceki örnekleri ve varsayılan kuralları korunur.
        with get_connection() as conn:
            conn.execute("DELETE FROM alerts WHERE service = ANY(%s)", (cls.services,))
            conn.execute("DELETE FROM alert_states WHERE service = ANY(%s)", (cls.services,))
            conn.execute("DELETE FROM alert_rules WHERE id = ANY(%s)", (cls.rule_ids,))
            conn.execute("DELETE FROM logs WHERE service = ANY(%s)", (cls.services,))
            conn.execute("DELETE FROM metrics WHERE service = ANY(%s)", (cls.services,))
            conn.execute("DELETE FROM processed_tasks WHERE task_id = ANY(%s::uuid[])", (cls.task_ids,))
        for task_id in cls.task_ids:
            celery_app.AsyncResult(task_id).forget()

    def service(self):
        value = "qa-" + uuid4().hex
        self.services.append(value)
        return value

    def metric(self, service, value=90, name="cpu_usage", unit="percent", **extra):
        return dict(timestamp=datetime.now(timezone.utc).isoformat(), service=service,
                    name=name, value=value, unit=unit, tags={"environment": "qa"}, **extra)

    def log(self, service, level="ERROR", message="Database connection timeout"):
        return dict(timestamp=datetime.now(timezone.utc).isoformat(), service=service,
                    level=level, message=message, tags={"environment": "qa"})

    def post(self, kind, body):
        code, response = request("POST", "/" + kind, body)
        self.assertEqual(code, 202, response)
        self.task_ids.append(response["task_id"])
        return response["task_id"]

    def wait_saved(self, task_ids):
        def check():
            with get_connection() as conn:
                count = conn.execute("SELECT count(*) FROM processed_tasks WHERE task_id = ANY(%s::uuid[])",
                                     (task_ids,)).fetchone()[0]
                return count == len(set(task_ids))
        wait_for(check)

    def items(self, path, **params):
        code, body = request("GET", path, params=params)
        self.assertEqual(code, 200, body)
        return body["items"]

    def rule(self, **overrides):
        body = dict(name="QA kural " + uuid4().hex, kind="metric_threshold",
                    metric_name="test_latency", metric_unit="ms", operator="gt", threshold=100)
        body.update(overrides)
        code, result = request("POST", "/alert-rules", body)
        self.assertEqual(code, 201, result)
        self.rule_ids.append(result["id"])
        return result

    def test_01_ingestion_and_filters(self):
        service = self.service()
        task = self.post("logs", self.log(service))
        self.wait_saved([task])
        for params in (
            {"service": service, "level": "ERROR", "q": "timeout"},
            {"service": service, "tags": '{"environment":"qa"}'},
            {"service": service, "start": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()},
        ):
            self.assertEqual(len(self.items("/logs", **params)), 1)
        self.assertEqual(self.items("/logs", service=service, level="INFO"), [])
        self.assertEqual(self.items("/logs", service=service, q="unrelatedword"), [])
        self.assertEqual(self.items("/logs", service=service, tags='{"environment":"other"}'), [])
        # SQL gibi görünen servis adı parametre olarak işlenir, kayıt sızdırmaz.
        self.assertEqual(self.items("/logs", service="' OR 1=1 --"), [])

    def test_02_metric_threshold_boundary_and_cooldown(self):
        service = self.service()
        self.wait_saved([self.post("metrics", self.metric(service, 85))])
        self.assertEqual(self.items("/alerts", service=service), [])
        self.wait_saved([self.post("metrics", self.metric(service, 85.1))])
        self.assertEqual(len(self.items("/alerts", service=service)), 1)
        tasks = [self.post("metrics", self.metric(service, 99)) for _ in range(4)]
        self.wait_saved(tasks)
        self.assertEqual(len(self.items("/alerts", service=service)), 1)
        self.assertEqual(len(self.items("/metrics", service=service, name="cpu_usage", unit="percent")), 6)

    def test_03_default_error_rule_at_51(self):
        service = self.service()
        tasks = [self.post("logs", self.log(service)) for _ in range(50)]
        self.wait_saved(tasks)
        self.assertEqual(self.items("/alerts", service=service), [])
        self.wait_saved([self.post("logs", self.log(service))])
        alerts = self.items("/alerts", service=service)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["observed_value"], 51)
        self.wait_saved([self.post("logs", self.log(service))])
        self.assertEqual(len(self.items("/alerts", service=service)), 1)

    def test_04_unit_and_service_isolation(self):
        service, other = self.service(), self.service()
        self.rule(service=service)
        tasks = [self.post("metrics", self.metric(other, 200, "test_latency", "ms")),
                 self.post("metrics", self.metric(service, 200, "test_latency", "seconds"))]
        self.wait_saved(tasks)
        self.assertEqual(self.items("/alerts", service=service), [])
        self.assertEqual(self.items("/alerts", service=other), [])
        self.wait_saved([self.post("metrics", self.metric(service, 200, "test_latency", "ms"))])
        self.assertEqual(len(self.items("/alerts", service=service)), 1)

    def test_05_disabled_rule_and_update_validation(self):
        service = self.service()
        rule = self.rule(service=service, enabled=False)
        self.wait_saved([self.post("metrics", self.metric(service, 200, "test_latency", "ms"))])
        self.assertEqual(self.items("/alerts", service=service), [])
        code, body = request("PATCH", f"/alert-rules/{rule['id']}", {"enabled": True, "threshold": 150})
        self.assertEqual(code, 200, body)
        self.wait_saved([self.post("metrics", self.metric(service, 200, "test_latency", "ms"))])
        self.assertEqual(len(self.items("/alerts", service=service)), 1)
        self.assertEqual(request("PATCH", f"/alert-rules/{rule['id']}", {"threshold": None})[0], 422)

    def test_06_acknowledgement_is_idempotent(self):
        service = self.service()
        self.wait_saved([self.post("metrics", self.metric(service))])
        alert = self.items("/alerts", service=service)[0]
        code, first = request("PATCH", f"/alerts/{alert['id']}/acknowledge")
        self.assertEqual(code, 200)
        self.assertEqual(first["status"], "acknowledged")
        code, second = request("PATCH", f"/alerts/{alert['id']}/acknowledge")
        self.assertEqual(first["acknowledged_at"], second["acknowledged_at"])
        self.assertEqual(self.items("/alerts", service=service, status="open"), [])

    def test_07_pagination(self):
        service = self.service()
        tasks = [self.post("logs", self.log(service, "INFO", f"sayfa {i}")) for i in range(3)]
        self.wait_saved(tasks)
        code, first = request("GET", "/logs", params={"service": service, "limit": 2})
        self.assertEqual(code, 200)
        self.assertTrue(first["has_more"])
        code, second = request("GET", "/logs", params={"service": service, "limit": 2, "offset": first["next_offset"]})
        self.assertFalse(second["has_more"])
        ids = [row["id"] for row in first["items"] + second["items"]]
        self.assertEqual(len(set(ids)), 3)

    def test_08_validation_and_missing_resources(self):
        service = self.service()
        for change in ({"timestamp": 1}, {"timestamp": "2026-10-11T12:00:00"},
                       {"service": "   "}, {"value": "90"}, {"value": 101},
                       {"tags": {"value": float("inf")}}, {"unknown": True}):
            body = self.metric(service)
            body.update(change)
            self.assertEqual(request("POST", "/metrics", body)[0], 422, change)
        self.assertEqual(request("POST", "/logs", {**self.log(service), "level": "DEBUG"})[0], 422)
        for params in ({"limit": 0}, {"limit": 201}, {"offset": -1},
                       {"tags": "[]"}, {"tags": '{"value": NaN}'}, {"tags": '{"value": 1e999}'},
                       {"start": "2026-10-12T00:00:00Z", "end": "2026-10-11T00:00:00Z"}):
            self.assertEqual(request("GET", "/logs", params=params)[0], 422)
        self.assertEqual(request("PATCH", "/alerts/9223372036854775807/acknowledge")[0], 404)
        self.assertEqual(request("PATCH", "/alert-rules/9223372036854775807", {"enabled": False})[0], 404)

    def test_09_duplicate_task_and_atomic_rollback(self):
        service = self.service()
        record = self.metric(service)
        record["received_at"] = datetime.now(timezone.utc).isoformat()
        task_id = str(uuid4())
        self.task_ids.append(task_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: save_record("metric", record, task_id), range(2)))
        self.assertEqual(len(self.items("/metrics", service=service)), 1)
        self.assertEqual(len(self.items("/alerts", service=service)), 1)

        failed_id = str(uuid4())
        self.task_ids.append(failed_id)
        with patch("tasks.evaluate_alerts", side_effect=RuntimeError("test rollback")):
            with self.assertRaises(RuntimeError):
                save_record("metric", record, failed_id)
        self.assertEqual(len(self.items("/metrics", service=service)), 1)
        with get_connection() as conn:
            self.assertIsNone(conn.execute("SELECT task_id FROM processed_tasks WHERE task_id = %s", (failed_id,)).fetchone())

    def test_10_log_window_expired_and_level_isolation(self):
        service = self.service()
        self.rule(service=service, kind="log_count", level="ERROR", threshold=1,
                  window_seconds=60, metric_name=None, metric_unit=None)
        old = self.log(service)
        old["received_at"] = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        task_id = str(uuid4())
        self.task_ids.append(task_id)
        save_record("log", old, task_id)
        self.wait_saved([self.post("logs", self.log(service, "INFO")),
                         self.post("logs", self.log(service))])
        self.assertEqual(self.items("/alerts", service=service), [])
        self.wait_saved([self.post("logs", self.log(service))])
        self.assertEqual(len(self.items("/alerts", service=service)), 1)

    def test_11_cooldown_expires_and_comparison_operators(self):
        service = self.service()
        rule = self.rule(service=service, operator="lte", threshold=100, cooldown_seconds=300)
        self.wait_saved([self.post("metrics", self.metric(service, 100, "test_latency", "ms"))])
        self.assertEqual(len(self.items("/alerts", service=service)), 1)
        with get_connection() as conn:
            conn.execute("UPDATE alert_states SET last_triggered_at = clock_timestamp() - interval '301 seconds' WHERE rule_id = %s AND service = %s",
                         (rule["id"], service))
        self.wait_saved([self.post("metrics", self.metric(service, 50, "test_latency", "ms"))])
        self.assertEqual(len(self.items("/alerts", service=service)), 2)

    def test_12_duplicate_rule_and_invalid_configuration(self):
        rule = self.rule(service=self.service())
        body = {key: rule[key] for key in ("name", "kind", "service", "metric_name", "metric_unit", "operator", "threshold")}
        self.assertEqual(request("POST", "/alert-rules", body)[0], 409)
        self.assertEqual(request("POST", "/alert-rules", {**body, "metric_unit": None})[0], 422)
        self.assertEqual(request("POST", "/alert-rules", {**body, "kind": "log_count", "metric_name": None,
                                                          "metric_unit": None, "level": "ERROR", "threshold": 1.5})[0], 422)

    def test_13_batch_multiple_alerts_and_duplicate_delivery(self):
        service, other = self.service(), self.service()
        rule = self.rule(service=service, metric_name="cpu_usage", metric_unit="percent",
                         threshold=85, cooldown_seconds=0)
        body = [self.metric(service, 90), self.metric(service, 95), self.metric(other, 90)]
        task_id = self.post("metrics/batch", body)
        self.wait_saved([task_id])
        self.assertEqual(len(self.items("/metrics", service=service)), 2)
        self.assertEqual(len(self.items("/alerts", service=service, rule_id=rule["id"])), 2)
        self.assertEqual(len(self.items("/alerts", service=other)), 1)
        # Aynı batch görevi tekrar teslim edilirse hiçbir satır tekrar yazılmaz.
        received_at = datetime.now(timezone.utc).isoformat()
        records = [{**item, "received_at": received_at} for item in body]
        save_records("metric", records, task_id)
        self.assertEqual(len(self.items("/metrics", service=service)), 2)
        status = wait_for(lambda: request("GET", f"/tasks/{task_id}")[1] if
                          request("GET", f"/tasks/{task_id}")[1]["state"] == "SUCCESS" else None)
        self.assertTrue(status["successful"])

    def test_14_batch_error_threshold_and_atomic_rollback(self):
        service = self.service()
        task_id = self.post("logs/batch", [self.log(service) for _ in range(51)])
        self.wait_saved([task_id])
        alerts = self.items("/alerts", service=service)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["observed_value"], 51)
        self.assertEqual(alerts[0]["source_record_index"], 50)
        another = self.service()
        records = [{**self.metric(another), "received_at": datetime.now(timezone.utc).isoformat()} for _ in range(2)]
        failed_id = str(uuid4())
        self.task_ids.append(failed_id)
        with patch("tasks.evaluate_alerts", side_effect=[None, RuntimeError("batch rollback")]):
            with self.assertRaises(RuntimeError):
                save_records("metric", records, failed_id)
        self.assertEqual(self.items("/metrics", service=another), [])

    def test_15_batch_validation_and_task_uuid(self):
        body = self.metric(self.service())
        for batch in ([], [body] * 101, [body, {**body, "value": "bad"}]):
            self.assertEqual(request("POST", "/metrics/batch", batch)[0], 422)
        self.assertEqual(request("GET", "/tasks/not-a-uuid")[0], 422)

    def test_16_pooled_connections_reset_row_format(self):
        from psycopg.rows import dict_row
        with get_connection() as conn:
            conn.row_factory = dict_row
            self.assertEqual(conn.execute("SELECT 1 AS value").fetchone()["value"], 1)
        with get_connection() as conn:
            self.assertEqual(conn.execute("SELECT 1").fetchone(), (1,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
