from celery_app import celery_app
from database import get_connection
from psycopg.types.json import Jsonb

@celery_app.task
def process_log(record: dict):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO logs
                (timestamp, received_at, service, level, message, stack_trace, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record["timestamp"],
                record["received_at"],
                record["service"],
                record["level"],
                record["message"],
                record.get("stack_trace"),
                Jsonb(record.get("tags", {})),
            ),
        )

    print("Log veritabanina kaydedildi:", record["service"])
    
@celery_app.task
def process_metric(record: dict):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO metrics
                (timestamp, received_at, service, name, value, unit, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record["timestamp"],
                record["received_at"],
                record["service"],
                record["name"],
                record["value"],
                record["unit"],
                Jsonb(record.get("tags", {})),
            ),
        )

    print("Metrik veritabanina kaydedildi:", record["service"])