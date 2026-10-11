from uuid import uuid4

from celery.utils.log import get_task_logger
from celery.signals import worker_process_shutdown
from psycopg import OperationalError
from psycopg.errors import DeadlockDetected, SerializationFailure, LockNotAvailable, QueryCanceled
from psycopg.types.json import Jsonb
from psycopg_pool import PoolTimeout, TooManyRequests

from alerts import evaluate_alerts, load_rules
from celery_app import celery_app
from database import get_connection, close_pool
from models import MAX_BATCH_SIZE

logger = get_task_logger(__name__)
TASK_OPTIONS = dict(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(OperationalError, DeadlockDetected, SerializationFailure, LockNotAvailable,
                   QueryCanceled, PoolTimeout, TooManyRequests),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)


def save_records(kind: str, records: list[dict], task_id: str):
    if not 1 <= len(records) <= MAX_BATCH_SIZE:
        raise ValueError("Bir görev 1-100 kayıt içermelidir")
    # Görev kimliği, kayıt ve alarm aynı transaction içinde tutulur.
    # İşlem yarıda kalırsa hepsi geri alınır; tekrar teslim çift kayıt üretmez.
    with get_connection() as conn:
        inserted = conn.execute(
            """INSERT INTO processed_tasks (task_id, kind, record_count) VALUES (%s, %s, %s)
               ON CONFLICT (task_id) DO NOTHING RETURNING task_id""",
            (task_id, kind, len(records)),
        ).fetchone()
        if inserted is None:
            logger.info("Görev daha önce işlendi: %s", task_id)
            return {"status": "already_processed"}
        # Kurallar her kayıt için yeniden okunmaz; toplu görevde bir kez sıralı kilitlenir.
        rules = load_rules(conn, kind, records)
        now = conn.execute("SELECT clock_timestamp()").fetchone()[0] if rules else None
        for index, record in enumerate(records):
            insert_record(conn, kind, record)
            evaluate_alerts(conn, kind, record, task_id, index, rules, now)
    logger.info("%s kaydı yazıldı ve alarm kuralları kontrol edildi: %s", len(records), kind)
    return {"status": "saved", "record_count": len(records)}


def insert_record(conn, kind: str, record: dict):
    if kind == "log":
        conn.execute(
            """INSERT INTO logs
               (timestamp, received_at, service, level, message, stack_trace, tags)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (record["timestamp"], record["received_at"], record["service"],
             record["level"], record["message"], record.get("stack_trace"),
             Jsonb(record.get("tags", {}))),
        )
    else:
        conn.execute(
            """INSERT INTO metrics
               (timestamp, received_at, service, name, value, unit, tags)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (record["timestamp"], record["received_at"], record["service"],
             record["name"], record["value"], record["unit"],
             Jsonb(record.get("tags", {}))),
        )

def save_record(kind: str, record: dict, task_id: str):
    return save_records(kind, [record], task_id)


@celery_app.task(**TASK_OPTIONS)
def process_log(self, record: dict):
    return save_record("log", record, self.request.id or str(uuid4()))


@celery_app.task(**TASK_OPTIONS)
def process_metric(self, record: dict):
    return save_record("metric", record, self.request.id or str(uuid4()))


@celery_app.task(**TASK_OPTIONS)
def process_logs_batch(self, records: list[dict]):
    return save_records("log", records, self.request.id or str(uuid4()))


@celery_app.task(**TASK_OPTIONS)
def process_metrics_batch(self, records: list[dict]):
    return save_records("metric", records, self.request.id or str(uuid4()))


@worker_process_shutdown.connect
def close_worker_connections(**kwargs):
    close_pool()
