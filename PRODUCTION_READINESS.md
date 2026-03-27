# Production Readiness Changes

## 1. User Creation Email Fix
**File:** `admin_dashboard/views.py`

- Tracks whether credential emails actually send successfully (`email_sent` flag)
- Falls back to `send_welcome_email` if `send_credentials_email` fails
- Success message ("password sent to email") only shows when email was **actually delivered**
- If both email attempts fail, warns admin to reset password manually - **no password is ever displayed in the UI**

## 2. Sentry Error Tracking
**Files:** `requirements.txt`, `mkj_cms/settings.py`

- Added `sentry-sdk[django]>=2.0` dependency
- Sentry initializes when `SENTRY_DSN` environment variable is set
- Captures all unhandled exceptions with full tracebacks, request data, and environment info
- Configurable `SENTRY_ENVIRONMENT` variable (default: `production`)
- Low performance overhead: `traces_sample_rate=0.1`, `profiles_sample_rate=0.1`
- `send_default_pii=False` for privacy

**Setup:** Create a free account at [sentry.io](https://sentry.io), create a Django project, and add the DSN to your `.env`:
```env
SENTRY_DSN=https://your-key@sentry.io/your-project-id
SENTRY_ENVIRONMENT=production
```

## 3. ADMINS Email Handler
**File:** `mkj_cms/settings.py`

- Added `ADMINS` setting (loaded from env, format: `Name:email`)
- Added `SERVER_EMAIL` setting
- Django emails all admins on every 500 error with full HTML traceback

**Setup:**
```env
ADMINS=Admin:admin@yourdomain.com
SERVER_EMAIL=noreply@mkjsupacup.go.ke
```

## 4. Improved Logging
**File:** `mkj_cms/settings.py`

- Added `mail_admins` handler with `require_debug_false` filter - only fires in production
- Added `django.request` logger - captures all request errors (4xx/5xx)
- `django.security` logger now also routes to `mail_admins`
- Verbose formatter includes process and thread IDs for debugging

## 5. Redis Cache in Production
**File:** `mkj_cms/settings.py`

- **Development (`DEBUG=True`):** local memory cache (no setup needed)
- **Production (`DEBUG=False`):** Redis cache via `django-redis`, using `REDIS_URL`

## 6. PostgreSQL Database Backup
**File:** `db_backup.sql`

- Full PostgreSQL dump of `mkj_supacup` database
- Committed to repo for portability between machines

**To restore on a new machine:**
```bash
# Create database and user
createdb -U postgres mkj_supacup
psql -U postgres -c "CREATE USER mkj_user WITH PASSWORD 'your-password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE mkj_supacup TO mkj_user;"

# Restore data
psql -U postgres mkj_supacup < db_backup.sql
```

---

## Production .env Checklist

Before going live, ensure these are set in your production environment:

```env
DEBUG=False
SECRET_KEY=<new-strong-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com

# Database
DATABASE_URL=postgres://user:pass@host:5432/mkj_supacup

# Email (required for credential emails to work)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Error monitoring
SENTRY_DSN=https://your-key@sentry.io/your-project-id
SENTRY_ENVIRONMENT=production
ADMINS=Admin:admin@yourdomain.com

# Cache
REDIS_URL=redis://your-redis-host:6379/0
```

## Security (auto-enabled when DEBUG=False)

- `SECURE_SSL_REDIRECT = True`
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `SECURE_HSTS_SECONDS = 31536000` (1 year)
- `SECURE_HSTS_PRELOAD = True`
- `X_FRAME_OPTIONS = "DENY"`
