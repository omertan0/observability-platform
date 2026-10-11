"""Faz 2 yerel ölçümü: veri alım hızı ve kuyruğun boşalma süresi.

Örnek: python scripts/load_backend.py --records 1000 --concurrency 8 --batch-size 1 --label baseline
Yalnızca bu denemenin benzersiz servisine ait kayıtlar sonunda temizlenir.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from threading import Event, Thread
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from database import get_connection
from redis import Redis
from celery_app import celery_app


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    return round(values[min(len(values) - 1, int((len(values) - 1) * fraction))] * 1000, 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--label", default="phase2")
    parser.add_argument("--log-level", choices=("INFO", "ERROR"), default="INFO")
    parser.add_argument("--metric-value", type=float, default=70)
    args = parser.parse_args()
    if not 1 <= args.records <= 10000 or not 1 <= args.concurrency <= 32 or not 1 <= args.batch_size <= 100:
        parser.error("records 1-10000, concurrency 1-32 ve batch-size 1-100 olmalıdır")
    if not 0 <= args.metric_value <= 100:
        parser.error("metric-value 0-100 arasında olmalıdır")
    service = "qa-load-" + uuid4().hex
    task_ids, latencies, errors = [], [], []
    stop = Event()
    queue_samples = []
    client = Redis.from_url(celery_app.conf.broker_url, socket_timeout=2)

    def monitor():
        while not stop.is_set():
            queue_samples.append(client.llen("celery"))
            stop.wait(0.1)

    def send(job):
        kind, records = job
        path = "/" + kind + ("/batch" if args.batch_size > 1 else "")
        payload = records if args.batch_size > 1 else records[0]
        req = Request("http://127.0.0.1:8000" + path, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
        began = time.perf_counter()
        try:
            with urlopen(req, timeout=30) as response:
                body = json.load(response)
                if response.status != 202:
                    return None, time.perf_counter() - began, len(records), str(response.status)
                return body["task_id"], time.perf_counter() - began, len(records), None
        except HTTPError as exc:
            return None, time.perf_counter() - began, len(records), f"HTTP {exc.code}"
        except OSError as exc:
            return None, time.perf_counter() - began, len(records), type(exc).__name__

    now = datetime.now(timezone.utc).isoformat()
    logs, metrics = [], []
    for i in range(args.records):
        common = dict(timestamp=now, service=service, tags={"test": "phase2-load", "sequence": i})
        if i % 2 == 0:
            logs.append(dict(**common, level=args.log_level, message=f"Yuk denemesi {i}"))
        else:
            metrics.append(dict(**common, name="cpu_usage", value=args.metric_value, unit="percent"))
    jobs = []
    for kind, records in (("logs", logs), ("metrics", metrics)):
        jobs.extend((kind, records[i:i + args.batch_size]) for i in range(0, len(records), args.batch_size))
    monitor_thread = Thread(target=monitor, daemon=True)
    monitor_thread.start()
    started = time.perf_counter()
    accepted = 0
    saved = 0
    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            for task_id, latency, record_count, error in executor.map(send, jobs):
                latencies.append(latency)
                if error:
                    errors.append(error)
                else:
                    task_ids.append(task_id)
                    accepted += record_count
        accepted_at = time.perf_counter()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            with get_connection() as conn:
                saved = conn.execute(
                    "SELECT (SELECT count(*) FROM logs WHERE service = %s) + (SELECT count(*) FROM metrics WHERE service = %s)",
                    (service, service),
                ).fetchone()[0]
            if saved >= accepted:
                break
            time.sleep(0.1)
        finished = time.perf_counter()
        with get_connection() as conn:
            alert_count = conn.execute("SELECT count(*) FROM alerts WHERE service = %s", (service,)).fetchone()[0]
        report = {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "label": args.label, "requested_records": args.records, "accepted_records": accepted,
            "saved_records": saved, "http_requests": len(jobs), "http_errors": errors,
            "concurrency": args.concurrency, "batch_size": args.batch_size,
            "acceptance_seconds": round(accepted_at - started, 3),
            "total_seconds": round(finished - started, 3),
            "records_per_second": round(saved / (finished - started), 2),
            "http_p50_ms": percentile(latencies, 0.5), "http_p95_ms": percentile(latencies, 0.95),
            "queue_peak_samples": max(queue_samples, default=0),
            "alert_count": alert_count,
            "successful": not errors and saved == accepted == args.records,
            "workload": f"Half {args.log_level} logs, half cpu_usage/percent={args.metric_value:g} metrics; local machine, single run.",
        }
        output = ROOT / "test-results" / ("load-" + args.label + ".json")
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["successful"] else 1
    finally:
        stop.set()
        monitor_thread.join(timeout=3)
        client.close()
        # Başarısız ölçümde bekleyen işler varsa inceleme için verileri korur.
        if saved == accepted:
            with get_connection() as conn:
                conn.execute("DELETE FROM alerts WHERE service = %s", (service,))
                conn.execute("DELETE FROM alert_states WHERE service = %s", (service,))
                conn.execute("DELETE FROM logs WHERE service = %s", (service,))
                conn.execute("DELETE FROM metrics WHERE service = %s", (service,))
                conn.execute("DELETE FROM processed_tasks WHERE task_id = ANY(%s::uuid[])", (task_ids,))
            with Redis.from_url(celery_app.conf.result_backend) as results:
                keys = [celery_app.backend.get_key_for_task(task_id) for task_id in task_ids]
                if keys:
                    results.delete(*keys)


if __name__ == "__main__":
    sys.exit(main())
