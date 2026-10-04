import os
from celery import Celery

redis_url = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/0"
)

celery_app = Celery("observability", broker=redis_url)