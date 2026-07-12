FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/')" || exit 1

CMD sh -c "python manage.py migrate --noinput && python manage.py ensure_update_service && daphne -b 0.0.0.0 -p ${PORT:-8000} duo_project.asgi:application"
