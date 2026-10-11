"""Yerel worker/DB kesintilerinde gerçek görev kurtarma kontrolleri.

Geçici olarak Docker servislerini durdurur ve bir worker alt sürecini sonlandırır.
Yalnızca geliştirme ortamında çalıştırılır; servisler finally içinde geri açılır.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from celery_app import celery_app
from database import get_connection
from tasks import process_metric


def docker(*args):
    command = ["docker", "compose", *args]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)


def request(method, path, payload=None, params=None):
    if params:
        path += "?" + urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request("http://127.0.0.1:8000" + path, data=data, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def wait_for(check, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError("Kurtarma kontrolünde beklenen sonuç oluşmadı")


def state(task_id):
    code, body = request("GET", "/tasks/" + task_id)
    if code != 200:
        raise AssertionError(body)
    return body["state"]


def main():
    services, task_ids, checks = [], [], []

    def payload():
        service = "qa-recovery-" + uuid4().hex
        services.append(service)
        return dict(timestamp=datetime.now(timezone.utc).isoformat(), service=service,
                    name="cpu_usage", value=70, unit="percent", tags={"test": "recovery"})

    def submit(body):
        code, response = request("POST", "/metrics", body)
        if code != 202:
            raise AssertionError(response)
        task_ids.append(response["task_id"])
        return response["task_id"]

    def verify_saved(body, task_id):
        wait_for(lambda: state(task_id) == "SUCCESS")
        with get_connection() as conn:
            count = conn.execute("SELECT count(*) FROM metrics WHERE service = %s", (body["service"],)).fetchone()[0]
            receipt = conn.execute("SELECT count(*) FROM processed_tasks WHERE task_id = %s", (task_id,)).fetchone()[0]
        if count != 1 or receipt != 1:
            raise AssertionError(f"Tek kayıt bekleniyordu: {count}, {receipt}")
        return {"record_count": count, "receipt_count": receipt, "state": "SUCCESS"}

    try:
        if request("GET", "/ready")[0] != 200:
            raise AssertionError("Servisler hazır değil")

        docker("stop", "worker")
        body = payload()
        task_id = submit(body)
        code, rows = request("GET", "/metrics", params={"service": body["service"]})
        if code != 200 or rows["items"]:
            raise AssertionError("Worker kapalıyken kayıt yazılmamalı")
        docker("up", "-d", "--wait", "worker")
        checks.append({"scenario": "worker_stopped_then_started", "passed": True,
                       **verify_saved(body, task_id)})

        docker("stop", "db")
        body = payload()
        task_id = submit(body)
        wait_for(lambda: state(task_id) == "RETRY", timeout=30)
        docker("up", "-d", "--wait", "db")
        checks.append({"scenario": "database_outage_retry_then_success", "retry_observed": True,
                       "passed": True, **verify_saved(body, task_id)})

        body = payload()
        # Worker'ın INSERT sırasında beklemesini sağlar; sonra tam o çalışan alt süreci kapatılır.
        with get_connection() as barrier:
            barrier.execute("LOCK TABLE metrics IN ACCESS EXCLUSIVE MODE")
            task_id = submit(body)

            def active_pid():
                active = celery_app.control.inspect(timeout=0.5).active() or {}
                for tasks in active.values():
                    for task in tasks:
                        if task["id"] == task_id and task.get("worker_pid"):
                            return int(task["worker_pid"])
                return None

            pid = wait_for(active_pid, timeout=20)
            if pid <= 1:
                raise AssertionError("Worker ana süreci sonlandırılamaz")
            docker("exec", "-T", "worker", "python", "-c",
                   f"import os,signal; os.kill({pid}, signal.SIGKILL)")
        checks.append({"scenario": "worker_child_lost_redelivery", "worker_child_pid": pid,
                       "passed": True, **verify_saved(body, task_id)})

        # API doğrulamasını bilerek atlayan iç test: kalıcı DB hatasının FAILURE olarak görünmesi.
        body = payload()
        body["received_at"] = datetime.now(timezone.utc).isoformat()
        body["value"] = None
        task_id = process_metric.apply_async(args=[body], retry=False).id
        task_ids.append(task_id)
        wait_for(lambda: state(task_id) == "FAILURE")
        with get_connection() as conn:
            count = conn.execute("SELECT count(*) FROM metrics WHERE service = %s", (body["service"],)).fetchone()[0]
        if count:
            raise AssertionError("Başarısız görevin kaydı geri alınmalı")
        checks.append({"scenario": "permanent_failure_visible_and_rolled_back", "passed": True,
                       "record_count": count, "state": "FAILURE"})
    finally:
        docker("up", "-d", "--wait", "worker")
        output = ROOT / "test-results" / "recovery-checks.json"
        report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
                  "successful": len(checks) == 4 and all(check["passed"] for check in checks)}
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["successful"]:
            with get_connection() as conn:
                conn.execute("DELETE FROM alerts WHERE service = ANY(%s)", (services,))
                conn.execute("DELETE FROM alert_states WHERE service = ANY(%s)", (services,))
                conn.execute("DELETE FROM metrics WHERE service = ANY(%s)", (services,))
                conn.execute("DELETE FROM processed_tasks WHERE task_id = ANY(%s::uuid[])", (task_ids,))
            for task_id in task_ids:
                celery_app.AsyncResult(task_id).forget()


if __name__ == "__main__":
    main()
