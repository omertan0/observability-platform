from fastapi import FastAPI
from models import LogInput
from models import LogInput, MetricInput
from datetime import datetime, timezone
from tasks import process_log, process_metric

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
