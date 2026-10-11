"""Yerel Docker servislerini kısa süre durdurup 503 yanıtlarını kontrol eder.

Servisler finally bloğunda yeniden açılır. Bu betiği canlı ortamda çalıştırmayın.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"


def docker(*args):
    result = subprocess.run(["docker", "compose", *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)


def request(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(BASE_URL + path, data=data, method=method, headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urlopen(req, timeout=20) as response:
            code, body = response.status, json.load(response)
    except HTTPError as exc:
        code, body = exc.code, json.load(exc)
    return code, body, round(time.monotonic() - started, 2)


if request("GET", "/ready")[0] != 200:
    raise RuntimeError("Testten önce API/Redis/DB hazır olmalıdır")

checks = []
for service in ("redis", "db"):
    try:
        docker("stop", service)
        if service == "redis":
            code, body, duration = request("POST", "/metrics", {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "outage-check", "name": "cpu_usage", "value": 90, "unit": "percent", "tags": {},
            })
        else:
            code, body, duration = request("GET", "/metrics")
        readiness_code = request("GET", "/ready")[0]
        checks.append({"service": service, "http_status": code, "readiness_status": readiness_code,
                       "response_seconds": duration, "detail": body,
                       "passed": code == 503 and readiness_code == 503})
        print(f"{service} kapalı: HTTP {code}; {duration}s")
    finally:
        docker("up", "-d", "--wait", service)

restored = request("GET", "/ready")[0] == 200
output = ROOT / "test-results" / "outage-checks.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps({"checked_at_utc": datetime.now(timezone.utc).isoformat(),
                              "checks": checks, "services_restored": restored},
                             ensure_ascii=False, indent=2), encoding="utf-8")
sys.exit(0 if restored and all(check["passed"] for check in checks) else 1)
