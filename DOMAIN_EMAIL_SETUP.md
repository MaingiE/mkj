# mkjsupacup.com — Domain, DNS & Email Setup Guide

This guide covers three things:
1. Wiring `mkjsupacup.com` to your Railway deployment
2. DNS records to configure at your registrar
3. Email accounts (`@mkjsupacup.com`) via Google Workspace
4. Wiping the database for a fresh start

---

## 1  Add the Custom Domain in Railway

1. Open **railway.app → your project → web service → Settings → Domains**
2. Click **"+ Add a Custom Domain"**
3. Enter `mkjsupacup.com` → click **Generate**
4. Railway will show you one of these record types (copy the value shown):
   - A record  →  IP address like `12.34.56.78`
   - CNAME record  →  something like `xyz.up.railway.app`
5. Repeat and also add `www.mkjsupacup.com`

---

## 2  Configure DNS at Your Registrar

Log in to wherever you registered `mkjsupacup.com` (Namecheap, GoDaddy, Cloudflare, etc.)  
and add/update these records:

### Apex domain (`mkjsupacup.com`)

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A    | `@`  | *(IP Railway gave you)* | 3600 |

> If Railway gave you a **CNAME** instead of an IP, use:  
> `CNAME @ xyz.up.railway.app` — but not all registrars support CNAME on apex; if yours doesn't, use Cloudflare (free) as your DNS provider and enable the orange-cloud proxy, or use A record mode.

### www subdomain

| Type  | Name  | Value | TTL |
|-------|-------|-------|-----|
| CNAME | `www` | `mkjsupacup.com` | 3600 |

### Email (Google Workspace MX records — add all five)

| Type | Name | Priority | Value |
|------|------|----------|-------|
| MX | `@` | 1 | `ASPMX.L.GOOGLE.COM` |
| MX | `@` | 5 | `ALT1.ASPMX.L.GOOGLE.COM` |
| MX | `@` | 5 | `ALT2.ASPMX.L.GOOGLE.COM` |
| MX | `@` | 10 | `ALT3.ASPMX.L.GOOGLE.COM` |
| MX | `@` | 10 | `ALT4.ASPMX.L.GOOGLE.COM` |

### SPF (prevents email going to spam)

| Type | Name | Value |
|------|------|-------|
| TXT | `@` | `v=spf1 include:_spf.google.com ~all` |

### DKIM (Google Workspace generates this for you — see step 3)

| Type | Name | Value |
|------|------|-------|
| TXT | `google._domainkey` | *(given by Google Workspace admin console after setup)* |

### DMARC (optional but recommended)

| Type | Name | Value |
|------|------|-------|
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:admin@mkjsupacup.com` |

> DNS propagation takes 5–60 minutes. Use https://dnschecker.org to verify.

---

## 3  Set Up Email Accounts via Google Workspace

Google Workspace gives you real `@mkjsupacup.com` addresses with Gmail, Calendar, Drive, etc.

### 3a  Sign up

1. Go to **workspace.google.com** → click **Get Started**
2. Enter your domain `mkjsupacup.com` (choose "I already have a domain")
3. Create your first admin account — suggest: `admin@mkjsupacup.com`
4. Verify domain ownership (Google gives you a TXT record to add in DNS)

### 3b  Recommended email accounts to create

| Address | Purpose |
|---------|---------|
| `admin@mkjsupacup.com` | Primary admin / IT contact |
| `noreply@mkjsupacup.com` | System-generated emails (registration confirmations, password resets) |
| `referees@mkjsupacup.com` | Referee communications |
| `teams@mkjsupacup.com` | Team manager communications |
| `info@mkjsupacup.com` | Public contact / enquiries |

### 3c  Generate an App Password for SMTP

The web app uses SMTP to send automated emails (password resets, notifications).

1. Sign in as `noreply@mkjsupacup.com` in Google
2. Go to **myaccount.google.com → Security → 2-Step Verification** → enable it
3. Then go to **myaccount.google.com → Security → App Passwords**
4. Choose App = "Mail", Device = "Other" → type "MKJ SUPA CUP Railway App" → Generate
5. Copy the 16-character password shown

### 3d  Add DKIM in Google Workspace

1. Google Workspace admin console → **Apps → Google Workspace → Gmail → Authenticate email**
2. Select domain `mkjsupacup.com` → click **Generate new record**
3. Copy the TXT record value → add it to your DNS (see table in §2 above)
4. Come back and click **Start authentication**

---

## 4  Update Railway Environment Variables

In **railway.app → your project → web service → Variables**, set:

```
ALLOWED_HOSTS=mkjsupacup.com,www.mkjsupacup.com
CSRF_TRUSTED_ORIGINS=https://mkjsupacup.com,https://www.mkjsupacup.com
CORS_ALLOWED_ORIGINS=https://mkjsupacup.com,https://www.mkjsupacup.com
SITE_URL=https://mkjsupacup.com
DEBUG=False

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=info@mkjsupacup.com
EMAIL_HOST_PASSWORD=<16-char app password from step 3c>
DEFAULT_FROM_EMAIL=MKJ SUPA CUP <info@mkjsupacup.com>
SERVER_EMAIL=info@mkjsupacup.com
ADMINS=Admin:info@mkjsupacup.com
```

Railway injects `DATABASE_URL` and `REDIS_URL` automatically if you have those plugins — **do not override them**.

After saving variables, Railway will automatically redeploy.

---

## 5  Wipe the Database (Fresh Start)

A management command is included to delete all competition data while preserving superuser accounts.

### Via Railway Shell (recommended)

1. Railway dashboard → your web service → **Shell** (top-right button)
2. Run:

```bash
# Preview what will be deleted (dry run — just shows counts)
python manage.py wipe_data

# Actually wipe (non-interactive — for Railway console)
python manage.py wipe_data --yes
```

### Options

| Flag | Effect |
|------|--------|
| *(none)* | Interactive — asks "YES" to confirm |
| `--yes` | Skip confirmation |
| `--keep-users` | Preserve all user accounts (only wipes competition data) |

### What gets deleted

- Competitions, pools, fixtures, venues, rounds
- Teams, players, squad submissions
- Matches, match reports, events, statistics
- Referees and assignments
- Appeals and evidence
- News articles and media files
- Admin activity logs
- All non-superuser accounts *(unless `--keep-users`)*

### What is preserved

- Superuser accounts (always)
- Django system tables (permissions, content types, sessions)
- Static files

### After wiping — recreate the admin account if needed

```bash
python manage.py createsuperuser
```

---

## 6  Verify Everything Works

Checklist after DNS propagation (~1 hour):

- [ ] `https://mkjsupacup.com` loads the site (Railway SSL cert auto-provisioned)
- [ ] `https://www.mkjsupacup.com` redirects correctly
- [ ] Padlock icon appears (HTTPS, no cert warning)
- [ ] Send a test password-reset email — arrives from `noreply@mkjsupacup.com`
- [ ] Email not in spam (SPF + DKIM records are correct)
- [ ] Railway dashboard shows domain as **"Active"** with green status

---

## Quick Reference

| Service | URL |
|---------|-----|
| Railway dashboard | https://railway.app |
| Google Workspace admin | https://admin.google.com |
| DNS checker | https://dnschecker.org |
| MX record checker | https://mxtoolbox.com |
| SSL checker | https://www.ssllabs.com/ssltest/ |
