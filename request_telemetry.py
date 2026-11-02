"""Safe request logging and latency record construction for API write operations."""
from datetime import datetime, timezone
import math


_CAPTURED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_EXCLUDED_PATHS = frozenset({"/health", "/ready", "/docs", "/redoc", "/openapi.json"})
_EXCLUDED_PREFIXES = ("/stream/",)
_EXCLUDED_READ_MODELS = ("/logs", "/metrics", "/alerts", "/alert-rules", "/tasks")


def should_capture_request(method: str, path: str) -> bool:
    """Capture API calls except health, telemetry reads and long-lived streams."""
    method = method.upper()
    if method in {"OPTIONS", "HEAD"} or path in _EXCLUDED_PATHS:
        return False
    if path.startswith(_EXCLUDED_PREFIXES):
        return False
    if method == "GET" and any(path == prefix or path.startswith(prefix + "/")
                                for prefix in _EXCLUDED_READ_MODELS):
        return False
    return method in _CAPTURED_METHODS or method == "GET"


def build_request_records(method: str, endpoint: str, status_code: int, duration_ms: float,
                          timestamp: datetime | None = None) -> tuple[dict, dict]:
    """Create privacy-safe log + metric payloads from an API request."""
    if isinstance(status_code, bool) or not isinstance(status_code, int) or not 100 <= status_code <= 599:
        raise ValueError("status_code must be an HTTP status in the range 100..599")
    if not math.isfinite(duration_ms) or duration_ms < 0:
        raise ValueError("duration_ms must be finite and non-negative")
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must include a timezone")

    method = method.upper()
    level = "INFO" if status_code < 400 else "WARN" if status_code < 500 else "ERROR"
    tags = {
        "source": "api-instrumentation",
        "method": method,
        "endpoint": endpoint,
        "status_code": status_code,
    }
    timestamp_text = timestamp.astimezone(timezone.utc).isoformat()
    message = f"HTTP {method} {endpoint} completed with status {status_code} in {duration_ms:.3f} ms"
    log_record = {
        "timestamp": timestamp_text,
        "received_at": timestamp_text,
        "service": "observability-api",
        "level": level,
        "message": message,
        "stack_trace": None,
        "tags": tags,
    }
    metric_record = {
        "timestamp": timestamp_text,
        "received_at": timestamp_text,
        "service": "observability-api",
        "name": "response_time",
        "value": float(duration_ms),
        "unit": "ms",
        "tags": tags,
    }
    return log_record, metric_record


