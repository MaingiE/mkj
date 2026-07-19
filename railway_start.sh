#!/bin/bash
set -e

echo "=== Running collectstatic ==="
python manage.py collectstatic --noinput

echo "=== Running migrations ==="
python manage.py migrate --noinput

echo "=== Clearing cache ==="
python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache cleared.')" || echo "Cache clear skipped (no Redis yet)"

echo "=== Ensuring superuser ==="
python manage.py ensure_superuser

echo "=== Starting gunicorn ==="
exec gunicorn mkj_cms.wsgi \
  --bind 0.0.0.0:$PORT \
  --workers 3 \
  --threads 2 \
  --timeout 180 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --preload \
  --access-logfile - \
  --access-logformat '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" %(L)ss'
