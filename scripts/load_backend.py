"""Yerel yük ölçümü: veri kabulü, kalıcı kayıt ve worker bitişi ayrı izlenir.

Örnek: python scripts/load_backend.py --records 1000 --concurrency 8 --batch-size 1 --label baseline
Yalnızca bu denemenin benzersiz servisine ait kayıtlar sonunda temizlenir.
"""
import argparse
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import sys
from threading import Event, Thread
import time
from urllib.error import HTTPError
from urllib.request import Request
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from database import get_connection
from redis import Redis
from celery_app import celery_app
from client_access import ingestion_headers, no_redirect_open as urlopen


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    return round(values[max(0, math.ceil(len(values) * fraction) - 1)] * 1000, 2)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--label", default="phase4")
    parser.add_argument("--log-level", choices=("INFO", "ERROR"), default="INFO")
    parser.add_argument("--metric-value", type=float, default=70)
    parser.add_argument("--rate", type=float, default=0, help="Hedef kayıt/saniye; 0 beklemeden gönderir")
    parser.add_argument("--wait-timeout", type=float, default=120)
    args = parser.parse_args(argv)
    if not 1 <= args.records <= 100000 or not 1 <= args.concurrency <= 32 or not 1 <= args.batch_size <= 100:
        parser.error("records 1-100000, concurrency 1-32 ve batch-size 1-100 olmalıdır")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", args.label):
        parser.error("label yalnızca harf, sayı, tire ve alt çizgi içerebilir; en fazla 80 karakterdir")
    if not math.isfinite(args.rate) or (args.rate != 0 and not 1 <= args.rate <= 100000):
        parser.error("rate 0 veya 1-100000 arasında sonlu bir sayı olmalıdır")
    if not math.isfinite(args.wait_timeout) or not 1 <= args.wait_timeout <= 600:
        parser.error("wait-timeout 1-600 arasında olmalıdır")
    if not 0 <= args.metric_value <= 100:
        parser.error("metric-value 0-100 arasında olmalıdır")
    return args


def run_jobs(jobs, send, concurrency, rate, clock=time.perf_counter, sleep=time.sleep):
    """En fazla concurrency kadar istek bekler; hız kayıt sayısına göre ayarlanır."""
    pending = set()
    submitted_records = 0
    started = clock()
    failed = False
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for job in jobs:
            if len(pending) >= concurrency:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    result = future.result()
                    failed = failed or result[-1] is not None
                    yield result
                if failed:
                    break
            if rate:
                sleep(max(0, started + submitted_records / rate - clock()))
            pending.add(executor.submit(send, job))
            submitted_records += len(job[1])
        for future in as_completed(pending):
            yield future.result()


def cleanup_test_data(service, task_ids):
    if not re.fullmatch(r"qa-load-[0-9a-f]{32}", service):
        raise ValueError("Yalnızca bu aracın test servisi temizlenebilir")
    for task_id in task_ids:
        UUID(task_id)
    with get_connection() as conn:
        conn.execute("DELETE FROM alerts WHERE service = %s", (service,))
        conn.execute("DELETE FROM alert_states WHERE service = %s", (service,))
        conn.execute("DELETE FROM logs WHERE service = %s", (service,))
        conn.execute("DELETE FROM metrics WHERE service = %s", (service,))
        conn.execute("DELETE FROM processed_tasks WHERE task_id = ANY(%s::uuid[])", (task_ids,))
    with Redis.from_url(celery_app.conf.result_backend, socket_timeout=5) as results:
        for offset in range(0, len(task_ids), 500):
            keys = [celery_app.backend.get_key_for_task(task_id) for task_id in task_ids[offset:offset + 500]]
            if keys:
                results.delete(*keys)


def main(argv=None):
    args = parse_args(argv)
    service = "qa-load-" + uuid4().hex
    task_ids, latencies, errors = [], [], []
    stop = Event()
    queue_samples = deque(maxlen=7200)
    queue_peak = None
    monitor_errors = []
    client = Redis.from_url(celery_app.conf.broker_url, socket_connect_timeout=2, socket_timeout=2)

    try:
        with urlopen(Request("http://127.0.0.1:8000/ready", headers=ingestion_headers()), timeout=10) as response:
            if response.status != 200 or json.load(response).get("status") != "ready":
                raise RuntimeError("API hazır değil")
        client.ping()
        with get_connection() as conn:
            conn.execute("SELECT 1")
        if not celery_app.control.ping(timeout=2):
            raise RuntimeError("Worker yanıt vermiyor")
    except Exception as exc:
        client.close()
        print(f"Ön kontrol başarısız: {type(exc).__name__}. API, Docker ve worker durumunu kontrol et.", file=sys.stderr)
        return 1

    def monitor():
        nonlocal queue_peak
        while not stop.is_set():
            try:
                length = client.llen("celery")
                queue_peak = max(queue_peak or 0, length)
                queue_samples.append({"seconds": round(time.perf_counter() - started, 3), "waiting_tasks": length})
            except Exception as exc:
                monitor_errors.append(type(exc).__name__)
                return
            stop.wait(0.5)

    def send(job):
        kind, records = job
        path = "/" + kind + ("/batch" if args.batch_size > 1 else "")
        payload = records if args.batch_size > 1 else records[0]
        req = Request("http://127.0.0.1:8000" + path, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json", **ingestion_headers()}, method="POST")
        began = time.perf_counter()
        try:
            with urlopen(req, timeout=30) as response:
                body = json.load(response)
                if response.status != 202 or body.get("status") != "queued":
                    raise ValueError("Kabul yanıtı geçersiz")
                if args.batch_size > 1 and body.get("record_count") != len(records):
                    raise ValueError("Kayıt sayısı geçersiz")
                task_id = str(UUID(body["task_id"]))
                return task_id, time.perf_counter() - began, len(records), None
        except HTTPError as exc:
            with exc:
                return None, time.perf_counter() - began, len(records), f"HTTP {exc.code}"
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            return None, time.perf_counter() - began, len(records), type(exc).__name__

    now = datetime.now(timezone.utc).isoformat()
    logs, metrics = [], []
    for i in range(args.records):
        common = dict(timestamp=now, service=service, tags={"test": "phase4-load", "sequence": i})
        if i % 2 == 0:
            logs.append(dict(**common, level=args.log_level, message=f"Yuk denemesi {i}"))
        else:
            metrics.append(dict(**common, name="cpu_usage", value=args.metric_value, unit="percent"))
    jobs = []
    for offset in range(0, max(len(logs), len(metrics)), args.batch_size):
        for kind, records in (("logs", logs), ("metrics", metrics)):
            batch = records[offset:offset + args.batch_size]
            if batch:
                jobs.append((kind, batch))
    monitor_thread = Thread(target=monitor, daemon=True)
    started = time.perf_counter()
    monitor_thread.start()
    accepted = 0
    saved = 0
    attempted = http_requests = 0
    database_at = None
    receipts = receipt_records = saved_logs = saved_metrics = 0
    states = {}
    cleanup_safe = False
    data_cleaned = False
    cleanup_error = None
    output = ROOT / "test-results" / ("load-" + args.label + ".json")
    output.parent.mkdir(exist_ok=True)
    print(f"Yük denemesi: {args.label}; {args.records} kayıt; {args.concurrency} gönderici; paket {args.batch_size}", flush=True)
    try:
        for task_id, latency, record_count, error in run_jobs(jobs, send, args.concurrency, args.rate):
            attempted += record_count
            http_requests += 1
            if error:
                errors.append(error)
            else:
                latencies.append(latency)
                task_ids.append(task_id)
                accepted += record_count
        accepted_at = time.perf_counter()
        deadline = time.monotonic() + args.wait_timeout
        pending_ids = set(task_ids)
        while time.monotonic() < deadline:
            with get_connection() as conn:
                saved_logs, saved_metrics, receipts, receipt_records = conn.execute(
                    "SELECT (SELECT count(*) FROM logs WHERE service = %s), "
                    "(SELECT count(*) FROM metrics WHERE service = %s), "
                    "(SELECT count(*) FROM processed_tasks WHERE task_id = ANY(%s::uuid[])), "
                    "(SELECT COALESCE(sum(record_count), 0) FROM processed_tasks WHERE task_id = ANY(%s::uuid[]))",
                    (service, service, task_ids, task_ids),
                ).fetchone()
            saved = saved_logs + saved_metrics
            if saved == accepted and receipts == len(task_ids) and receipt_records == accepted:
                if database_at is None:
                    database_at = time.perf_counter()
                for task_id in list(pending_ids):
                    state = celery_app.AsyncResult(task_id).state
                    states[task_id] = state
                    if state in ("SUCCESS", "FAILURE"):
                        pending_ids.remove(task_id)
                if not pending_ids:
                    break
            time.sleep(0.2)
        for task_id in pending_ids:
            states[task_id] = celery_app.AsyncResult(task_id).state
        finished = time.perf_counter()
        state_counts = Counter(states.values())
        with get_connection() as conn:
            alert_count = conn.execute("SELECT count(*) FROM alerts WHERE service = %s", (service,)).fetchone()[0]
        report = {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "label": args.label, "requested_records": args.records, "accepted_records": accepted,
            "service": service, "saved_records": saved, "saved_logs": saved_logs, "saved_metrics": saved_metrics,
            "processed_tasks": receipts, "receipt_records": int(receipt_records), "task_states": dict(state_counts),
            "attempted_records": attempted, "not_attempted_records": args.records - attempted,
            "http_requests": http_requests, "http_errors": errors,
            "http_error_rate_percent": round(len(errors) / http_requests * 100, 3) if http_requests else None,
            "concurrency": args.concurrency, "batch_size": args.batch_size,
            "acceptance_seconds": round(accepted_at - started, 3),
            "target_records_per_second": args.rate or None,
            "total_seconds": round(database_at - started, 3) if database_at is not None else None,
            "queue_drain_seconds": round(database_at - accepted_at, 3) if database_at is not None else None,
            "worker_confirmed_seconds": round(finished - started, 3),
            "records_per_second": round(saved / (database_at - started), 2) if database_at is not None else None,
            "http_p50_ms": percentile(latencies, 0.5), "http_p95_ms": percentile(latencies, 0.95),
            "http_p99_ms": percentile(latencies, 0.99),
            "queue_peak_samples": queue_peak, "queue_samples": list(queue_samples), "queue_monitor_errors": monitor_errors,
            "queue_scope": "Tüm yerel celery kuyruğundaki bekleyen görevler; çalışan görevler dahil değil.",
            "alert_count": alert_count,
            "successful": not errors and not monitor_errors and saved == accepted == args.records
                and saved_logs == len(logs) and saved_metrics == len(metrics)
                and receipts == len(task_ids) and receipt_records == accepted
                and state_counts["SUCCESS"] == len(task_ids) and len(task_ids) > 0,
            "environment": {"platform": platform.platform(), "python": platform.python_version(), "logical_cpus": os.cpu_count()},
            "timing_note": "Ön hazırlık ve temizlik hariç. DB bitişi gönderim sonrası kontrol edilir. HTTP yüzdelikleri başarılı kabul yanıtlarına aittir; nearest-rank kullanılır.",
            "workload": f"Half {args.log_level} logs, half cpu_usage/percent={args.metric_value:g} metrics; local machine, single run.",
        }
        cleanup_safe = report["successful"]
        # JSON dosyası finally sonrasında temizlik bilgisiyle birlikte yazılır.
    except (Exception, KeyboardInterrupt) as exc:
        report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "label": args.label,
                  "service": service, "requested_records": args.records, "accepted_records": accepted,
                  "saved_records": saved, "http_errors": errors, "task_states": states,
                  "task_ids": task_ids, "counts_are_partial": True, "successful": False,
                  "run_error": type(exc).__name__}
    finally:
        stop.set()
        monitor_thread.join(timeout=4)
        client.close()
        # Başarısız ölçümde bekleyen işler varsa inceleme için verileri korur.
        if monitor_errors:
            report["successful"] = False
        if cleanup_safe and not monitor_errors:
            try:
                cleanup_test_data(service, task_ids)
                data_cleaned = True
            except Exception as exc:
                cleanup_error = type(exc).__name__

    report["data_cleaned"] = data_cleaned
    report["cleanup_error"] = cleanup_error
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "queue_samples"}, indent=2, ensure_ascii=False), flush=True)
    return 0 if report["successful"] and data_cleaned else 1


if __name__ == "__main__":
    sys.exit(main())
