from datetime import datetime, timezone
import logging
from typing import Annotated, Literal
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path, Query, Request, Body
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from kombu.exceptions import OperationalError as BrokerError
from psycopg import OperationalError
from psycopg.errors import UniqueViolation, QueryCanceled, LockNotAvailable, UndefinedTable
from psycopg.rows import dict_row
from pydantic import AwareDatetime, ValidationError
from redis import Redis
from redis.exceptions import RedisError
from psycopg_pool import PoolTimeout, TooManyRequests

# Ayarlar görev modülü içe alınmadan önce yüklenir.
load_dotenv()

from celery_app import celery_app
from database import get_connection
from models import LogInput, MetricInput, AlertRuleInput, AlertRulePatch, MAX_BATCH_SIZE
from queries import page, telemetry_filters
from tasks import process_log, process_metric, process_logs_batch, process_metrics_batch

logger = logging.getLogger(__name__)
app = FastAPI(title="Observability Platform", version="0.3.0",
              description="Log/metrik toplama, filtreleme ve sistem içi alarm API'si.")

Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Service = Annotated[str | None, Query(min_length=1, max_length=200, pattern=r"\S")]
Time = Annotated[AwareDatetime | None, Query()]
RecordId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # NaN/Infinity gibi geçersiz girdileri cevap JSON'una tekrar eklemeyiz.
    details = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
               for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": details})


@app.exception_handler(OperationalError)
@app.exception_handler(QueryCanceled)
@app.exception_handler(LockNotAvailable)
@app.exception_handler(PoolTimeout)
@app.exception_handler(TooManyRequests)
async def database_unavailable(request: Request, exc: Exception):
    logger.warning("Veritabanı işlemi tamamlanamadı: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Veritabanı geçici olarak erişilemiyor; tekrar deneyin."})


@app.get("/health", tags=["Sağlık"])
def health():
    return {"status": "ok"}


@app.get("/ready", tags=["Sağlık"])
def ready():
    checks = {"database": False, "redis": False}
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1 FROM alert_rules LIMIT 1")
        checks["database"] = True
    except (OperationalError, UndefinedTable, QueryCanceled, LockNotAvailable, PoolTimeout, TooManyRequests):
        pass
    try:
        with Redis.from_url(celery_app.conf.broker_url, socket_connect_timeout=2, socket_timeout=2) as client:
            checks["redis"] = bool(client.ping())
    except RedisError:
        pass
    ok = all(checks.values())
    return JSONResponse(status_code=200 if ok else 503,
                        content={"status": "ready" if ok else "unavailable", "checks": checks})


def enqueue(task, payload):
    is_batch = isinstance(payload, list)
    items = payload if is_batch else [payload]
    received_at = datetime.now(timezone.utc).isoformat()
    records = [item.model_dump(mode="json") for item in items]
    for record in records:
        record["received_at"] = received_at
    try:
        result = task.apply_async(args=[records if is_batch else records[0]], retry=False)
    except (BrokerError, RedisError, OSError):
        raise HTTPException(503, "Veri kuyruğa alınamadı; Redis bağlantısını kontrol edip tekrar deneyin.")
    response = {"status": "queued", "task_id": result.id}
    if is_batch:
        response["record_count"] = len(records)
    return response


@app.post("/logs", status_code=202, tags=["Loglar"])
def receive_log(log: LogInput):
    return enqueue(process_log, log)


@app.post("/metrics", status_code=202, tags=["Metrikler"])
def receive_metric(metric: MetricInput):
    return enqueue(process_metric, metric)


@app.post("/logs/batch", status_code=202, tags=["Loglar"])
def receive_logs_batch(logs: Annotated[list[LogInput], Body(min_length=1, max_length=MAX_BATCH_SIZE)]):
    return enqueue(process_logs_batch, logs)


@app.post("/metrics/batch", status_code=202, tags=["Metrikler"])
def receive_metrics_batch(metrics: Annotated[list[MetricInput], Body(min_length=1, max_length=MAX_BATCH_SIZE)]):
    return enqueue(process_metrics_batch, metrics)


@app.get("/tasks/{task_id}", tags=["Görevler"])
def task_status(task_id: UUID):
    try:
        result = celery_app.AsyncResult(str(task_id))
        state = result.state
    except (BrokerError, RedisError, OSError):
        raise HTTPException(503, "Görev durumuna erişilemiyor; Redis bağlantısını kontrol edin.")
    # PENDING, kimliğin varlığını kanıtlamaz; sonucu henüz yok veya süresi dolmuş olabilir.
    response = {"task_id": str(task_id), "state": state,
                "completed": state in ("SUCCESS", "FAILURE"), "successful": state == "SUCCESS"}
    if state == "FAILURE":
        response["detail"] = "Görev başarısız oldu; worker loglarında bu kimliği arayın."
    return response


@app.get("/logs", tags=["Loglar"])
def list_logs(service: Service = None,
              level: Literal["INFO", "WARN", "ERROR", "FATAL"] | None = None,
              q: Annotated[str | None, Query(min_length=1, max_length=500, pattern=r"\S")] = None,
              tags: Annotated[str | None, Query(max_length=4000)] = None,
              start: Time = None, end: Time = None, limit: Limit = 20, offset: Offset = 0):
    clauses, values = telemetry_filters(service, start, end, tags)
    if level is not None:
        clauses.append("level = %s")
        values.append(level)
    if q is not None:
        clauses.append("to_tsvector('simple', message) @@ websearch_to_tsquery('simple', %s)")
        values.append(q)
    return page("SELECT id, timestamp, received_at, service, level, message, stack_trace, tags FROM logs",
                clauses, values, "timestamp DESC, id DESC", limit, offset)


@app.get("/metrics", tags=["Metrikler"])
def list_metrics(service: Service = None,
                 name: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
                 unit: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
                 tags: Annotated[str | None, Query(max_length=4000)] = None,
                 start: Time = None, end: Time = None, limit: Limit = 20, offset: Offset = 0):
    clauses, values = telemetry_filters(service, start, end, tags)
    for column, value in (("name", name), ("unit", unit)):
        if value is not None:
            clauses.append(f"{column} = %s")
            values.append(value)
    return page("SELECT id, timestamp, received_at, service, name, value, unit, tags FROM metrics",
                clauses, values, "timestamp DESC, id DESC", limit, offset)


RULE_FIELDS = ("name", "kind", "service", "metric_name", "metric_unit", "level", "operator",
               "threshold", "window_seconds", "cooldown_seconds", "enabled")


@app.get("/alert-rules", tags=["Alarm kuralları"])
def list_rules(enabled: bool | None = None, limit: Limit = 20, offset: Offset = 0):
    clauses, values = (["enabled = %s"], [enabled]) if enabled is not None else ([], [])
    return page("SELECT * FROM alert_rules", clauses, values, "id ASC", limit, offset)


@app.post("/alert-rules", status_code=201, tags=["Alarm kuralları"])
def create_rule(rule: AlertRuleInput):
    data = rule.model_dump()
    try:
        with get_connection() as conn:
            conn.row_factory = dict_row
            result = conn.execute(
                "INSERT INTO alert_rules (" + ", ".join(RULE_FIELDS) + ") VALUES ("
                + ", ".join(["%s"] * len(RULE_FIELDS)) + ") RETURNING *",
                [data[field] for field in RULE_FIELDS],
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(409, "Bu isimde bir alarm kuralı zaten var")
    return result


@app.patch("/alert-rules/{rule_id}", tags=["Alarm kuralları"])
def update_rule(rule_id: RecordId, patch: AlertRulePatch):
    changes = patch.model_dump(exclude_unset=True)
    try:
        with get_connection() as conn:
            conn.row_factory = dict_row
            existing = conn.execute("SELECT * FROM alert_rules WHERE id = %s FOR UPDATE", (rule_id,)).fetchone()
            if existing is None:
                raise HTTPException(404, "Alarm kuralı bulunamadı")
            if not changes:
                return existing
            merged = {field: existing[field] for field in RULE_FIELDS}
            merged.update(changes)
            try:
                validated = AlertRuleInput.model_validate(merged).model_dump()
            except ValidationError as exc:
                raise HTTPException(422, exc.errors(include_context=False, include_input=False))
            result = conn.execute(
                "UPDATE alert_rules SET " + ", ".join(field + " = %s" for field in RULE_FIELDS)
                + ", updated_at = clock_timestamp() WHERE id = %s RETURNING *",
                [validated[field] for field in RULE_FIELDS] + [rule_id],
            ).fetchone()
            # Düzenlenen kuralın yeni ayarları sonraki kayıtta hemen uygulanır.
            conn.execute("DELETE FROM alert_states WHERE rule_id = %s", (rule_id,))
    except UniqueViolation:
        raise HTTPException(409, "Bu isimde bir alarm kuralı zaten var")
    return result


@app.get("/alerts", tags=["Alarmlar"])
def list_alerts(service: Service = None, status: Literal["open", "acknowledged"] | None = None,
                rule_id: Annotated[int | None, Query(ge=1, le=9223372036854775807)] = None,
                limit: Limit = 20, offset: Offset = 0):
    clauses, values = [], []
    for column, value in (("service", service), ("status", status), ("rule_id", rule_id)):
        if value is not None:
            clauses.append(f"{column} = %s")
            values.append(value)
    return page("SELECT * FROM alerts", clauses, values, "triggered_at DESC, id DESC", limit, offset)


@app.patch("/alerts/{alert_id}/acknowledge", tags=["Alarmlar"])
def acknowledge_alert(alert_id: RecordId):
    with get_connection() as conn:
        conn.row_factory = dict_row
        result = conn.execute(
            """UPDATE alerts SET status = 'acknowledged',
               acknowledged_at = COALESCE(acknowledged_at, clock_timestamp())
               WHERE id = %s RETURNING *""", (alert_id,),
        ).fetchone()
        if result is None:
            raise HTTPException(404, "Alarm bulunamadı")
    return result
