FROM python:3.12-slim

# Verhindert, dass Python unnötigen Datenmüll schreibt (.pyc)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Im Dockerfile
RUN apt-get update && apt-get install -y \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- VORSCHLAG 1: SCHNELLES BAUEN ---
# Zuerst nur die Liste der Pakete kopieren
COPY requirements.txt /app/
# Nur installieren, wenn sich die requirements.txt geändert hat
RUN pip install --no-cache-dir -r requirements.txt

# --- VORSCHLAG 2: AUTOMATISCHES CSS ---
# Den restlichen Code kopieren
COPY . /app/
# CSS-Dateien für Nginx einsammeln (passiert jetzt beim Bauen)
RUN python manage.py collectstatic --noinput

# Startbefehl für Gunicorn
CMD ["gunicorn", "mittagessen.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "90", "--workers", "3"]
