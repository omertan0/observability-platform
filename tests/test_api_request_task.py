import unittest
from unittest.mock import patch

from tasks import process_api_request


class FakeResult:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.seen_task = False
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        if "INSERT INTO processed_tasks" in query:
            if self.seen_task:
                return FakeResult(None)
            self.seen_task = True
            return FakeResult({"task_id": params[0]})
        return FakeResult(None)

    def cursor(self, **_):
        return FakeCursor()


class ApiRequestTaskTests(unittest.TestCase):
    def setUp(self):
        self.log = {
            "timestamp": "2026-11-02T00:00:00+00:00", "received_at": "2026-11-02T00:00:00+00:00", "service": "observability-api",
            "level": "INFO", "message": "HTTP POST /logs completed with status 202 in 3 ms",
            "stack_trace": None, "tags": {"source": "api-instrumentation"},
        }
        self.metric = {
            "timestamp": "2026-11-02T00:00:00+00:00", "received_at": "2026-11-02T00:00:00+00:00", "service": "observability-api",
            "name": "response_time", "value": 3.0, "unit": "ms",
            "tags": {"source": "api-instrumentation"},
        }

    def test_log_metric_are_written_together_and_duplicate_task_is_ignored(self):
        conn = FakeConnection()
        task_id = "edb83201-ae9f-4f75-8575-a22d7dbbd761"
        with patch("tasks.get_connection", return_value=conn), patch("tasks.load_rules", return_value=[]):
            first = process_api_request.apply(args=[self.log, self.metric], task_id=task_id).get()
            second = process_api_request.apply(args=[self.log, self.metric], task_id=task_id).get()

        self.assertEqual(first, {"status": "saved", "record_count": 2})
        self.assertEqual(second, {"status": "already_processed"})
        statements = [query for query, _ in conn.statements]
        self.assertEqual(sum("INSERT INTO processed_tasks" in query for query in statements), 2)
        self.assertEqual(sum("INSERT INTO logs" in query for query in statements), 1)
        self.assertEqual(sum("INSERT INTO metrics" in query for query in statements), 1)
        task_insert = next((query, params) for query, params in conn.statements if "INSERT INTO processed_tasks" in query)
        self.assertIn("'api_request', 2", task_insert[0])


if __name__ == "__main__":
    unittest.main()

