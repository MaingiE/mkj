# MKJ SUPA CUP — Team Manager Guide

## Overview

Team Managers are responsible for managing their team's match-day squads, monitoring player eligibility, tracking disciplinary sanctions, and filing appeals. Each Team Manager is linked to a specific county discipline through the Technical Bench system.

---

## Users & Roles

| Role | Access |
|------|--------|
| **Team Manager** | Manage own team squads, view verified players, view sanctions, file appeals, view opponent squads (post-approval) |
| **Admin** | Full access to all team manager views |

---

## End-to-End Process

### 1. Team Manager Onboarding

- A county registers a discipline (e.g., Football Men — Makueni Sub-County)
- The **Technical Bench** is populated: Team Manager, Head Coach, Assistant Coach
- When a Team Manager is added to the Technical Bench, a **user account** is auto-created with:
  - Role: `team_manager`
  - Linked `TechnicalBenchMember` profile (one-to-one)
  - Temporary password (emailed, must change on first login)

### 2. Dashboard

**URL:** `/portal/team-manager/`

The Team Manager's home screen shows:
- Linked discipline and county registration
- Verified players in their discipline
- Upcoming fixtures with squad submission status
- Disciplinary sanctions (own team: yellow/red cards)
- Quick links: Squad Selection, Sanctions, Appeals

### 3. Verified Players

**URL:** `/portal/team-manager/verified-players/`

- Lists all **verified** county players in the manager's discipline
- Only verified players (ID + Huduma + FIFA Connect cleared) are eligible for squad selection
- Read-only view — players are registered and verified at the county/sub-county level

### 4. Match-Day Squad Selection

**URL:** `/portal/team-manager/fixtures/<fixture_pk>/squad/`

This is the core Team Manager function:

| Step | Detail |
|------|--------|
| **View fixture** | See upcoming match details (opponent, venue, date, kickoff) |
| **Select starters** | Exact count required by sport (Football: 11, Volleyball: 6, etc.) |
| **Select substitutes** | Up to the allowed number |
| **Choose formation** | Football only (4-4-2, 4-3-3, 4-2-3-1, 3-5-2, etc.) |
| **Choose kit** | Home / Away / Third |
| **Submit** | Status changes to `SUBMITTED` |

**Eligibility rules:**
- Player must be **verified** (ID, Huduma, FIFA Connect all cleared)
- Player must NOT be **suspended**
- Football-specific: Must include at least 1 GK in starters and 1 GK in subs
- Cannot edit after match has started
- If edited after referee approval, requires **re-approval**

**Squad statuses:**
| Status | Meaning |
|--------|---------|
| `Draft` | Saved but not submitted |
| `Submitted` | Awaiting referee approval |
| `Approved` | Confirmed by head official |
| `Rejected` | Needs changes (reason provided) |

### 5. Opponent Team View

**URL:** `/portal/team-manager/fixtures/<fixture_pk>/opponent/`

- Available **only after both squads are approved** by the referee
- Shows opponent's **starting lineup only** (not substitutes)
- Includes shirt numbers and positions

### 6. Sanctions Tracking

**URL:** `/portal/team-manager/sanctions/`

Tracks disciplinary records:
- **Own team:** Yellow cards, red cards per player across all competitions
- **Opponent teams:** Cards from recent fixtures against the manager's teams
- Sorted by severity (red cards first)

### 7. Filing Appeals

**URL:** `/portal/team-manager/appeal/`

| Step | Detail |
|------|--------|
| **Initiate** | Select respondent team, enter subject and details |
| **Save** | Appeal saved as `DRAFT` |
| **Review** | County Sports Director reviews before formal submission |
| **Track** | Status visible on dashboard |

Both appellant and respondent team managers receive email notifications when appeals are filed.

---

## Data Model Summary

```
User (team_manager role)
  └── technical_bench_profile → TechnicalBenchMember
      └── discipline → CountyDiscipline
          ├── players → CountyPlayer (verified)
          └── linked_team → Team
              ├── squad_submissions → SquadSubmission
              │   ├── status (draft → submitted → approved/rejected)
              │   ├── formation, kit_choice
              │   └── squad_players → SquadPlayer
              │       ├── player → Player
              │       ├── is_starter (bool)
              │       └── shirt_number
              └── fixtures (home/away) → Fixture

Appeal
  ├── appellant_team → Team (manager's team)
  ├── appellant_user → User (team manager)
  ├── respondent_team → Team
  └── status (draft → under_review → ...)
```

---

## Data Flow

```
County registers discipline + technical bench
        │
        ▼
Team Manager account auto-created (linked to discipline)
        │
        ▼
Manager views verified players in their discipline
        │
        ▼
Upcoming fixture appears ──► Manager selects squad (starters + subs + formation + kit)
        │
        ▼
Squad SUBMITTED ──► Referee (head official) reviews
        │
        ├── APPROVED ──► Manager can view opponent starters
        │
        └── REJECTED ──► Manager revises and resubmits
        │
        ▼
Post-match: sanctions tracked (yellow/red cards)
        │
        ▼
If dispute: Manager files appeal (Draft → Director review → Jury)
```

---

## Access Control

- Team Managers only see **their own** discipline's players and fixtures
- Squad selection limited to **verified, non-suspended** players
- Opponent view gated behind **mutual squad approval**
- All views protected by `@role_required('team_manager')` decorator
- Login required on all portal pages
