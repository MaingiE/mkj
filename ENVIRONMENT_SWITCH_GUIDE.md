# Environment Switch Guide (Local vs Production)

This project should run with different `.env` values per environment.

- Local machines: `DEBUG=True`
- AWS server: `DEBUG=False`

Do not keep one shared `.env` for all environments.

## 1. Files to use

- Local template: `.env.local.example`
- Production template: `.env.production.example`

## 2. Local development setup (both machines)

On each local machine:

1. Copy `.env.local.example` to `.env`
2. Fill values if needed
3. Run local server

```bash
python manage.py check
python manage.py runserver
```

## 3. Production setup (AWS server)

On the AWS server only:

1. Copy `.env.production.example` to `.env`
2. Fill real secrets/domains/DB/S3 values
3. Restart app service

```bash
sudo systemctl restart mkj_supacup
sudo systemctl status mkj_supacup
```

## 4. When you deploy new code

From your AWS server:

```bash
cd /home/ubuntu/mkj_supacup
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart mkj_supacup
```

## 5. If local accidentally has DEBUG=False

Fix local `.env`:

```env
DEBUG=True
```

Then restart local server:

```bash
python manage.py runserver
```

## 6. Verify current mode quickly

```bash
python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"
```

- `True` = local dev mode
- `False` = production mode

## 7. See errors in production (DEBUG=False)

Use logs, not browser tracebacks:

```bash
sudo journalctl -u mkj_supacup -f
sudo tail -n 200 /var/log/mkj_supacup_error.log
sudo tail -n 200 /var/log/nginx/error.log
```

If configured, also use:

- Sentry dashboard
- Admin emails from `ADMINS`
