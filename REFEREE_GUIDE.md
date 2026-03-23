# MKJ SUPA CUP — Referee Guide

## Overview

Referees officiate matches, approve team squads, and submit match reports. The system supports sport-specific officiating roles (Football, Volleyball, Basketball, Handball) with appointment management, availability declaration, profile maintenance, and post-match performance reviews.

---

## Users & Roles

| Role | Access |
|------|--------|
| **Referee** | View own appointments, confirm/decline, approve squads, submit match reports, manage availability, edit profile |
| **Coordinator** | Approve/reject referee registrations, appoint referees to fixtures, review match reports, rate referees |
| **Admin** | Full access to all referee views |

---

## End-to-End Process

### 1. Referee Registration & Approval

**Self-registration flow:**

| Step | Detail |
|------|--------|
| **Register** | Referee submits: name, email, phone, national ID, county, level, referee type, bio, experience, profile photo |
| **Pending** | Account created as `is_active=False`, `is_approved=False` |
| **Review** | Coordinator or Admin views pending list at `/portal/coordinator/referees/` |
| **Approve** | Account activated, temp password generated and emailed, `must_change_password=True` |
| **Reject** | Profile and user account permanently deleted |

**Referee levels:** County, Regional, National, International
**Referee types:** Referee, Assistant Referee, Fourth Official, Match Commissioner

### 2. Profile Management

**URL:** `/portal/referee/edit-profile/`

Referees can edit:
- Personal info (name, phone)
- Referee type and level
- County
- Bio and years of experience
- Profile picture

### 3. Dashboard

**URL:** `/portal/referee/`

The referee's home screen shows:
- **Pending confirmations** — appointments waiting for accept/decline
- **Today's matches** — current day fixtures
- **Upcoming matches** — future confirmed appointments
- **Completed matches** — past fixtures
- **Pending match reports** — completed matches needing reports (head officials only)
- **Draft/returned reports** — reports in progress or sent back for revision
- **Pending squads** — team lists awaiting referee approval (head officials only)

### 4. Appointment Management

#### Coordinator Side

**URLs:**
- `/portal/coordinator/appointments/` — Overview of all fixtures with staffing status
- `/portal/coordinator/appointments/<fixture_pk>/` — Appoint officials to a specific fixture

**Sport-specific roles:**

| Football | Volleyball | Basketball | Handball |
|----------|------------|------------|----------|
| Referee (head) | 1st Referee | Crew Chief | Referee 1 |
| Assistant Referee 1 | 2nd Referee | Umpire 1 | Referee 2 |
| Assistant Referee 2 | Scorer | Umpire 2 | Timekeeper |
| Reserve Referee | Line Judge 1–4 | Commissioner | Scorekeeper |
| Fourth Official | Assistant Scorer | Shot Clock Operator | Delegate |
| Match Commissioner | | Scorer | |

**Appointment process:**
1. Coordinator selects a fixture
2. System shows required and optional roles for that sport
3. Coordinator selects an **approved** referee for each role
4. System warns if referee is already appointed elsewhere on the same date (but allows)
5. Replacing an existing appointment marks the old one as `replaced`

#### Referee Side

**API:** `GET /api/v1/referees/my-appointments/`

**Appointment statuses:**
| Status | Meaning |
|--------|---------|
| `Pending` | Awaiting referee confirmation |
| `Confirmed` | Referee accepted |
| `Declined` | Referee declined |
| `Replaced` | Superseded by a new appointment |

Referees confirm or decline via the dashboard or API (`POST /api/v1/referees/appointments/<id>/confirm/`).

### 5. Availability Declaration

**Model:** `RefereeAvailability` — one entry per referee per date

| Status | Meaning |
|--------|---------|
| `Available` | Free to officiate |
| `Unavailable` | Not available |
| `Tentative` | Might be available |

Coordinators see availability status when making appointments, with busy referees highlighted.

### 6. Squad Approval

**URL:** `/portal/squads/review/`

Only the **head official** (confirmed appointment in the head role for that sport) can approve squads:

| Step | Detail |
|------|--------|
| **View** | See submitted squad with starters, subs, shirt numbers, formation |
| **Approve** | Squad status → `APPROVED`, both teams can proceed |
| **Reject** | Squad status → `REJECTED` with reason, team manager must revise |

Once both squads are approved, team managers can view each other's starting lineups.

### 7. Match Report Submission

**URL:** `/portal/match-report/<fixture_pk>/`

Only the **head official** (or admin) can submit match reports.

#### Report Fields

| Category | Fields |
|----------|--------|
| **Scores** | Home score, away score |
| **Period scores** | Per-period breakdown (halves, sets, quarters depending on sport) |
| **Cards** | Home/away yellow cards, red cards |
| **Duration** | Match duration, added time (HT/FT) |
| **Conditions** | Pitch condition (excellent/good/fair/poor), weather |
| **Attendance** | Spectator count |
| **Events** | Goal, yellow card, red card, substitution, penalty, own goal — with player, team, minute |
| **Abandonment** | Flag + reason if match abandoned |
| **Sport-specific** | Sets won (volleyball), suspensions (handball), overtime periods |
| **Notes** | Referee freeform notes |

#### Report Workflow

```
Referee creates report ──► DRAFT (can save and return later)
        │
        ▼
Referee submits ──────────► SUBMITTED (locked for review)
        │
        ▼
Coordinator reviews ──┬──► APPROVED (final, fixture updated)
                      │
                      └──► RETURNED (referee revises and resubmits)
```

Auto-populated data:
- Approved squad players (starters + subs) from both teams
- Match officials from referee appointments
- Sport-specific event types and period structure

### 8. Performance Reviews

**Model:** `RefereeReview` — one per referee per fixture

Coordinators rate referees after matches on a 1–10 scale:

| Criterion | Description |
|-----------|-------------|
| Overall Score | General performance rating |
| Positioning | Court/field positioning quality |
| Decision Making | Accuracy and consistency of decisions |
| Fitness | Physical fitness and movement |
| Communication | Communication with players, teams, other officials |

Reviews automatically recalculate the referee's `avg_rating` on their profile.

### 9. Certifications

**Model:** `RefereeCertification`

Referees can have multiple certifications:
- Title (e.g., "FIFA Referee Badge")
- Issuing body
- Issue date and expiry date
- Certificate file upload

---

## Data Model Summary

```
User (referee role)
  └── referee_profile → RefereeProfile
      ├── level (county/regional/national/international)
      ├── referee_type (referee/AR/4th official/commissioner)
      ├── is_approved, approved_by, approved_at
      ├── total_matches, avg_rating
      │
      ├── certifications → RefereeCertification[]
      ├── availability → RefereeAvailability[] (date + status)
      ├── appointments → RefereeAppointment[]
      │   ├── fixture → Fixture
      │   ├── role (sport-specific)
      │   ├── status (pending/confirmed/declined/replaced)
      │   └── appointed_by → User (coordinator)
      └── reviews → RefereeReview[]
          ├── fixture → Fixture
          ├── scores (overall, positioning, decision_making, fitness, communication)
          └── reviewer → User (coordinator)

MatchReport
  ├── fixture → Fixture
  ├── referee → RefereeProfile (head official)
  ├── status (draft/submitted/approved/returned)
  ├── scores, cards, duration, conditions
  ├── events → MatchEvent[] (goals, cards, subs with minute + player)
  ├── period_scores → PeriodScore[] (per-period breakdown)
  └── reviewed_by → User (coordinator)

SquadSubmission
  ├── reviewed_by → User (referee who approved/rejected)
  └── reviewed_at
```

---

## Data Flow

```
Referee self-registers ──► Coordinator approves (credentials emailed)
        │
        ▼
Referee logs in, edits profile, declares availability
        │
        ▼
Coordinator appoints referee to fixture (sport-specific role)
        │
        ▼
Referee confirms/declines appointment
        │
        ▼
Pre-match: Referee approves/rejects submitted team squads
        │
        ▼
Match day: Referee officiates
        │
        ▼
Post-match: Head official submits match report (scores, events, cards)
        │
        ├── DRAFT ──► continue editing
        └── SUBMITTED ──► Coordinator reviews
            ├── APPROVED ──► fixture results finalized
            └── RETURNED ──► referee revises
        │
        ▼
Coordinator rates referee performance (1–10 on 5 criteria)
        │
        ▼
avg_rating updated on referee profile
```

---

## REST API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/referees/` | List referees (filterable) |
| GET/PATCH | `/api/v1/referees/<id>/` | View/edit referee profile |
| POST | `/api/v1/referees/<id>/approve/` | Approve/reject registration |
| GET | `/api/v1/referees/my-appointments/` | My appointments |
| POST | `/api/v1/referees/appointments/<id>/confirm/` | Confirm/decline appointment |
| CRUD | `/api/v1/referees/appointments/` | Manage all appointments (coordinator) |
| CRUD | `/api/v1/referees/reviews/` | Manage referee reviews |
| CRUD | `/api/v1/referees/availability/` | Manage availability |

---

## Access Control

- Referees only see **their own** profile, appointments, and reports
- Squad approval restricted to the **confirmed head official** for each fixture
- Match report submission restricted to the **head official** (or admin)
- Coordinator/Admin can approve registrations, appoint officials, review reports, and rate performance
- All views protected by role decorators
- Login required on all portal pages
