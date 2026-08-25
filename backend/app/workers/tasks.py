import time
from celery.utils.log import get_task_logger
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="send_welcome_notification")
def send_welcome_notification(self, email: str, username: str) -> dict:
    """Simulates sending a transactional onboarding notification."""
    logger.info(f"Starting email delivery task for user: {username} ({email})")
   
    time.sleep(3)
    logger.info(f"Email successfully delivered to {email}")
    return {
        "status": "SENT",
        "recipient": email,
        "timestamp": time.time(),
    }


@celery_app.task(bind=True, name="process_data_analytics")
def process_data_analytics(self, record_count: int) -> dict:
    """Simulates a resource-intensive computational analytics job."""
    logger.info(f"Processing batch data analytics on {record_count} records...")
   
    time.sleep(5)
    
    result_metric = record_count * 1.42
    logger.info(f"Batch processing completed. Computed metric: {result_metric}")
    return {
        "status": "COMPLETED",
        "records_processed": record_count,
        "computed_metric": result_metric,
    }