from celery_app import celery_app

@celery_app.task
def process_log(record: dict):
    print("worker logu aldi:", record)