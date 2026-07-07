# Implementation Plan: Ligi Mashinani → Sub-County MKJ Finals → County MKJ Supa Cup Finals

## Overview

This plan implements the three-level grassroots competition pipeline by extending the existing MKJ SUPA CUP Django application. The approach is additive: a `level` field scopes existing model families (`Competition`, `CountyRegistration`, `CountyDiscipline`, `CountyPlayer`) to ward/subcounty/county tiers without duplicating models. New models (`WardLonglist`) and new views (`/ligi/`, `/subcounty/`) are added alongside existing code. All code targets Python/Django.

---

## Tasks

- [x] 1. Model layer — extend existing models with level fields and migrations
  - [x] 1.1 Add `CompetitionLevel` TextChoices and `level`, `sub_county`, `ward` fields to `competitions/models.py` `Competition` model
    - Add `CompetitionLevel` TextChoices enum (`ward`, `subcounty`, `county`) to `competitions/models.py`
    - Add `level` CharField(20) with default `county`, `sub_county` CharField(100) blank/default `""`, `ward` CharField(100) blank/default `""` to `Competition`
    - Override `Competition.clean()` to enforce: `level=subcounty` → `sub_county` required; `level=ward` → both `sub_county` and `ward` required; `level=county` → no additional constraint
    - _Requirements: 1.1, 1.2, 1.3, 1.7_

  - [ ]* 1.2 Write property tests for Competition level field (Properties 1 & 2)
    - **Property 1: Competition level field default preserves existing data**
    - **Validates: Requirements 1.1, 1.4, 1.5**
    - **Property 2: Level validation rejects incomplete subcounty/ward competitions**
    - **Validates: Requirements 1.2, 1.3, 1.7**

  - [x] 1.3 Add `level` field to `CountyRegistration` and `CountyDiscipline` in `teams/models.py`; add `ward` field to `CountyDiscipline`; update `CountyDiscipline.unique_together`
    - Add `level` CharField(20) defaulting to `county` to both `CountyRegistration` and `CountyDiscipline`
    - Add `ward` CharField(100) blank/default `""` to `CountyDiscipline`
    - Update `CountyDiscipline.Meta.unique_together` to `["registration", "sport_type", "sub_county", "level", "ward"]`
    - _Requirements: 1.4, 1.5_

  - [x] 1.4 Add `ward` field and `WARD_SPORTS_COUNCIL_CHAIR` role to `accounts/models.py` `User` model
    - Add `WARD_SPORTS_COUNCIL_CHAIR = "ward_sports_council_chair", "Ward Sports Council Chair"` to `UserRole`
    - Add `ward` CharField(100) blank/default `""` to `User`
    - Add `is_ward_sports_council_chair` property following existing role helper pattern
    - _Requirements: 4.1, 10.1_

  - [x] 1.5 Create `WardLonglist` model and `WardLonglistStatus` choices in `teams/models.py`
    - Implement `WardLonglistStatus` TextChoices: `draft`, `submitted`, `wscc_approved`, `returned`
    - Implement `WardLonglist` with fields: `discipline` (OneToOneField to CountyDiscipline, `limit_choices_to={"level": "ward"}`), `status`, `submitted_at`, `reviewed_by`, `reviewed_at`, `return_reason`, `created_at`, `updated_at`
    - _Requirements: 3.5, 3.6, 4.3_

  - [x] 1.6 Add `qualified_to_county` and `qualifying_county_competition` fields to `Team` model in `teams/models.py`
    - Add `qualified_to_county` BooleanField default `False`
    - Add `qualifying_county_competition` FK to `Competition`, nullable, `related_name="qualified_teams"`
    - _Requirements: 11.1, 11.2_

  - [x] 1.7 Add `source_ward_player` and `source_subcounty_player` FK fields to `CountyPlayer` model in `teams/models.py`
    - Add `source_ward_player` self-FK, null/blank, `related_name='subcounty_instances'`
    - Add `source_subcounty_player` self-FK, null/blank, `related_name='county_instances'`
    - _Requirements: 8.1, 8.2_

  - [x] 1.8 Generate and apply all database migrations for the model changes above
    - Create migration for `competitions` app: `CompetitionLevel`, `level`, `sub_county`, `ward` on `Competition`
    - Create migration for `accounts` app: `ward` field and new `UserRole` value
    - Create migration for `teams` app: `level`/`ward` on `CountyRegistration` and `CountyDiscipline`, updated `unique_together`, `WardLonglist`, team qualification fields, `CountyPlayer` source FKs
    - _Requirements: 1.1–1.5_

- [x] 2. Checkpoint — Verify migrations and model layer
  - Run `python manage.py migrate --check` and `python manage.py test` (smoke tests) to confirm all migrations apply cleanly and existing tests pass. Ask the user if questions arise.

- [x] 3. Ward Team Manager onboarding — approval signal and account creation
  - [x] 3.1 Implement atomic `approve_registrations` admin action in `teams/admin.py`
    - Wrap the entire creation sequence in `transaction.atomic()`
    - Create `User` (`role=TEAM_MANAGER`, `must_change_password=True`, `sub_county`/`ward` from registration)
    - Find or create `CountyRegistration` at `level=ward`
    - Find or create `CountyDiscipline` at `level=ward` with matching `sub_county` and `ward`
    - Create `Team` (`status=registered`) linked to the discipline
    - Create `WardLonglist` in `draft` status for that discipline
    - Send credentials email (wrapped in try/except; on failure log to `ActivityLog` and continue)
    - Set `LigiMashinaniRegistration.account_created = True`
    - On any exception: rollback, set `status=pending`, log to `ActivityLog`, raise `messages.error`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 3.2 Write property tests for approval transaction atomicity and account setup invariants (Properties 3 & 4)
    - **Property 3: Approval transaction is all-or-nothing**
    - **Validates: Requirements 2.3, 2.4**
    - **Property 4: Ward Team Manager account setup invariants**
    - **Validates: Requirements 2.1, 2.2**

  - [x] 3.3 Implement rejection notification for `LigiMashinaniRegistration` in `teams/admin.py`
    - When registration is set to `rejected`, send rejection email with reason to the manager's registered email
    - _Requirements: 2.6_

- [x] 4. Player longlist management — Ward Team Manager views (`/ligi/`)
  - [x] 4.1 Implement scoping helpers in `mkj_cms/web_views.py`
    - Extend `_discipline_queryset_for_user(user, level=None)` to filter by `level` and optionally `ward`
    - Extend `_competition_queryset_for_user(user, level=None)` to filter by `level` and `sub_county`
    - Add `subcounty_scope_required` decorator that raises HTTP 403 if `object.sub_county != request.user.sub_county`
    - _Requirements: 12.1, 12.2_

  - [x] 4.2 Implement Ward Team Manager dashboard view (`ward_tm_dashboard_view`) in `mkj_cms/web_views.py`
    - Gate with `@role_required('team_manager')` and guard that redirects if user has no linked `WardLonglist`
    - Display ward, sub-county, discipline, and longlist status summary
    - Redirect to `/ligi/dashboard/`
    - _Requirements: 2.5_

  - [x] 4.3 Implement player longlist list view (`ward_tm_longlist_view`) and add/edit/delete player views
    - `ward_tm_longlist_view`: display all `CountyPlayer` objects for user's ward `CountyDiscipline` at `level=ward`
    - `ward_tm_add_player_view`: enforce required fields (full name, national ID or birth certificate number, DOB, passport photo, identity document); check for duplicate national ID; calculate and store age from DOB on save
    - `ward_tm_edit_player_view`: block if longlist status is `wscc_approved`
    - `ward_tm_delete_player_view`: block if longlist status is `wscc_approved`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.7_

  - [ ]* 4.4 Write property tests for player longlist scoping, field validation, age calculation, and national ID uniqueness (Properties 5, 6, 7, 8)
    - **Property 5: Ward player longlist scoping**
    - **Validates: Requirements 3.1, 12.1**
    - **Property 6: Player field validation rejects incomplete submissions**
    - **Validates: Requirements 3.2**
    - **Property 7: Age calculation invariant**
    - **Validates: Requirements 3.3**
    - **Property 8: National ID uniqueness across all CountyPlayer records**
    - **Validates: Requirements 3.4, 8.3**

  - [x] 4.5 Implement longlist submit view (`ward_tm_submit_longlist_view`)
    - Prevent submission if longlist has zero players (display validation message)
    - On submit: set `WardLonglist.status = submitted`, set `submitted_at`, prevent further edits
    - Send email notification to assigned WSCC that a new longlist awaits review (wrapped in try/except with ActivityLog on failure)
    - _Requirements: 3.5, 3.6, 3.7, 13.1_

  - [ ]* 4.6 Write property tests for longlist state machine transitions (Property 9)
    - **Property 9: Longlist state machine transitions are gating**
    - **Validates: Requirements 3.6, 3.8, 4.3, 4.7**

  - [x] 4.7 Register all `/ligi/` URL patterns in project URL conf
    - Add routes: `/ligi/dashboard/`, `/ligi/longlist/`, `/ligi/longlist/add-player/`, `/ligi/longlist/<int:player_pk>/edit/`, `/ligi/longlist/<int:player_pk>/delete/`, `/ligi/longlist/submit/`, `/ligi/fixtures/`, `/ligi/fixtures/<int:fixture_pk>/squad/`
    - _Requirements: 2.5, 3.1–3.7_

- [x] 5. Checkpoint — Ward Team Manager portal
  - Run unit tests covering the `/ligi/` views. Ensure all tests pass. Ask the user if questions arise.

- [x] 6. WSCC role — portal views and approval/return workflow (`/ligi/wscc/`)
  - [x] 6.1 Implement WSCC dashboard and longlist list views (`wscc_dashboard_view`, `wscc_longlists_view`)
    - Gate with `@role_required('ward_sports_council_chair', 'admin')`
    - Filter all querysets by `sub_county = request.user.sub_county`
    - Dashboard: show all submitted longlists for wards in the WSCC's sub-county
    - _Requirements: 4.2, 10.5_

  - [x] 6.2 Implement WSCC longlist detail view (`wscc_longlist_detail_view`)
    - Display all identity document images, calculated age, and full player name
    - _Requirements: 4.5_

  - [x] 6.3 Implement WSCC approve longlist view (`wscc_approve_longlist_view`)
    - POST only; set `WardLonglist.status = wscc_approved`, set `reviewed_by` and `reviewed_at`
    - Send approval email to Ward Team Manager
    - _Requirements: 4.3, 13.2_

  - [x] 6.4 Implement WSCC return longlist view (`wscc_return_longlist_view`)
    - POST only; require non-empty, non-whitespace written reason (reject and show error if absent)
    - Set `WardLonglist.status = draft` (or `returned`), store `return_reason`
    - Send return email to Ward Team Manager containing the written reason
    - _Requirements: 4.4, 3.8, 13.3_

  - [ ]* 6.5 Write property test for WSCC return reason required and WSCC dashboard scoping (Properties 10 & 20)
    - **Property 10: WSCC return requires a written reason**
    - **Validates: Requirements 4.4**
    - **Property 20: WSCC dashboard scopes to their sub-county's wards only**
    - **Validates: Requirements 4.2, 10.5**

  - [x] 6.6 Register all `/ligi/wscc/` URL patterns
    - Add routes: `/ligi/wscc/dashboard/`, `/ligi/wscc/longlists/`, `/ligi/wscc/longlists/<int:longlist_pk>/`, `/ligi/wscc/longlists/<int:longlist_pk>/approve/`, `/ligi/wscc/longlists/<int:longlist_pk>/return/`
    - _Requirements: 4.1–4.7_

- [x] 7. WSCC admin management (one-per-ward enforcement)
  - [x] 7.1 Add WSCC uniqueness validation to `User` model or form in `accounts/`
    - In `User.clean()` (or a dedicated form validator), enforce that only one active (`is_active=True`) WSCC exists per `ward` at any time
    - Apply same enforcement when assigning or changing a WSCC's ward
    - _Requirements: 10.2_

  - [ ]* 7.2 Write property test for one active WSCC per ward uniqueness (Property 21)
    - **Property 21: One active WSCC per ward uniqueness invariant**
    - **Validates: Requirements 10.2**

  - [x] 7.3 Extend Django admin panel for WSCC management
    - Display WSCC's assigned ward, sub-county, and count of pending longlist reviews in the admin list view
    - Allow admin to change WSCC's assigned ward (triggers access revocation/grant logic via `ward` field update)
    - When WSCC `is_active` is set to `False`, surface a notice in admin that pending reviews must be manually reassigned before they can be actioned
    - _Requirements: 10.1, 10.3, 10.4, 10.5_

- [x] 8. Match-day squad selection (ward level)
  - [x] 8.1 Implement match-day squad selection view (`ward_tm_ward_squad_view`)
    - Gate to Ward Team Manager; present only `CountyPlayer` objects whose `WardLonglist.status = wscc_approved`
    - Enforce `SQUAD_LIMITS` per sport type: Football 24, Volleyball 14, Handball 14, Basketball 5×5 12, Basketball 3×3 8
    - On submit: record submission timestamp, lock squad from further changes within `SQUAD_SUBMISSION_HOURS_BEFORE_KICKOFF` window
    - Reject submissions exceeding the discipline's maximum and display allowed limit
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [ ]* 8.2 Write property tests for squad selection scoping and squad size limits (Properties 11 & 12)
    - **Property 11: Squad selection only allows wscc_approved players**
    - **Validates: Requirements 4.6, 5.1**
    - **Property 12: Squad size limits are enforced per discipline at all levels**
    - **Validates: Requirements 5.2, 5.5, 9.3**

- [x] 9. Checkpoint — WSCC portal and match-day squad
  - Run unit and integration tests for WSCC views and squad selection. Ensure all tests pass. Ask the user if questions arise.

- [x] 10. Sub-County Competition portal (`/portal/subcounty/`)
  - [x] 10.1 Upgrade `subcounty_officer_dashboard_view` and implement sub-county competition list/create views
    - `sc_competitions_view`: list competitions at `level=subcounty` for `sub_county = request.user.sub_county`
    - `sc_create_competition_view`: auto-set `level=subcounty` and `sub_county` from officer's profile regardless of form values submitted
    - Extended dashboard: summary of sub-county competitions
    - _Requirements: 6.1, 6.2_

  - [ ]* 10.2 Write property tests for SCSO competition queryset scoping and auto-inheritance (Properties 13 & 14)
    - **Property 13: SCSO competition queryset is scoped to their sub-county and level**
    - **Validates: Requirements 6.1, 6.4, 12.1**
    - **Property 14: New SCSO competitions auto-inherit level and sub_county**
    - **Validates: Requirements 6.2**

  - [x] 10.3 Implement sub-county competition management views (pools, fixtures, standings, live tracking)
    - `sc_competition_manage_view`: reuse existing coordinator engine scoped to sub-county competition
    - `sc_manage_pools_view`: manage pools for sub-county competition
    - `sc_generate_fixtures_view`: generate fixtures; include only `Team` records linked to the sub-county competition
    - `sc_live_match_view`: live match tracking using existing `Fixture` live-tracking fields
    - `sc_edit_standings_view`: edit standings, update `PoolTeam` standings using existing sport-specific points logic
    - _Requirements: 6.3, 6.4, 6.5, 6.7, 9.4, 9.5_

  - [ ]* 10.4 Write property test for points calculation consistency (Property 23)
    - **Property 23: Points calculation is identical for subcounty and county competitions of the same sport type**
    - **Validates: Requirements 9.4**

  - [x] 10.5 Implement cross-sub-county team block in competition team-addition logic
    - When adding a team to a sub-county competition, check `team.sub_county == competition.sub_county`; if mismatch, reject with error message and HTTP 403
    - Apply `subcounty_scope_required` decorator to all SCSO object-level views
    - Return HTTP 403 for any SCSO access to competitions/fixtures/teams/players from a different sub-county
    - _Requirements: 6.8, 12.1, 12.2_

  - [ ]* 10.6 Write property test for cross-sub-county team block (Property 15)
    - **Property 15: Cross-sub-county team addition is blocked**
    - **Validates: Requirements 6.8, 12.2**

  - [x] 10.7 Implement referee appointment for sub-county fixtures
    - Wire existing referee appointment workflow to sub-county fixture URLs
    - _Requirements: 6.6_

  - [x] 10.8 Implement sub-county qualification view (`sc_qualify_teams_view`)
    - Allow SCSO to designate qualifying teams when competition is `completed` by setting `qualified_to_county=True`
    - Link qualifying `Team` to a county-level `Competition` of the same `sport_type` and season
    - Prevent duplicate qualification (same team linked to same county competition more than once per season per discipline)
    - Display qualification badge/indicator on competition results and team-level views
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 10.9 Write property test for team qualification uniqueness (Property 22)
    - **Property 22: Team qualification uniqueness per season per discipline**
    - **Validates: Requirements 11.4**

  - [x] 10.10 Add `ActivityLog` instrumentation to all SCSO create/update/delete views
    - Use existing `ActivityLog` mechanism; create an entry for every SCSO write operation
    - _Requirements: 12.5_

  - [ ]* 10.11 Write property test for ActivityLog on SCSO writes (Property 24)
    - **Property 24: ActivityLog entry is created for every SCSO write operation**
    - **Validates: Requirements 12.5**

  - [x] 10.12 Register all `/portal/subcounty/` URL patterns
    - Add routes for dashboard, competitions CRUD, pools, fixtures, standings, live match, qualify teams, verification, promote player
    - _Requirements: 6.1–6.8, 12.1–12.5_

- [x] 11. Sub-County Player Verification
  - [x] 11.1 Wire existing 4-step verification workflow to `/portal/subcounty/verification/` URLs
    - `sc_verification_dashboard_view`: filter player list by `sub_county = request.user.sub_county` and `level = subcounty`
    - `sc_verify_player_view`: apply all four verification steps (Document, IPRS, Huduma, Higher League) to `CountyPlayer` at `level=subcounty`
    - On completion of all four steps set `verification_status = verified`; on any step failure set `verification_status = rejected` and record reason
    - _Requirements: 7.1, 7.2, 7.4, 7.6_

  - [ ]* 11.2 Write property tests for verification state machine and SCSO verification dashboard scoping (Properties 16 & 17)
    - **Property 16: Verification status transitions follow the 4-step gate sequence**
    - **Validates: Requirements 7.4, 7.5, 7.7**
    - **Property 17: SCSO verification dashboard scoping**
    - **Validates: Requirements 7.6, 12.3**

  - [x] 11.3 Implement Higher League Check flagging logic
    - When step 4 sets `higher_league_status = flagged`, block squad inclusion regardless of other step statuses
    - Require manual clearance by a Verification Officer or SCSO before the player can be added to a squad
    - _Requirements: 7.7_

  - [x] 11.4 Block unverified players from sub-county squad submissions
    - In squad submission logic, reject any player where `verification_status != verified` at sub-county level
    - _Requirements: 7.5_

- [x] 12. Player promotion — ward → sub-county → county data flow
  - [x] 12.1 Implement `sc_promote_player_view` and `promote_to_subcounty()` service function
    - Create a new `CountyPlayer` at `level=subcounty` linked to the same `national_id_number`
    - Copy identity fields: `first_name`, `last_name`, `date_of_birth`, `national_id_number`, `phone`, `photo`, `id_document`, `birth_certificate`, `huduma_number`
    - Set `source_ward_player` FK on the new record
    - Do NOT copy verification step statuses (fresh verification required at sub-county level)
    - Display ward player's current verification status and sub-county promotion indicator on Ward Team Manager view
    - _Requirements: 8.1, 8.4, 8.6_

  - [ ]* 12.2 Write property tests for player promotion identity preservation (Property 18)
    - **Property 18: Player promotion preserves identity and is level-independent**
    - **Validates: Requirements 8.1, 8.4**

  - [x] 12.3 Implement `promote_to_county()` service function (sub-county → county)
    - Create a new `CountyPlayer` at `level=county` referencing the same `national_id_number`
    - Copy identity fields and set `source_subcounty_player` FK
    - Copy sub-county verification step statuses to the county record as pre-filled values
    - County verification form shows completed steps as pre-filled, requiring only a final countersignature
    - _Requirements: 8.2, 8.5, 7.3_

  - [ ]* 12.4 Write property test for verification carry-forward to county level (Property 19)
    - **Property 19: Subcounty verification statuses carry forward to county level**
    - **Validates: Requirements 7.3, 8.2, 8.5**

  - [x] 12.5 Enforce national ID uniqueness per level and season
    - Validate at the form/service layer that `national_id_number` is unique per `(level, competition_season)` before saving
    - _Requirements: 8.3_

- [x] 13. Checkpoint — Sub-County portal and player promotion
  - Run unit and integration tests for SCSO views, verification, and promotion. Ensure all tests pass. Ask the user if questions arise.

- [x] 14. Notifications and email resilience
  - [x] 14.1 Implement all remaining email notification triggers using existing email infrastructure
    - Fixture schedule published → email to Ward Team Managers of both teams (venue, date, kick-off time)
    - Player verification status change (approved or rejected) → email to Ward Team Manager with outcome and rejection reason
    - _Requirements: 13.4, 13.5_

  - [ ]* 14.2 Write property test for email backend failure graceful degradation (Property 25)
    - **Property 25: Email backend failure does not abort user-facing request processing**
    - **Validates: Requirements 13.6**

- [x] 15. County qualification — county Competition Manager view
  - [x] 15.1 Extend county competition team registrations view to show originating sub-county for qualified teams
    - When a county Competition Manager views pending team registrations, display the originating `sub_county` for each qualified team
    - Allow manager to accept or defer the team's entry
    - _Requirements: 11.5_

- [x] 16. Discipline and squad-limit validation across all levels
  - [x] 16.1 Add discipline validation to `LigiMashinaniRegistration` form/model
    - Reject any registration submission with a `discipline` value not in the ten supported `LIGI_DISCIPLINE_CHOICES`
    - _Requirements: 9.1, 9.2_

  - [ ]* 16.2 Write property test for discipline validation (Property 26)
    - **Property 26: Discipline validation rejects unsupported sport types**
    - **Validates: Requirements 9.2**

  - [x] 16.3 Confirm `SQUAD_LIMITS` constant is centralised and referenced at both ward and sub-county squad submission points
    - Ensure `SQUAD_LIMITS` dict maps `sport_type` → max squad size and is the single source of truth for both ward and sub-county enforcement
    - _Requirements: 9.3_

- [x] 17. Final checkpoint — full pipeline integration
  - Run the full test suite (unit, property-based, integration). Ensure all migrations apply, all tests pass, no regressions in county-level functionality. Ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional property/unit tests — they can be skipped for a faster MVP but are strongly recommended to validate correctness invariants.
- All new view functions go into `mkj_cms/web_views.py` with clear section comments. No new Django apps are introduced.
- `CompetitionLevel` is defined in `competitions/models.py` and imported wherever needed across apps.
- Email notifications follow the existing try/except pattern: failure logs to `ActivityLog` and shows a `messages.warning` to the user; the primary request always completes.
- The `subcounty_scope_required` decorator is the primary access-control boundary for all SCSO views; it must be applied to every view that fetches a `Competition`, `Fixture`, `Team`, or `Player` by PK.
- Property-based tests use **Hypothesis** with a minimum of 100 iterations each (`@settings(max_examples=100)`).
- Each property test file should include a comment header: `# Feature: ligi-mashinani-subcounty-system, Property N: <title>`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3", "1.4", "1.5", "1.6", "1.7"] },
    { "id": 1, "tasks": ["1.2", "1.8"] },
    { "id": 2, "tasks": ["3.1", "4.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "4.2", "4.3", "7.1"] },
    { "id": 4, "tasks": ["4.4", "4.5", "7.2", "7.3"] },
    { "id": 5, "tasks": ["4.6", "4.7", "6.1", "6.2", "8.1"] },
    { "id": 6, "tasks": ["6.3", "6.4", "6.5", "6.6", "8.2"] },
    { "id": 7, "tasks": ["10.1", "11.1", "12.1", "16.1"] },
    { "id": 8, "tasks": ["10.2", "10.3", "11.2", "12.2", "16.2", "16.3"] },
    { "id": 9, "tasks": ["10.4", "10.5", "11.3", "11.4", "12.3"] },
    { "id": 10, "tasks": ["10.6", "10.7", "10.8", "12.4", "12.5"] },
    { "id": 11, "tasks": ["10.9", "10.10", "10.11", "14.1"] },
    { "id": 12, "tasks": ["10.12", "14.2", "15.1"] }
  ]
}
```
