import logging
from celery import Celery
from m4_app.config.settings import settings

# Setup logging formatting for the Celery module
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("m4_app")

# Initialize the Celery application
celery_app = Celery(
    "m4_app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BROKER_URL  # Use redis also for result backend
)

# Celery Configurations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True
)

# Discover tasks from tasks package
# By targeting "m4_app", Celery automatically scans "m4_app.tasks" for any tasks
celery_app.autodiscover_tasks(["m4_app"])

logger.info(f"Celery application initialized pointing to broker: {settings.CELERY_BROKER_URL}")

if __name__ == "__main__":
    print("FocusFlow Module 4 - AI / Transcription Worker Initialized.")
    print("To start this Celery worker, execute:")
    print("  celery -A m4_app.main.celery_app worker --loglevel=info")
