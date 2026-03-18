# KYISA Competition Management System
## Complete Developer Setup & Architecture Guide

---

## WHAT YOU HAVE BUILT

A full enterprise-grade Django REST API backend for the Kenya Youth Intercounty Sports Association competition management system. Here is what every file does:

```
kyisa_cms/                      ← Project root
├── manage.py                   ← Django command runner
├── requirements.txt            ← All Python dependencies
├── .env.example                ← Copy to .env and fill in your values
│
├── kyisa_cms/                  ← Main Django project config
│   ├── settings.py             ← ALL configuration (DB, auth, CORS, JWT...)
│   └── urls.py                 ← Master URL router
│
├── accounts/                   ← Users & authentication
│   ├── models.py               ← Custom User model with 5 roles
│   ├── serializers.py          ← JWT login + user profile serializers
│   ├── views.py                ← Login, register, profile, user management
│   ├── permissions.py          ← Role-based permission classes
│   ├── urls.py                 ← Auth endpoints
│   └── admin.py                ← Admin panel config
│
├── competitions/               ← Core competition logic
│   ├── models.py               ← Competition, Venue, Pool, PoolTeam, Fixture
│   ├── serializers.py          ← Data validation + field transformations
│   ├── views.py                ← CRUD ViewSets with role-based access
│   ├── urls.py                 ← Competition endpoints
│   └── admin.py
│
├── referees/                   ← Referee lifecycle management
│   ├── models.py               ← RefereeProfile, Appointment, Availability, Review
│   ├── serializers.py          ← Includes approval + review workflows
│   ├── views.py                ← Register, approve, appoint, review
│   ├── urls.py
│   └── admin.py
│
├── teams/                      ← Team and player management
│   ├── models.py               ← Team, Player
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── admin.py
│
└── matches/                    ← Match day operations
    ├── models.py               ← SquadSubmission, MatchReport, MatchEvent
    ├── serializers.py          ← Deadline enforcement + squad validation
    ├── views.py                ← Submit squad, approve squad, submit/approve report
    ├── urls.py
    └── admin.py
```

---

## STEP 1 — INSTALL PREREQUISITES

You need these installed on your machine before starting.

### Python (3.11+)
```bash
python --version        # Must be 3.11 or higher
# If not installed: https://www.python.org/downloads/
```

### PostgreSQL (recommended for production, optional for development)
```bash
# Ubuntu/Debian:
sudo apt update && sudo apt install postgresql postgresql-contrib

# macOS with Homebrew:
brew install postgresql@16

# Create the database:
sudo -u postgres psql
CREATE USER kyisa_user WITH PASSWORD 'your_password';
CREATE DATABASE kyisa_db OWNER kyisa_user;
GRANT ALL PRIVILEGES ON DATABASE kyisa_db TO kyisa_user;
\q
```

### Redis (for caching and Celery)
```bash
# Ubuntu/Debian:
sudo apt install redis-server
sudo systemctl start redis

# macOS:
brew install redis
brew services start redis

# Test Redis is running:
redis-cli ping    # Should return: PONG
```

---

## STEP 2 — PROJECT SETUP

### 1. Create and activate a virtual environment

```bash
cd kyisa_cms
python -m venv venv

# Activate it:
source venv/bin/activate          # Linux / macOS
venv\Scripts\activate             # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set:
- `SECRET_KEY` — generate one: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `DATABASE_URL` — use SQLite for dev, PostgreSQL for production
- `REDIS_URL` — use `redis://127.0.0.1:6379/0`

### 4. Run database migrations

```bash
python manage.py makemigrations accounts competitions referees teams matches
python manage.py migrate
```

### 5. Create a superuser (System Admin)

```bash
python manage.py createsuperuser
# Enter: email, first name, last name, password
```

### 6. Start the development server

```bash
python manage.py runserver
```

The API is now running at: **http://127.0.0.1:8000**

---

## STEP 3 — VERIFY EVERYTHING IS WORKING

Open your browser and visit:

| URL | What you see |
|-----|-------------|
| http://127.0.0.1:8000/admin/ | Django Admin Panel |
| http://127.0.0.1:8000/api/docs/ | Swagger API Documentation |
| http://127.0.0.1:8000/api/redoc/ | ReDoc API Documentation |

---

## STEP 4 — SEED INITIAL DATA

### Option A: Use the Admin Panel (easiest)
Go to http://127.0.0.1:8000/admin/ and create:
1. Users for each role (Competition Manager, Referee Manager, etc.)
2. Competitions
3. Venues
4. Pools

### Option B: Django shell (for bulk loading)
```bash
python manage.py shell
```

```python
from accounts.models import User

# Create Competition Manager
User.objects.create_user(
    email="cm@kyisa.ke",
    password="StrongPassword123",
    first_name="James",
    last_name="Kamau",
    role="competition_manager",
    county="Nairobi"
)

# Create Referee Manager
User.objects.create_user(
    email="rm@kyisa.ke",
    password="StrongPassword123",
    first_name="Grace",
    last_name="Ochieng",
    role="coordinator",
    county="Kisumu",
    assigned_discipline="football_men"
)

# Create a competition
from competitions.models import Competition
comp = Competition.objects.create(
    name="KYISA U-17 Inter-County Championship 2025",
    season="2025",
    age_group="U17",
    status="active",
    start_date="2025-03-01",
    end_date="2025-06-30",
    max_teams=16,
)
print("Competition created:", comp)
```

---

## STEP 5 — FULL API REFERENCE

### Authentication

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| POST | /api/v1/auth/login/ | All | Login — returns JWT access+refresh + user object |
| POST | /api/v1/auth/logout/ | All | Blacklist refresh token |
| POST | /api/v1/auth/register/ | All | Create new account |
| GET | /api/v1/auth/profile/ | All | Get my profile |
| PATCH | /api/v1/auth/profile/ | All | Update my profile |
| POST | /api/v1/auth/token/refresh/ | All | Get new access token using refresh token |

**Login Request:**
```json
POST /api/v1/auth/login/
{
  "email": "cm@kyisa.ke",
  "password": "your_password"
}
```

**Login Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1Q...",
  "refresh": "eyJ0eXAiOiJKV1Q...",
  "user": {
    "id": 1,
    "email": "cm@kyisa.ke",
    "full_name": "James Kamau",
    "role": "competition_manager",
    "role_display": "Competition Manager",
    "county": "Nairobi"
  }
}
```

**All subsequent requests need the Authorization header:**
```
Authorization: Bearer eyJ0eXAiOiJKV1Q...
```

---

### Competitions (Competition Manager only — write access)

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| GET | /api/v1/competitions/ | All | List competitions (filter: status, age_group) |
| POST | /api/v1/competitions/ | CM | Create competition |
| GET | /api/v1/competitions/{id}/ | All | Competition detail |
| PATCH | /api/v1/competitions/{id}/ | CM | Update competition |
| DELETE | /api/v1/competitions/{id}/ | CM | Delete competition |

### Venues

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| GET | /api/v1/competitions/venues/ | All | List venues |
| POST | /api/v1/competitions/venues/ | CM | Add venue |
| PATCH | /api/v1/competitions/venues/{id}/ | CM | Update venue |

### Fixtures

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| GET | /api/v1/competitions/fixtures/ | All | List fixtures (filter: competition, status, date) |
| POST | /api/v1/competitions/fixtures/ | CM | Create fixture |
| PATCH | /api/v1/competitions/fixtures/{id}/ | CM | Update fixture |
| GET | /api/v1/competitions/fixtures/{id}/squads/ | Auth | View both squads for a fixture |

### Pools

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/competitions/pools/ | List pools with standings |
| POST | /api/v1/competitions/pools/ | Create pool (CM) |
| POST | /api/v1/competitions/pools/add-team/ | Add team to pool (CM) |

---

### Referees

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| GET | /api/v1/referees/ | All | List referees (filter: approved, level, county) |
| POST | /api/v1/referees/register/ | Referee | Submit registration profile |
| GET | /api/v1/referees/{id}/ | All | Referee detail |
| POST | /api/v1/referees/{id}/approve/ | RM | Approve or reject referee |
| GET | /api/v1/referees/my-appointments/ | Referee | My assigned fixtures |
| POST | /api/v1/referees/appointments/{id}/confirm/ | Referee | Confirm or decline appointment |

**Approve Referee:**
```json
POST /api/v1/referees/5/approve/
{
  "is_approved": true,
  "notes": "All documents verified"
}
```

**Make Appointment (Referee Manager):**
```json
POST /api/v1/referees/appointments/
{
  "fixture": 3,
  "referee": 1,
  "role": "centre",
  "notes": "Experience in U-17 games required"
}
```

**Confirm Appointment (Referee):**
```json
POST /api/v1/referees/appointments/7/confirm/
{
  "action": "confirm"
}
```

### Referee Availability
```json
POST /api/v1/referees/availability/
{
  "date": "2025-03-15",
  "status": "available"
}
```

### Referee Reviews (Referee Manager)
```json
POST /api/v1/referees/reviews/
{
  "referee": 1,
  "fixture": 3,
  "overall_score": 8,
  "positioning": 9,
  "decision_making": 8,
  "fitness": 7,
  "communication": 8,
  "notes": "Excellent management of the game"
}
```

---

### Teams

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| GET | /api/v1/teams/ | All | List teams |
| POST | /api/v1/teams/ | TM | Register team |
| GET | /api/v1/teams/{id}/ | All | Team detail with players |
| GET | /api/v1/teams/players/ | All | List players |
| POST | /api/v1/teams/players/ | TM | Register player |

---

### Matches — Squad Submission

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| POST | /api/v1/matches/squads/ | TM | Submit squad (enforces 4-hour deadline) |
| GET | /api/v1/matches/squads/list/ | Auth | View submitted squads |
| POST | /api/v1/matches/squads/{id}/approve/ | Referee | Approve or reject squad |

**Squad Submission (Team Manager):**
```json
POST /api/v1/matches/squads/
{
  "fixture": 1,
  "squad_players": [
    {"player": 5,  "shirt_number": 1,  "is_starter": true},
    {"player": 3,  "shirt_number": 3,  "is_starter": true},
    {"player": 7,  "shirt_number": 7,  "is_starter": true},
    {"player": 11, "shirt_number": 11, "is_starter": true},
    {"player": 4,  "shirt_number": 4,  "is_starter": true},
    {"player": 9,  "shirt_number": 9,  "is_starter": true},
    {"player": 6,  "shirt_number": 6,  "is_starter": true},
    {"player": 2,  "shirt_number": 2,  "is_starter": true},
    {"player": 10, "shirt_number": 10, "is_starter": true},
    {"player": 8,  "shirt_number": 8,  "is_starter": true},
    {"player": 12, "shirt_number": 12, "is_starter": true},
    {"player": 14, "shirt_number": 14, "is_starter": false},
    {"player": 15, "shirt_number": 15, "is_starter": false},
    {"player": 16, "shirt_number": 16, "is_starter": false}
  ]
}
```

**The API will automatically reject submissions past the 4-hour deadline.**

**Approve Squad (Referee):**
```json
POST /api/v1/matches/squads/3/approve/
{
  "action": "approve"
}

// OR reject:
{
  "action": "reject",
  "rejection_reason": "Player #9 is suspended. Please replace."
}
```

---

### Matches — Match Reports

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| POST | /api/v1/matches/reports/ | Referee | Submit match report |
| GET | /api/v1/matches/reports/ | Auth | List reports (referees see only theirs) |
| PATCH | /api/v1/matches/reports/{id}/ | Referee | Update draft report |
| POST | /api/v1/matches/reports/{id}/approve/ | RM | Approve or return for revision |

**Submit Match Report (Referee):**
```json
POST /api/v1/matches/reports/
{
  "fixture": 1,
  "home_score": 2,
  "away_score": 1,
  "home_yellow_cards": 2,
  "away_yellow_cards": 1,
  "home_red_cards": 0,
  "away_red_cards": 0,
  "pitch_condition": "good",
  "weather": "Sunny, 28°C",
  "attendance": 850,
  "referee_notes": "Match played without major incidents. Player #9 (Nairobi Stars) received yellow card for simulation in 67th minute.",
  "events": [
    {"team": 1, "player": 9,  "event_type": "goal",   "minute": 23, "notes": "Header from corner"},
    {"team": 1, "player": 11, "event_type": "goal",   "minute": 71, "notes": "Counter attack"},
    {"team": 2, "player": 7,  "event_type": "goal",   "minute": 45, "notes": "Free kick"},
    {"team": 1, "player": 9,  "event_type": "yellow", "minute": 67, "notes": "Simulation"},
    {"team": 2, "player": 3,  "event_type": "yellow", "minute": 80, "notes": "Late tackle"}
  ]
}
```

**When the Referee Manager approves a match report, the system automatically:**
1. Updates the fixture score
2. Sets fixture status to "completed"
3. Updates pool standings (W/D/L/GF/GA/Points)

---

## STEP 6 — CONNECTING YOUR REACT FRONTEND

In your React app (the `.jsx` file we built), replace the static `USERS` and `FIXTURES` data with real API calls.

### Setup Axios

```bash
npm install axios
```

Create `src/api.js`:

```javascript
import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/v1",
});

// Automatically attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh token on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem("refresh_token");
      if (refresh) {
        const res = await axios.post("/api/v1/auth/token/refresh/", { refresh });
        localStorage.setItem("access_token", res.data.access);
        error.config.headers.Authorization = `Bearer ${res.data.access}`;
        return axios(error.config);
      }
      // Refresh failed → redirect to login
      window.location.href = "/";
    }
    return Promise.reject(error);
  }
);

export default api;
```

### Login call

```javascript
import api from "./api";

async function login(email, password) {
  const res = await api.post("/auth/login/", { email, password });
  localStorage.setItem("access_token",  res.data.access);
  localStorage.setItem("refresh_token", res.data.refresh);
  return res.data.user;  // { id, email, full_name, role, county, ... }
}
```

### Fetch fixtures

```javascript
const fixtures = await api.get("/competitions/fixtures/");
// fixtures.data.results = array of fixtures
```

---

## STEP 7 — PRODUCTION DEPLOYMENT

### On a VPS (DigitalOcean, AWS EC2, etc.)

**1. Install system dependencies**
```bash
sudo apt update && sudo apt install python3.11 python3.11-venv postgresql postgresql-contrib redis-server nginx
```

**2. Set up the project**
```bash
git clone https://github.com/your-org/kyisa-cms.git
cd kyisa-cms
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set DEBUG=False, real DATABASE_URL, strong SECRET_KEY
python manage.py collectstatic --noinput
python manage.py migrate
```

**3. Run with Gunicorn**
```bash
gunicorn kyisa_cms.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

**4. Nginx config** (`/etc/nginx/sites-available/kyisa`)
```nginx
server {
    listen 80;
    server_name api.kyisa.ke;

    location /static/ { root /home/ubuntu/kyisa-cms/staticfiles; }
    location /media/  { root /home/ubuntu/kyisa-cms/media; }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**5. SSL with Certbot (free HTTPS)**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.kyisa.ke
```

**6. Systemd service** (`/etc/systemd/system/kyisa.service`)
```ini
[Unit]
Description=KYISA CMS Gunicorn
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/kyisa-cms
EnvironmentFile=/home/ubuntu/kyisa-cms/.env
ExecStart=/home/ubuntu/kyisa-cms/venv/bin/gunicorn kyisa_cms.wsgi:application --bind 0.0.0.0:8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable kyisa && sudo systemctl start kyisa
```

---

## STEP 8 — COMMON COMMANDS CHEAT SHEET

```bash
# Start development server
python manage.py runserver

# Apply database changes (run after editing models.py)
python manage.py makemigrations
python manage.py migrate

# Open interactive Python shell (with Django loaded)
python manage.py shell

# Create admin account
python manage.py createsuperuser

# Collect static files (production)
python manage.py collectstatic

# Run tests
python manage.py test

# Check for configuration errors
python manage.py check

# Start Celery worker (for background tasks like emails)
celery -A kyisa_cms worker -l info

# Reset all data (CAUTION — deletes everything!)
python manage.py flush
```

---

## STEP 9 — WHAT TO BUILD NEXT

Your backend is complete and working. Here is the recommended order for next features:

**Priority 1 — Core Workflow Completion**
- [ ] Add `migrations/` folders by running `makemigrations` (needed before `migrate`)
- [ ] Add email notifications (referee appointment → email referee, squad rejection → email team manager)
- [ ] Add `pytz` to requirements for timezone handling in squad deadlines

**Priority 2 — Polish**
- [ ] Live score WebSocket updates using Django Channels
- [ ] PDF export for match reports
- [ ] SMS notifications via Africa's Talking API (Kenya-local SMS)
- [ ] Player eligibility auto-check (age vs competition age_group)

**Priority 3 — Reporting**
- [ ] Competition summary endpoint (aggregated stats)
- [ ] Referee performance report endpoint
- [ ] Export to Excel/CSV

**Priority 4 — Mobile**
- [ ] Push notifications for referees and team managers
- [ ] React Native / Flutter mobile app using the same API

---

## ARCHITECTURE OVERVIEW

```
Browser/Mobile App (React)
         │
         │ HTTPS / REST API (JSON)
         ▼
┌─────────────────────────────────┐
│        Nginx (reverse proxy)    │
└───────────────┬─────────────────┘
                │
┌───────────────▼─────────────────┐
│     Django + DRF (Gunicorn)     │
│  ┌─────────────────────────┐    │
│  │  JWT Authentication     │    │
│  │  Role-Based Permissions │    │
│  │  REST API Endpoints     │    │
│  └────────────┬────────────┘    │
└───────────────┼─────────────────┘
                │
     ┌──────────┼───────────┐
     ▼          ▼           ▼
┌─────────┐ ┌───────┐ ┌────────┐
│PostgreSQL│ │ Redis │ │ Media  │
│(database)│ │(cache)│ │ Files  │
└─────────┘ └───────┘ └────────┘
```

---

## TROUBLESHOOTING

| Error | Fix |
|-------|-----|
| `No module named 'environ'` | Run `pip install django-environ` |
| `DATABASES setting improperly configured` | Copy `.env.example` to `.env` |
| `django.db.utils.OperationalError: no such table` | Run `python manage.py migrate` |
| `401 Unauthorized` on API calls | Include `Authorization: Bearer <token>` header |
| `403 Forbidden` | Your user's role doesn't have permission for that endpoint |
| `400 Squad submission deadline has passed` | Squad submitted too late (>4 hrs before KO) |
| Redis `Connection refused` | Start Redis: `sudo systemctl start redis` |

---

*Built for KYISA — Kenya Youth Intercounty Sports Association*
*Framework: Django 5.0 · DRF 3.15 · PostgreSQL · JWT Authentication*
