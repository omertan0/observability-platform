import os
from celery import Celery

redis_url = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/0"
)

result_url = os.getenv("REDIS_RESULT_URL", redis_url.rsplit("/", 1)[0] + "/1")
celery_app = Celery("observability", broker=redis_url, backend=result_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=False,
    task_track_started=True,
    result_expires=86400,
    redis_socket_connect_timeout=3,
    redis_socket_timeout=3,
    result_backend_transport_options={"retry_policy": {"timeout": 3, "max_retries": 1}},
    task_publish_retry=False,
    broker_connection_timeout=3,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
        "retry_on_timeout": False,
        "visibility_timeout": 3600,
    },
    worker_prefetch_multiplier=1,
    timezone="UTC",
)
