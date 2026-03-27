# MKJ SUPA CUP - Discipline Coordinator Guide

## Overview

Discipline Coordinators are the operational backbone of each sport in the MKJ SUPA CUP. Each coordinator is assigned a specific discipline (Football, Volleyball, Basketball, or Handball) and manages everything within that discipline: competitions, fixtures, pools, venues, referees, match reports, squads, and statistics. All views are scoped so a coordinator only sees data for their assigned sport.

---

## Users & Roles

| Role | Access |
|------|--------|
| **Coordinator** | Full management of competitions, fixtures, pools, venues, referees, match reports, squads, and statistics within assigned discipline |
| **Admin** | Full access to all coordinator views across all disciplines |

---

## Discipline Scoping

Every coordinator has an `assigned_discipline` (required at account creation):

| Discipline | Sport Variants Covered |
|------------|----------------------|
| Football | Football Men, Football Women |
| Volleyball | Volleyball Men, Volleyball Women |
| Basketball | Basketball Men, Basketball Women, Basketball 3x3 Men, Basketball 3x3 Women |
| Handball | Handball Men, Handball Women |

All queries are automatically filtered through `_coordinator_variants(discipline)`, ensuring complete isolation between disciplines.

---

## End-to-End Process

### 1. Coordinator Onboarding

- An **Admin** creates the coordinator account via the admin dashboard
- Required fields: email, name, phone, `assigned_discipline`
- Temporary password auto-generated and emailed
- `must_change_password=True` enforced on first login

### 2. Dashboard

**URL:** `/portal/coordinator/`

Overview scoped to the coordinator's discipline:
- Active and upcoming competitions
- Total fixtures, completed, upcoming
- Pending match reports and referee approvals
- Recent results

### 3. Competition Management

**URLs:**
- `/portal/coordinator/competitions/` - List competitions
- `/portal/coordinator/competitions/<pk>/` - Central management hub
- `/portal/coordinator/competitions/<pk>/edit/` - Edit competition settings

**Editable fields:** format type, age group, start/end dates, max teams, teams per group, qualify from group count, description, rules, status

**Central management hub shows:**
- Pool standings (auto-sorted by points, goal difference, goals for)
- Eligible teams not yet in pools
- Group-stage and knockout fixtures
- Active venues
- Match report counts (pending/approved)

### 4. Pool Management

**URL:** `/portal/coordinator/competitions/<pk>/pools/`

| Action | Detail |
|--------|--------|
| **Create pool** | Name + optional default venue |
| **Delete pool** | Removes pool and all associated fixtures |
| **Add team** | Assign team to pool; auto-generates round-robin fixtures if pool has 2+ teams |
| **Remove team** | Remove team from pool |

**Auto-fixture generation:**
- Round-robin: all team combinations within the pool
- Dates spaced by configurable interval (default: 7 days)
- Default kickoff time: 14:00
- Round numbers auto-incremented

### 5. Fixture Generation & Management

**Generate:** `/portal/coordinator/competitions/<pk>/fixtures/generate/`

| Parameter | Description |
|-----------|-------------|
| Start date | First fixture date |
| Kickoff time | Default time for all fixtures |
| Group interval | Days between group-stage matches |
| Knockout interval | Days between knockout matches |
| Venue | Optional single venue for all fixtures |
| Knockout teams | Number advancing from each group |

Uses `generate_all_fixtures()` from the fixture engine. Action logged to `ActivityLog`.

**Edit fixture:** `/portal/coordinator/competitions/<pk>/fixtures/<fixture_pk>/edit/`

Editable: match date, kickoff time, venue, status, scores. For knockout: home/away teams.

**Exceptional case handling:** Score or status changes require:
- Confirmation checkbox (`confirm_exceptional`)
- Written reason (minimum 12 characters)
- Logged as `RESULT_OVERRIDE` with before/after state

### 6. Venue Management

**URLs:**
- `/portal/coordinator/venues/` - View and manage all venues
- `/portal/coordinator/competitions/<pk>/venues/` - Allocate venue to a competition

| Action | Detail |
|--------|--------|
| **Create** | Name, county, city, capacity, surface type, address, facilities |
| **Toggle** | Activate or deactivate a venue |
| **Update** | Edit venue details |
| **Allocate** | Batch-set venue for all fixtures in a competition |

### 7. Standings Management

**URL:** `/portal/coordinator/competitions/<pk>/standings/edit/`

| Action | Detail |
|--------|--------|
| **Update standings** | Edit pool team stats: played, won, drawn, lost, goals for, goals against, bonus points |
| **Recalculate** | Recalculate a single pool from fixture results |
| **Recalculate all** | Recalculate all pools in the competition |

Manual standings edits require exceptional case confirmation + reason (min 12 chars). Logged as `STANDINGS_OVERRIDE`.

### 8. Referee Management

**URL:** `/portal/coordinator/referees/`

| Action | Detail |
|--------|--------|
| **View pending** | List referees awaiting approval |
| **Approve** | Activate account, generate temp password, send credentials email |
| **Reject** | Delete referee profile and user account |
| **View approved** | Full list of active referees with stats |

### 9. Referee Appointments

**URLs:**
- `/portal/coordinator/appointments/` - Overview of all fixtures with staffing status
- `/portal/coordinator/appointments/<fixture_pk>/` - Appoint officials to a specific fixture

**Appointment process:**
1. View fixtures needing officials (filterable: upcoming/past)
2. See required and optional roles per sport type
3. Select approved referee for each role
4. System warns about same-date conflicts (but allows)
5. Replacing an existing appointment marks the old one as `replaced`

**Staffing stats shown:** Total fixtures, needing officials, partially staffed, fully staffed

### 10. Match Reports

**URL:** `/portal/coordinator/match-reports/`

Coordinators review submitted match reports:

| Action | Detail |
|--------|--------|
| **Approve** | Finalize the report; fixture results locked |
| **Return** | Send back to referee with reviewer notes for revision |

Filterable by status: submitted, approved, returned.

### 11. Squad Review

**URL:** `/portal/coordinator/squads/`

View all squad submissions filtered by the coordinator's discipline:
- Filterable by status: draft, submitted, approved, rejected
- Coordinator can monitor squad approval progress (referee handles actual approval)

### 12. Statistics

**URL:** `/portal/coordinator/competitions/<pk>/stats/`

Comprehensive statistical view:
- **Top scorers** - ranked by goals
- **Top assisters** - ranked by assists
- **Disciplinary table** - yellow and red cards per player
- **Fair play table** - team-level discipline ranking
- **Pool standings** - per pool with full stats

### 13. Competition Rules

**URL:** `/portal/coordinator/competitions/<pk>/rules/`

Edit the competition's rules text field (freeform).

---

## Data Model Summary

```
User (coordinator role)
  └── assigned_discipline (football/volleyball/basketball/handball)
      │
      └── Scopes access to ──► Competition (sport_type matches variants)
                                  │
                                  ├── pools → Pool[]
                                  │   └── teams → PoolTeam[] (standings)
                                  │
                                  ├── fixtures → Fixture[]
                                  │   ├── referee_appointments → RefereeAppointment[]
                                  │   ├── squads → SquadSubmission[]
                                  │   └── match_report → MatchReport
                                  │       ├── events → MatchEvent[]
                                  │       └── period_scores → PeriodScore[]
                                  │
                                  └── venues → Venue[]

RefereeProfile
  ├── is_approved (coordinator approves)
  ├── appointments (coordinator creates)
  └── reviews (coordinator rates)
```

---

## Data Flow

```
Admin creates Coordinator (assigns discipline)
        │
        ▼
Coordinator views/creates competitions for their sport
        │
        ▼
Creates pools ──► Adds teams ──► Auto-generates round-robin fixtures
        │
        ▼
Generates knockout fixtures (configurable parameters)
        │
        ▼
Manages venues ──► Allocates venues to competitions/fixtures
        │
        ▼
Approves referee registrations ──► Appoints referees to fixtures
        │
        ▼
Monitors squad submissions (referee handles approval)
        │
        ▼
Reviews match reports ──┬──► Approves (results finalized)
                        └──► Returns (referee revises)
        │
        ▼
Manages standings (auto-recalculate or manual edit with audit)
        │
        ▼
Reviews statistics (scorers, assists, discipline, fair play)
        │
        ▼
Rates referee performance (post-match reviews)
```

---

## Activity Logging

All sensitive coordinator actions are logged to `ActivityLog`:

| Action | Trigger |
|--------|---------|
| `FIXTURES_GENERATED` | Fixture generation completed |
| `RESULT_OVERRIDE` | Score or status manually edited (with before/after + reason) |
| `STANDINGS_OVERRIDE` | Pool standings manually edited (with before/after + reason) |

---

## Access Control

- Coordinators only see data for their **assigned discipline** (complete isolation)
- All views protected by `@role_required('coordinator', 'admin')` decorator
- Exceptional case edits (scores, standings) require confirmation + written justification
- Login required on all portal pages
- Admin can access any coordinator view regardless of discipline
