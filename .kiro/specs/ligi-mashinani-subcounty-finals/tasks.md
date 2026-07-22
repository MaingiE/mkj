# Implementation Plan: Ligi Mashinani → MKJ Supa Cup Subcounty Finals

## Overview
Extend the existing Ligi Mashinani system to support the MKJ Supa Cup Subcounty Finals tier.
Reuse the County Finals competition engine (pools, fixtures, standings) wherever possible.
All new code is layered onto `teams/models.py`, `accounts/models.py`, and `mkj_cms/web_views.py`.

## Tasks

- [ ] 1. Data model changes
  - [ ] 1.1 Add `subcounty_discipline_coordinator` to `UserRole` in `accounts/models.py`
  - [ ] 1.2 Add `WardAllStarsTeam` model to `teams/models.py`
  - [ ] 1.3 Add `OutsideLigiPlayerRequest` + `OutsideLigiRequestStatus` to `teams/models.py`
  - [ ] 1.4 Add `SubcountyDisciplineCoordinator` model to `teams/models.py`
  - [ ] 1.5 Add `qualified_to_subcounty_finals` + `qualifying_subcounty_competition` FK to `Team` model
  - [ ] 1.6 Add `allstars_team` FK, `is_outside_ligi`, `outside_ligi_request` FK to `CountyPlayer`
  - [ ] 1.7 Create and apply migration `0047_subcounty_finals_models`

- [ ] 2. Business logic helpers (`teams/subcounty_finals.py`)
  - [ ] 2.1 Implement `check_subcounty_finals_age_eligibility(dob, competition_date)`
  - [ ] 2.2 Implement `validate_ward_allstars_squad_age(squad_players, competition)`
  - [ ] 2.3 Implement `submit_outside_ligi_player_request(...)`
  - [ ] 2.4 Implement `director_review_outside_ligi_request(...)`
  - [ ] 2.5 Implement `cso_final_review_outside_ligi_request(...)`
  - [ ] 2.6 Implement `promote_ligi_player_to_allstars(county_player, allstars_team)`

- [ ] 3. WSCC views — Ward All Stars management
  - [ ] 3.1 `wscc_allstars_dashboard_view` — GET /ligi/wscc/allstars/
  - [ ] 3.2 `wscc_create_allstars_team_view` — create WardAllStarsTeam for competition
  - [ ] 3.3 `wscc_appoint_officials_view` — appoint/replace Coach + TM
  - [ ] 3.4 `wscc_revoke_official_view` — revoke appointment
  - [ ] 3.5 Template: `ligi/wscc/allstars_dashboard.html`
  - [ ] 3.6 Template: `ligi/wscc/allstars_appoint.html`

- [ ] 4. Ward All Stars Manager (TM) views
  - [ ] 4.1 `allstars_tm_dashboard_view` — GET /ligi/allstars/dashboard/
  - [ ] 4.2 `allstars_tm_longlist_view` — manage Under-23 longlist
  - [ ] 4.3 `allstars_tm_add_ligi_player_view` — pick eligible Ligi Mashinani players
  - [ ] 4.4 `allstars_tm_request_outside_player_view` — submit outside-Ligi request
  - [ ] 4.5 `allstars_tm_outside_requests_view` — track request statuses
  - [ ] 4.6 `allstars_tm_fixture_squad_view` — match-day squad selection
  - [ ] 4.7 Templates for all TM views

- [ ] 5. Director of Sports — Outside-Ligi review views
  - [ ] 5.1 `director_outside_ligi_requests_view` — list pending requests
  - [ ] 5.2 `director_outside_ligi_review_view` — approve/reject + forward to CSO
  - [ ] 5.3 Template: `portal/director/outside_ligi_requests.html`

- [ ] 6. Chief Sports Officer — final approval views
  - [ ] 6.1 `cso_outside_ligi_requests_view` — list forwarded requests
  - [ ] 6.2 `cso_outside_ligi_review_view` — final approve/reject
  - [ ] 6.3 Template: `portal/cso/outside_ligi_requests.html`

- [ ] 7. SCSO — Subcounty Finals management (minimal, reuse existing)
  - [ ] 7.1 `sc_qualify_ward_champion_view` — mark ward qualifiers
  - [ ] 7.2 `sc_allstars_overview_view` — all-stars team status per competition
  - [ ] 7.3 Templates: `portal/subcounty_officer/allstars_overview.html`

- [ ] 8. Subcounty Discipline Coordinator portal
  - [ ] 8.1 `sdc_dashboard_view` — read-only fixture/standings monitor
  - [ ] 8.2 Template: `portal/sdc/dashboard.html`
  - [ ] 8.3 Add SDC sidebar to `includes/sidebar.html`

- [ ] 9. URLs and imports
  - [ ] 9.1 Register all new views in `mkj_cms/urls.py`
  - [ ] 9.2 Add Ligi Mashinani section links to WSCC, TM, Director, CSO, SCSO sidebars

- [ ] 10. Notifications
  - [ ] 10.1 TM appointment email (credentials or notification)
  - [ ] 10.2 Outside-Ligi request emails (Director, CSO, TM on decision)
  - [ ] 10.3 Ward qualification notification to WSCC and SCSO

- [ ] 11. System check and verification
  - [ ] 11.1 Run `python manage.py check` — 0 issues
  - [ ] 11.2 Run `python manage.py migrate` — migration applies cleanly

## Notes
- WSCC appointment of Coach/TM uses existing `notify_account_created` for new TM accounts
- Subcounty Finals competition uses existing Competition engine — no new competition models
- Squad submission reuses existing `SquadSubmission` / `SquadPlayer` with age validation layer
- `SubcountyDisciplineCoordinator` uses existing `coordinator` UserRole with a scoped assignment record
