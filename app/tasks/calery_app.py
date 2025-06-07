# ===========================================================================
# File: app/tasks/celery_app.py (Basic Celery Setup)
# ===========================================================================
"""
from celery import Celery
from app.core.config import settings, logger # Menggunakan logger dari config

# Pastikan Celery bisa menemukan modul tasks.
# Ini bisa dilakukan dengan mengatur PYTHONPATH atau memastikan struktur impor benar.
# Jika worker dijalankan dari root project, path 'app.tasks.nama_modul_task' seharusnya bekerja.

celery_app = Celery(
    "cigar_ds_worker", # Nama instance Celery, bisa apa saja
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[ # Daftar modul yang berisi definisi tasks
        'app.tasks.example_tasks',
        # 'app.tasks.user_tasks', # Akan ditambahkan nanti
        # 'app.tasks.mission_tasks', # Akan ditambahkan nanti
    ]
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC', # Disarankan menggunakan UTC untuk Celery
    enable_utc=True,
    # task_acks_late = True, # Jika ingin task di-ack setelah selesai (bukan saat diterima worker)
    # worker_prefetch_multiplier = 1, # Untuk task I/O bound atau long-running
    # worker_send_task_events = True, # Jika ingin memonitor task events (misal dengan Flower)
    # task_send_sent_event = True,
)

# Contoh Celery Beat schedule (jika ada tugas periodik)
# celery_app.conf.beat_schedule = {
# 'run-example-every-minute': {
# 'task': 'app.tasks.example_tasks.periodic_example_task', # Path lengkap ke task
# 'schedule': 60.0, # Setiap 60 detik
# 'args': ("Hello from Beat",),
# },
# }

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    logger.info("Celery app configured. Periodic tasks (if any) should be set up.")
    # Jika beat_schedule di-set di atas, ini hanya konfirmasi.
    # Jika ingin menambah task secara dinamis, bisa dilakukan di sini.

if __name__ == '__main__':
    # Perintah untuk menjalankan worker dari CLI:
    # celery -A app.tasks.celery_app.celery_app worker -l info -P eventlet (untuk Windows)
    # celery -A app.tasks.celery_app.celery_app beat -l info (untuk scheduler)
    celery_app.start()
"""