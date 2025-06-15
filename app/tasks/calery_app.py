from celery import Celery
from app.core.config import settings

# Gunakan Redis yang sudah ada sebagai message broker dan result backend
# Pastikan MONGO_CONNECTION_STRING Anda memiliki format yang benar untuk broker
# Contoh: redis://localhost:6379/0
# Untuk simplisitas, kita asumsikan Redis ada di localhost, atau sesuaikan.
REDIS_URL = "redis://localhost:6379/0" 

celery = Celery(
    __name__,
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks.twitter_tasks']
)

celery.conf.update(
    task_track_started=True,
)