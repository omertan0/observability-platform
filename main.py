from fastapi import FastAPI
from models import LogInput
from models import LogInput, MetricInput
from datetime import datetime, timezone

app = FastAPI(title="Observability Platform")


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/logs")  #Bu adrese gönderilen POST isteklerini karşılar.
def receive_log(log: LogInput): #Gönderilen JSON, LogInput kurallarına göre kontrol edilir. Hatalıysa FastAPI otomatik olarak 422 döndürür.
    record = log.model_dump(mode="json")
    record["received_at"] = datetime.now(timezone.utc).isoformat()
    return {
        "status": "validated",
        "log": record #Alınma zamanı eklenen kaydı cevapta gösterir.
    }

@app.post("/metrics")
def receive_metric(metric: MetricInput):
    record = metric.model_dump(mode="json")
    record["received_at"] = datetime.now(timezone.utc).isoformat()

    return {
        "status": "validated",
        "metric": record
    }
