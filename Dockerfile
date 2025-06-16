# Gunakan Python image
FROM python:3.13.1

# Set direktori kerja
WORKDIR /app

# Salin requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file ke image
COPY . .

# Jalankan FastAPI pakai Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
