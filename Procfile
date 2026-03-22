web: gunicorn mkj_cms.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 120
release: python manage.py migrate && python manage.py collectstatic --noinput
