# Gunakan image ringan tapi lengkap
FROM python:3.10-slim

# Install system dependencies (buat lxml, cryptography, dll)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Salin semua file ke container
COPY . /app

# Upgrade pip dan install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port untuk FastAPI (default: 8000)
EXPOSE 8000

# Command default: Jalankan FastAPI pakai uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
