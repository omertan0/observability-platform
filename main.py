from fastapi import FastAPI
from models import LogInput
from models import LogInput, MetricInput
from datetime import datetime, timezone
from tasks import process_log, process_metric
from dotenv import load_dotenv
from database import get_connection
from psycopg.rows import dict_row

load_dotenv()

app = FastAPI(title="Observability Platform")


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/logs", status_code=202)
def receive_log(log: LogInput):
    record = log.model_dump(mode="json")
    record["received_at"] = datetime.now(timezone.utc).isoformat()

    task = process_log.delay(record)

    return {
        "status": "queued",
        "task_id": task.id
    }

@app.post("/metrics", status_code=202)
def receive_metric(metric: MetricInput):
    record = metric.model_dump(mode="json")
    record["received_at"] = datetime.now(timezone.utc).isoformat()

    task = process_metric.delay(record)

    return {
        "status": "queued",
        "task_id": task.id
    }

@app.get("/logs")
def list_logs():
    with get_connection() as conn:
        conn.row_factory = dict_row

        records = conn.execute(
            """
            SELECT id, timestamp, received_at, service,
            level, message, stack_trace, tags
            FROM logs
            ORDER BY timestamp DESC, id DESC
            LIMIT 20
            """
        ).fetchall()

    return {"items": records}
