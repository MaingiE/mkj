#!/bin/bash
set -e

echo "=== Running collectstatic ==="
python manage.py collectstatic --noinput

echo "=== Running migrations ==="
python manage.py migrate --noinput

echo "=== Ensuring superuser ==="
python manage.py ensure_superuser

echo "=== Starting gunicorn ==="
exec gunicorn mkj_cms.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 120
