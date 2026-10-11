from uuid import uuid4

from celery.utils.log import get_task_logger
from psycopg import OperationalError
from psycopg.errors import DeadlockDetected, SerializationFailure, LockNotAvailable
from psycopg.types.json import Jsonb

from alerts import evaluate_alerts
from celery_app import celery_app
from database import get_connection

logger = get_task_logger(__name__)
TASK_OPTIONS = dict(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(OperationalError, DeadlockDetected, SerializationFailure, LockNotAvailable),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)


def save_record(kind: str, record: dict, task_id: str):
    # Görev kimliği, kayıt ve alarm aynı transaction içinde tutulur.
    # İşlem yarıda kalırsa hepsi geri alınır; tekrar teslim çift kayıt üretmez.
    with get_connection() as conn:
        inserted = conn.execute(
            """INSERT INTO processed_tasks (task_id, kind) VALUES (%s, %s)
               ON CONFLICT (task_id) DO NOTHING RETURNING task_id""",
            (task_id, kind),
        ).fetchone()
        if inserted is None:
            logger.info("Görev daha önce işlendi: %s", task_id)
            return
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
        evaluate_alerts(conn, kind, record, task_id)
    logger.info("%s kaydedildi ve alarm kuralları kontrol edildi: %s", kind, record["service"])


@celery_app.task(**TASK_OPTIONS)
def process_log(self, record: dict):
    save_record("log", record, self.request.id or str(uuid4()))


@celery_app.task(**TASK_OPTIONS)
def process_metric(self, record: dict):
    save_record("metric", record, self.request.id or str(uuid4()))
