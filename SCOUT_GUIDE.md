# MKJ SUPA CUP — Scout Module Guide

## Overview

The Scout module enables talent identification and evaluation across all sports disciplines in the Governor Mutula Kilonzo Junior Super Cup. Scouts are assigned a specific discipline and can browse verified players, build shortlists, attend matches, and submit detailed evaluation reports using internationally-aligned scouting criteria.

---

## Users & Roles

| Role | Access |
|------|--------|
| **Scout** | Browse players, manage personal shortlist, evaluate players at matches, view own reports |
| **Admin** | Full access to all scout views |
| **Chief Sports Officer / Director of Sports / Chief Officer - Sports / CEC Sports** | Read-only access to all scout reports across all scouts (Leadership portal) |

---

## End-to-End Process

### 1. Scout Onboarding

- An **Admin** creates the scout's user account via the admin dashboard
- Role is set to **Scout**
- An **assigned discipline** is mandatory (e.g., Football, Volleyball, Basketball, Handball)
- The discipline scopes the scout's default views

### 2. Dashboard

**URL:** `/portal/scout/`

The scout's home screen shows:
- Assigned discipline
- Shortlist count and top-rated (4–5 star) players
- Total verified players in their discipline
- Quick links: Browse Players, My Shortlist, Live Matches

### 3. Browse Players

**URL:** `/portal/scout/players/`

- Lists all **verified** county players, defaulting to the scout's discipline
- **Filters:** discipline, county, name search
- Each player shows whether they're already shortlisted
- Scout can add a player to their shortlist directly (with rating and notes)

### 4. Shortlist Management

**URL:** `/portal/scout/shortlist/`

| Action | URL |
|--------|-----|
| View shortlist | `/portal/scout/shortlist/` |
| Add player | `/portal/scout/shortlist/add/<player_pk>/` (POST) |
| Edit entry | `/portal/scout/shortlist/<pk>/edit/` |
| Remove entry | `/portal/scout/shortlist/<pk>/remove/` (POST) |

- **Rating:** 1–5 stars (1 = Low potential, 5 = Outstanding)
- **Notes:** Freeform scouting notes
- One entry per scout–player pair (unique constraint)
- Filterable by rating

### 5. Live Match Scouting

**URL:** `/portal/scout/matches/`

- Lists fixtures filtered by: Today / Upcoming / Past
- Scoped to the scout's assigned discipline
- Shows which matches have approved squad submissions (home/away)
- Click into a match to view squad details

### 6. Match Squad View

**URL:** `/portal/scout/match/<fixture_pk>/squad/`

- Full squad lists for both teams: starters, substitutes, shirt numbers
- Substitution events from the match report (player, minute)
- Highlights players the scout has already evaluated
- "Evaluate" button on each player

### 7. Player Evaluation

**URL:** `/portal/scout/match/<fixture_pk>/evaluate/<player_pk>/`

This is the core scouting tool — a **sport-specific, criteria-based evaluation form**.

#### Scouting Criteria by Sport

**Football (FIFA standards):**

| Criterion | Description |
|-----------|-------------|
| Technical Ability | Ball control, first touch, passing accuracy, dribbling, shooting technique |
| Tactical Awareness | Positioning, decision making, reading of play, spatial awareness, game intelligence |
| Physical Attributes | Speed, stamina, strength, agility, balance, acceleration |
| Mental Attributes | Composure, leadership, work rate, concentration, resilience, communication |
| Attacking Play | Movement off the ball, finishing, crossing, chance creation, link-up play |
| Defensive Play | Tackling, interceptions, aerial duels, marking, recovery runs |

**Goalkeeper-specific (auto-detected by position):**

| Criterion | Description |
|-----------|-------------|
| Shot Stopping | Reflexes, diving, positioning, one-on-one saves |
| Distribution | Goal kicks, throwing, passing accuracy under pressure |
| Command of Area | Cross collection, communication, sweeping, set piece organisation |
| Footwork | Ability with feet, composure on the ball, short passing |

**Other sports:** Volleyball (FIVB), Basketball (FIBA), and Handball (IHF) each have their own criteria sets.

#### Evaluation Form Fields

| Field | Type | Range |
|-------|------|-------|
| Criteria scores | Per-criterion | 1–10 each |
| Overall rating | Number | 1–10 |
| Strengths | Text | Freeform |
| Weaknesses | Text | Freeform |
| Recommendation | Choice | Highly Recommended / Recommended / Continue Monitoring / Not Recommended |
| Minutes observed | Number | 0+ |
| Notes | Text | Freeform |

- One report per scout + player + fixture (unique constraint)
- Reports can be edited after initial submission

### 8. My Reports

**URL:** `/portal/scout/reports/`

- Lists all the scout's evaluation reports
- Filterable by discipline and recommendation level
- Click into any report for a full detail view with criteria breakdown

**Report Detail:** `/portal/scout/reports/<pk>/`

### 9. Leadership Review

**URL:** `/portal/leadership/scout-reports/`

Available to: Chief Sports Officer, Director of Sports, Chief Officer - Sports, CEC Sports Member

- Browse **all scout reports** across all scouts
- **Filters:** by scout, discipline, recommendation
- **Aggregate stats:** total reports, highly recommended count, active scouts
- Drill into any report: `/portal/leadership/scout-reports/<pk>/`

---

## Data Model Summary

```
ScoutShortlist
├── scout (User, role=scout)
├── player (CountyPlayer)
├── rating (1–5)
├── notes (text)
├── created_at / updated_at
└── Unique: (scout, player)

ScoutReport
├── scout (User, role=scout)
├── player (Player)
├── fixture (Fixture)
├── sport_type (string)
├── criteria_scores (JSON: {"technical": 8, "tactical": 7, ...})
├── overall_rating (1–10)
├── strengths (text)
├── weaknesses (text)
├── recommendation (choice)
├── notes (text)
├── minutes_observed (int)
├── created_at / updated_at
└── Unique: (scout, player, fixture)
```

---

## Data Flow

```
Admin creates Scout (assigns discipline)
        │
        ▼
Scout browses verified players ──► Adds to Shortlist (1–5 rating + notes)
        │
        ▼
Scout views live/upcoming fixtures ──► Opens approved squad lists
        │
        ▼
Scout evaluates players in-match (sport-specific criteria, 1–10 scores)
        │
        ▼
ScoutReport saved (criteria JSON, overall rating, recommendation)
        │
        ▼
Leadership reviews all reports ──► Identifies talent across the county
```

---

## Access Control

- Scouts only see and edit **their own** shortlists and reports
- Discipline scoping ensures focus on the assigned sport (can browse others if needed)
- Leadership gets **read-only** cross-scout visibility
- All scout views are protected by `@role_required('scout', 'admin')` decorator
- Login required on all portal pages
