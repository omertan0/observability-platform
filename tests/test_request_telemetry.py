import unittest
from datetime import datetime, timezone

from request_telemetry import build_request_records, should_capture_request


class RequestTelemetryTests(unittest.TestCase):
    def test_captures_write_routes_and_excludes_health_read_and_stream_routes(self):
        self.assertTrue(should_capture_request("POST", "/logs"))
        self.assertTrue(should_capture_request("PATCH", "/alert-rules/3"))
        self.assertTrue(should_capture_request("GET", "/auth/session"))
        for method, path in [
            ("GET", "/logs"), ("GET", "/metrics"), ("GET", "/alerts"),
            ("GET", "/health"), ("GET", "/ready"), ("GET", "/stream/metrics"),
            ("GET", "/docs"), ("POST", "/health"), ("OPTIONS", "/logs"),
        ]:
            with self.subTest(method=method, path=path):
                self.assertFalse(should_capture_request(method, path))

    def test_builds_safe_log_and_duration_metric_without_request_secrets(self):
        timestamp = datetime(2026, 11, 2, tzinfo=timezone.utc)
        log, metric = build_request_records("POST", "/logs", 202, 12.345, timestamp)
        self.assertEqual(log["service"], "observability-api")
        self.assertEqual(log["level"], "INFO")
        self.assertEqual(log["timestamp"], timestamp.isoformat())
        self.assertEqual(log["stack_trace"], None)
        self.assertEqual(log["tags"], {
            "source": "api-instrumentation", "method": "POST", "endpoint": "/logs", "status_code": 202,
        })
        self.assertIn("12.345 ms", log["message"])
        self.assertEqual(metric["name"], "response_time")
        self.assertEqual(metric["unit"], "ms")
        self.assertEqual(metric["value"], 12.345)
        self.assertEqual(metric["service"], "observability-api")
        self.assertEqual(metric["tags"], log["tags"])
        self.assertNotIn("token", log["message"].lower())

    def test_http_error_levels_and_route_template_only(self):
        log, metric = build_request_records("POST", "/logs/{log_id}", 503, 4.0)
        self.assertEqual(log["level"], "ERROR")
        self.assertEqual(metric["tags"]["endpoint"], "/logs/{log_id}")
        warning, _ = build_request_records("POST", "/auth/login", 401, 3.0)
        self.assertEqual(warning["level"], "WARN")

    def test_rejects_invalid_durations_and_status_codes(self):
        for duration, status in [(-1, 200), (float("nan"), 200), (1, 99), (1, 600)]:
            with self.subTest(duration=duration, status=status):
                with self.assertRaises(ValueError):
                    build_request_records("POST", "/logs", status, duration)


if __name__ == "__main__":
    unittest.main()
