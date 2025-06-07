
# Cigar DS Backend API

API Backend untuk Project Cigar DS ($CIGAR) Restoration Project.
Dibangun menggunakan FastAPI, MongoDB, dan Redis.

## Struktur Project

Lihat `fastapi_folder_structure_cigar_ds` untuk detail struktur folder.

## Setup

1.  **Buat dan aktifkan virtual environment Python:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate    # Windows
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Environment Variables:**
    * Salin `.env.example` menjadi `.env`.
    * Isi semua variabel yang dibutuhkan di file `.env` (MONGODB_URL, SECRET_KEY, dll.).

4.  **Pastikan MongoDB dan Redis berjalan:**
    * MongoDB harus berjalan dan dapat diakses sesuai `MONGODB_URL`.
    * Redis harus berjalan dan dapat diakses sesuai `REDIS_HOST` dan `REDIS_PORT`.

## Menjalankan Aplikasi FastAPI

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Akses API di `http://localhost:8000`.
Dokumentasi Swagger UI: `http://localhost:8000/docs`
Dokumentasi ReDoc: `http://localhost:8000/redoc`

## Menjalankan Celery Worker (Untuk Tugas Asynchronous)

(Konfigurasi Celery akan ditambahkan lebih detail nanti)
Pastikan Redis (sebagai broker) berjalan.
```bash
celery -A app.tasks.celery_app.celery_app worker -l info
```

## Menjalankan Celery Beat (Untuk Tugas Terjadwal)
```bash
celery -A app.tasks.celery_app.celery_app beat -l info
```

## Testing

(Struktur tes sudah ada, implementasi tes akan ditambahkan)
```bash
# pytest
```