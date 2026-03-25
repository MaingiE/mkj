# MKJ SUPA CUP AWS Deployment and Operations Guide

This guide is written for a beginner-friendly, step-by-step deployment and day-2 operations workflow.

## 1. What you are deploying

Architecture:

- EC2 (Ubuntu): runs Django + gunicorn + nginx
- PostgreSQL: app database
- Redis: cache/background broker
- S3: media file storage (player docs, photos, files)
- CloudFront (optional but recommended): CDN for S3 media
- Route 53: DNS for your domain
- Let's Encrypt (certbot): SSL certificates

## 2. One-time server setup (EC2)

### 2.1 Connect to your server

From your local machine:

```bash
ssh -i ~/.ssh/mkj-key.pem ubuntu@<EC2_PUBLIC_IP>
```

### 2.2 Install packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev \
  postgresql postgresql-contrib nginx redis-server \
  git certbot python3-certbot-nginx libpq-dev build-essential
```

### 2.3 Create database and DB user

```bash
sudo -u postgres psql << 'EOF'
CREATE DATABASE mkj_supacup;
CREATE USER mkj_user WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE mkj_supacup TO mkj_user;
ALTER DATABASE mkj_supacup OWNER TO mkj_user;
\q
EOF
```

### 2.4 Clone code and install dependencies

```bash
cd /home/ubuntu
git clone https://github.com/Emannuh/MKJ-SUPA-CUP.git mkj_supacup
cd mkj_supacup
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.5 Create production env file

```bash
nano /home/ubuntu/mkj_supacup/.env
```

Use this template:

```env
DEBUG=False
SECRET_KEY=<GENERATE_A_STRONG_SECRET>

ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,<EC2_PUBLIC_IP>
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

DATABASE_URL=postgres://mkj_user:CHANGE_ME_STRONG_PASSWORD@localhost:5432/mkj_supacup
REDIS_URL=redis://127.0.0.1:6379/0

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

AWS_ACCESS_KEY_ID=<AWS_ACCESS_KEY_ID>
AWS_SECRET_ACCESS_KEY=<AWS_SECRET_ACCESS_KEY>
AWS_STORAGE_BUCKET_NAME=<S3_BUCKET_NAME>
AWS_S3_REGION_NAME=af-south-1
AWS_S3_CUSTOM_DOMAIN=<optional-cloudfront-domain>

SENTRY_DSN=<optional-sentry-dsn>
SENTRY_ENVIRONMENT=production
ADMINS=Admin:admin@yourdomain.com
SERVER_EMAIL=noreply@yourdomain.com
```

### 2.6 Apply migrations and static build

```bash
cd /home/ubuntu/mkj_supacup
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```

## 3. Run app as a Linux service (gunicorn)

Create service file:

```bash
sudo nano /etc/systemd/system/mkj_supacup.service
```

Paste:

```ini
[Unit]
Description=MKJ SUPA CUP Django App
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/mkj_supacup
EnvironmentFile=/home/ubuntu/mkj_supacup/.env
ExecStart=/home/ubuntu/mkj_supacup/venv/bin/gunicorn \
  mkj_cms.wsgi \
  --bind 127.0.0.1:8000 \
  --workers 3 \
  --timeout 120 \
  --access-logfile /var/log/mkj_supacup_access.log \
  --error-logfile /var/log/mkj_supacup_error.log
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mkj_supacup
sudo systemctl start mkj_supacup
sudo systemctl status mkj_supacup
```

## 4. Configure nginx reverse proxy

```bash
sudo nano /etc/nginx/sites-available/mkj_supacup
```

Paste:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 50M;

    location /static/ {
        alias /home/ubuntu/mkj_supacup/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

Enable site and restart nginx:

```bash
sudo ln -s /etc/nginx/sites-available/mkj_supacup /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 5. Enable SSL

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo certbot renew --dry-run
```

## 6. Deploy updates later (normal workflow)

Whenever you update code:

```bash
ssh -i ~/.ssh/mkj-key.pem ubuntu@<EC2_PUBLIC_IP>
cd /home/ubuntu/mkj_supacup
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart mkj_supacup
sudo systemctl status mkj_supacup
```

## 7. IMPORTANT: How to see errors when DEBUG=False

When `DEBUG=False`, detailed error pages are hidden from browser users (this is correct for production).

Use these ways to see errors:

### 7.1 Gunicorn service logs (primary)

```bash
sudo journalctl -u mkj_supacup -n 200 --no-pager
sudo journalctl -u mkj_supacup -f
```

### 7.2 App access and error log files

```bash
sudo tail -n 200 /var/log/mkj_supacup_error.log
sudo tail -n 200 /var/log/mkj_supacup_access.log
```

### 7.3 Nginx logs

```bash
sudo tail -n 200 /var/log/nginx/error.log
sudo tail -n 200 /var/log/nginx/access.log
```

### 7.4 Django checks

```bash
cd /home/ubuntu/mkj_supacup
source venv/bin/activate
python manage.py check
```

### 7.5 Sentry (recommended)

If `SENTRY_DSN` is set in `.env`, unhandled exceptions go to Sentry dashboard with traceback and request context.

### 7.6 Admin error emails

If `ADMINS` and SMTP are configured, Django sends server error emails to admins in production.

## 8. How to access server later to run commands

Use SSH from your laptop each time:

```bash
ssh -i ~/.ssh/mkj-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Then run app commands:

```bash
cd /home/ubuntu/mkj_supacup
source venv/bin/activate
python manage.py shell
python manage.py createsuperuser
python manage.py migrate
python manage.py collectstatic --noinput
```

Service control commands:

```bash
sudo systemctl status mkj_supacup
sudo systemctl restart mkj_supacup
sudo systemctl stop mkj_supacup
sudo systemctl start mkj_supacup
```

## 9. Quick troubleshooting checklist

- Site not loading:
  - `sudo systemctl status nginx`
  - `sudo systemctl status mkj_supacup`
  - Check security group allows ports 80/443/22
- 502 Bad Gateway:
  - gunicorn likely down, run `sudo journalctl -u mkj_supacup -n 200 --no-pager`
- Login errors:
  - Check database URL in `.env`
  - Check app logs and activity logs
- Static not loading:
  - `python manage.py collectstatic --noinput`
- Media upload failing:
  - Check S3 credentials and bucket policy

## 10. Security and operations best practices

- Keep `DEBUG=False` in production always
- Never commit `.env`
- Rotate AWS and DB credentials periodically
- Snapshot EC2 volume and back up PostgreSQL regularly
- Restrict SSH (port 22) to your office/home IP where possible
- Use CloudWatch and Sentry for continuous monitoring

---

If you want, create one more file with copy-paste commands for only "daily operations" (restart, logs, deploy, rollback) for your team.
