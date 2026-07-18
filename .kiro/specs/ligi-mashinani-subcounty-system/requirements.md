# Requirements Document

## Introduction

This document defines requirements for the **Ligi Mashinani → Sub-County MKJ Finals → County MKJ Supa Cup Finals** grassroots-to-finals competition pipeline in the MKJ SUPA CUP Django system for Makueni County, Kenya.

The pipeline has three levels:

- **Level 1  -  Ligi Mashinani (Ward Level):** Ward team managers register their teams and players. A Ward Sports Council Chairperson approves longlists. The team manager/coach selects match-day squads per discipline and gender.
- **Level 2  -  Sub-County MKJ Finals:** Ward teams that qualify compete within one of Makueni's six sub-counties (Makueni, Kibwezi West, Kibwezi East, Kaiti, Kilome, Mbooni). A Sub-County Sports Officer manages fixtures, pools, knockout stages, and player verification using the same competition engine as the county finals.
- **Level 3  -  MKJ Supa Cup County Finals:** The best teams from sub-county finals qualify for the existing county finals (already built).

The system reuses existing models  -  `Competition`, `Fixture`, `Pool`, `PoolTeam`, `Team`, `Player`, `CountyPlayer`, `CountyDiscipline`, and `CountyRegistration`  -  by introducing a `level` field (`ward` / `subcounty` / `county`) rather than building parallel model families.

---

## Glossary

- **System:** The MKJ SUPA CUP Django web application.
- **Ward_Team_Manager:** A `TEAM_MANAGER`-role user linked to a `LigiMashinaniRegistration`; manages a ward team's player longlist and match-day squads.
- **Ward_Sports_Council_Chair (WSCC):** New user role; reviews and approves ward team longlists per discipline. One WSCC is assigned per ward.
- **Sub_County_Sports_Officer (SCSO):** Existing `subcounty_sports_officer`-role user; manages sub-county competitions, fixtures, standings, and player verification for their assigned sub-county.
- **Verification_Officer:** Existing role; performs the 4-step player verification at sub-county and county level.
- **Longlist:** The full register of players submitted by a Ward_Team_Manager for a given discipline, pending WSCC approval.
- **Match_Day_Squad:** A subset of the approved longlist selected for a specific fixture; subject to squad size limits per discipline.
- **Competition_Level:** A string field added to `Competition` with values `ward`, `subcounty`, or `county`; scopes all related objects to their level.
- **LigiMashinaniRegistration:** Existing model capturing a ward team manager's pre-registration from the public homepage.
- **CountyPlayer:** Existing model storing a player in a `CountyDiscipline`; reused at all three levels.
- **CountyDiscipline:** Existing model scoping players and bench members to a sport type; reused at all three levels.
- **IPRS:** Integrated Population Registration System  -  used for age and identity verification.
- **Huduma:** Huduma Kenya  -  identity cross-check step in the 4-step verification workflow.
- **Sub-county:** One of the six Makueni sub-counties: Makueni, Kibwezi West, Kibwezi East, Kaiti, Kilome, Mbooni.
- **Ward:** An IEBC-defined administrative division within a sub-county (sourced from `MAKUENI_SUBCOUNTY_WARDS`).
- **Discipline:** One of the ten competitive sport types: Football Men, Football Women, Volleyball Men, Volleyball Women, Basketball 5×5 Men, Basketball 5×5 Women, Basketball 3×3 Men, Basketball 3×3 Women, Handball Men, Handball Women.

---

## Requirements

### Requirement 1: Competition Level Model Extension

**User Story:** As a system admin, I want competitions, teams, and registrations to carry a level tag (`ward`, `subcounty`, `county`), so that all portal views and rules are correctly scoped without duplicating model families.

#### Acceptance Criteria

1. THE System SHALL add a `level` field with choices `ward`, `subcounty`, `county` to the `Competition` model, defaulting to `county` so all existing data is unaffected.
2. WHEN a new `Competition` is created with `level = subcounty`, THE System SHALL require an associated `sub_county` value drawn from `MakueniSubCounty` choices.
3. WHEN a new `Competition` is created with `level = ward`, THE System SHALL require both a `sub_county` value and a `ward` value drawn from `MAKUENI_SUBCOUNTY_WARDS`.
4. THE System SHALL add a `level` field to the `CountyRegistration` model with the same three choices, defaulting to `county`.
5. THE System SHALL add a `level` field to the `CountyDiscipline` model with the same three choices, defaulting to `county`.
6. WHEN `level = county`, THE System SHALL enforce all existing county-level validation rules unchanged.
7. IF a `Competition` is created with `level = subcounty` but no `sub_county` value is provided, THEN THE System SHALL reject the save, return a validation error message identifying the `sub_county` field as required, and leave the `Competition` record unsaved.

---

### Requirement 2: Ward Team Manager Onboarding

**User Story:** As a Ward_Team_Manager whose `LigiMashinaniRegistration` has been approved, I want a portal account created automatically, so that I can log in and manage my ward team.

#### Acceptance Criteria

1. WHEN a `LigiMashinaniRegistration` is set to `approved` status by an admin, THE System SHALL automatically create a `User` account with `role = TEAM_MANAGER`, setting `sub_county` and `ward` fields from the registration.
2. WHEN a `User` account is created from a `LigiMashinaniRegistration`, THE System SHALL set `must_change_password = True` and send login credentials to the manager's registered email address.
3. WHEN a `LigiMashinaniRegistration` is approved, THE System SHALL atomically create the `User` account, the `CountyDiscipline` at `level = ward` (if it does not already exist), and the linked `Team` record with `status = registered` in a single database transaction; if any step fails, all changes SHALL be rolled back and the registration status SHALL revert to `pending`.
4. IF the atomic account-creation transaction fails, THEN THE System SHALL set the `LigiMashinaniRegistration` status back to `pending`, log the error to the `ActivityLog`, and display an error notice to the admin so the record can be re-approved once the issue is resolved.
5. WHEN a `Ward_Team_Manager` logs into the portal, THE System SHALL redirect them to a ward team manager dashboard showing their ward, sub-county, discipline, and a summary of their player longlist status.
6. IF a `LigiMashinaniRegistration` is set to `rejected` status, THEN THE System SHALL send a rejection notification to the manager's registered email including the rejection reason.

---

### Requirement 3: Player Longlist Management (Ward Level)

**User Story:** As a Ward_Team_Manager, I want to build and manage a player longlist for my ward team, so that my players can be reviewed and approved for competition.

#### Acceptance Criteria

1. WHEN a Ward_Team_Manager accesses the player longlist page, THE System SHALL display all players registered under their ward's `CountyDiscipline` at `level = ward`.
2. WHEN a Ward_Team_Manager adds a player, THE System SHALL require: full name (as on ID or birth certificate), national ID number or birth certificate number, date of birth, passport photo, and at least one identity document (national ID copy or birth certificate copy).
3. WHEN a player's date of birth is saved, THE System SHALL automatically calculate and store the player's age in years relative to the current date.
4. WHEN a Ward_Team_Manager submits a player with a national ID number that already exists in the system, THE System SHALL reject the submission and display an error identifying the duplicate.
5. WHEN a Ward_Team_Manager has added at least one player, THE System SHALL allow them to submit the longlist to the Ward_Sports_Council_Chair for review.
6. WHEN a longlist is submitted, THE System SHALL set its status to `submitted` and prevent further additions or edits to that longlist until the WSCC returns it.
7. IF a Ward_Team_Manager attempts to submit an empty longlist (zero players), THEN THE System SHALL prevent submission and display a validation message.
8. WHEN a Ward_Sports_Council_Chair returns a longlist with a reason, THE System SHALL set the longlist status back to `draft` and notify the Ward_Team_Manager by email with the reason provided.

---

### Requirement 4: Ward Sports Council Chairperson (WSCC) Role

**User Story:** As a Ward_Sports_Council_Chair, I want to review and approve ward team longlists, so that only eligible players proceed to sub-county competitions.

#### Acceptance Criteria

1. THE System SHALL add `ward_sports_council_chair` as a new `UserRole` value, with display name "Ward Sports Council Chair".
2. WHEN a WSCC logs into the portal, THE System SHALL display a dashboard showing all submitted longlists for wards within their assigned sub-county.
3. WHEN a WSCC approves a longlist, THE System SHALL set the longlist status to `wscc_approved` and notify the Ward_Team_Manager by email.
4. WHEN a WSCC rejects or returns a longlist, THE System SHALL require a written reason and set the longlist status back to `draft`, notifying the Ward_Team_Manager.
5. WHEN a WSCC views a player record, THE System SHALL display all identity document images, the calculated age, and the player's full name as submitted.
6. THE System SHALL prevent a Ward_Team_Manager from selecting a player for a match-day squad if that player's longlist has not reached `wscc_approved` status.
7. WHILE a longlist status is `wscc_approved`, THE System SHALL prevent the Ward_Team_Manager from adding, editing, or removing players from that longlist without first requesting an unlock.

---

### Requirement 5: Match-Day Squad Selection (Ward Level)

**User Story:** As a Ward_Team_Manager, I want to select a match-day squad from my WSCC-approved longlist for each fixture, so that only registered and approved players can participate.

#### Acceptance Criteria

1. WHEN a Ward_Team_Manager selects a match-day squad for a fixture, THE System SHALL only present players whose longlist status is `wscc_approved`.
2. THE System SHALL enforce the following maximum squad sizes per discipline: Football 24, Volleyball 14, Handball 14, Basketball 5×5 12, Basketball 3×3 8.
3. WHEN a Ward_Team_Manager submits a match-day squad, THE System SHALL record the submission timestamp and lock the squad from further changes within the deadline window defined by `SQUAD_SUBMISSION_HOURS_BEFORE_KICKOFF`.
4. WHEN a coordinator or SCSO views the fixture, THE System SHALL display the submitted match-day squad for each team.
5. IF a Ward_Team_Manager attempts to submit a squad that exceeds the discipline's maximum size, THEN THE System SHALL reject the submission and display the allowed limit.

---

### Requirement 6: Sub-County Competition Management

**User Story:** As a Sub_County_Sports_Officer, I want to manage fixtures, pools, knockout stages, and standings for my sub-county's competition, so that I can run the sub-county MKJ Finals using the same tools as the county finals.

#### Acceptance Criteria

1. WHEN a Sub_County_Sports_Officer accesses their portal, THE System SHALL display only competitions whose `level = subcounty` and `sub_county` matches the officer's assigned `sub_county`.
2. WHEN a Sub_County_Sports_Officer creates a competition, THE System SHALL set `level = subcounty` and `sub_county` automatically from the officer's profile, using the existing `Competition` model.
3. THE System SHALL allow a Sub_County_Sports_Officer to create pools, generate fixtures (group stage and/or knockout), manage standings, and record match reports using the existing competition engine with no parallel model families.
4. WHEN a Sub_County_Sports_Officer generates fixtures, THE System SHALL only include `Team` records whose `Competition` link points to the relevant sub-county competition.
5. WHEN a Sub_County_Sports_Officer records a match result, THE System SHALL update `PoolTeam` standings using the existing sport-specific points calculation logic.
6. THE Sub_County_Sports_Officer SHALL be able to appoint referees to sub-county fixtures using the existing referee appointment workflow.
7. WHEN a Sub_County_Sports_Officer views live match tracking, THE System SHALL show score, match minute, and period label using the existing `Fixture` live-tracking fields.
8. IF a Sub_County_Sports_Officer attempts to add a team to a sub-county competition that belongs to a different sub-county, THEN THE System SHALL block the addition entirely and display a sub-county mismatch error.

---

### Requirement 7: Sub-County Player Verification

**User Story:** As a Verification_Officer assigned to a sub-county, I want to verify ward players using the same 4-step workflow as county level, so that player eligibility is consistently enforced.

#### Acceptance Criteria

1. THE System SHALL apply the existing 4-step verification workflow (Step 1: Document Verification; Step 2: IPRS Age Verification; Step 3: Huduma Kenya Check; Step 4: Higher League Check) to players at `level = subcounty`.
2. WHEN a Verification_Officer completes all four verification steps for a player at sub-county level, THE System SHALL set `verification_status = verified` on that player's `CountyPlayer` record.
3. WHEN a player's `verification_status` is `verified` at sub-county level, THE System SHALL allow the player's verification status to carry forward to county level without re-performing steps already completed.
4. WHEN a player fails any verification step, THE System SHALL set `verification_status = rejected` and record the rejection reason on the `CountyPlayer` record.
5. THE System SHALL prevent a player with `verification_status != verified` at sub-county level from being included in any sub-county match-day squad submission.
6. WHEN a Sub_County_Sports_Officer views the player verification dashboard, THE System SHALL filter the player list by `sub_county = request.user.sub_county` and `level = subcounty` every time the dashboard is viewed, regardless of whether sub-county-level players are currently present.
7. IF a player is flagged in the Higher League Check step, THEN THE System SHALL set `higher_league_status = flagged` and require a Verification_Officer or SCSO to manually clear or reject the player before the player can be included in a squad.

---

### Requirement 8: Data Flow  -  Ward → Sub-County → County

**User Story:** As a Sub_County_Sports_Officer and as a county Competition_Manager, I want player records and verification statuses to carry upward through the pipeline, so that players do not need to re-register or repeat completed verification steps at each level.

#### Acceptance Criteria

1. WHEN a ward player is promoted to sub-county level, THE System SHALL create a linked `CountyPlayer` record at `level = subcounty` referencing the same player identity (matched by national ID number), preserving all previously captured document images and identity fields.
2. WHEN a sub-county player qualifies for county level, THE System SHALL create a linked `CountyPlayer` record at `level = county` referencing the same player identity, carrying forward the verification step statuses already completed at sub-county level.
3. THE System SHALL ensure a player's national ID number is unique across all `CountyPlayer` records at the same competition level within the same competition season.
4. THE System SHALL ensure that each player snapshot at every level maintains completely independent data; no sync option between levels is provided, and updates at one level never propagate to another.
5. WHEN a county Verification_Officer views a county-level player whose sub-county verification is fully complete, THE System SHALL display the previously completed verification steps as pre-filled, requiring only a final countersignature rather than repeating all steps.
6. WHEN a Ward_Team_Manager views their team's player list, THE System SHALL display the player's current verification status at ward level and indicate whether the player has been promoted to sub-county level.

---

### Requirement 9: All Disciplines and Gender Categories

**User Story:** As a competition organiser, I want the grassroots pipeline to support all ten competitive disciplines across both genders, so that every sport benefits from the same structured pathway.

#### Acceptance Criteria

1. THE System SHALL support the following ten disciplines at all three competition levels: Football Men, Football Women, Volleyball Men, Volleyball Women, Basketball 5×5 Men, Basketball 5×5 Women, Basketball 3×3 Men, Basketball 3×3 Women, Handball Men, Handball Women.
2. WHEN a `LigiMashinaniRegistration` is submitted, THE System SHALL validate the discipline against the ten supported values and reject any submission with an unsupported discipline.
3. WHEN squad size limits are enforced, THE System SHALL apply discipline-specific limits (Football: 24, Volleyball: 14, Handball: 14, Basketball 5×5: 12, Basketball 3×3: 8) consistently across ward and sub-county levels.
4. WHEN standings points are calculated for a sub-county competition, THE System SHALL apply the same sport-family rules as county finals: Football W×3+D×1, Handball W×2+D×1, Volleyball FIVB bonus points, Basketball FIBA bonus points.
5. WHEN a Sub_County_Sports_Officer creates a competition for a discipline, THE System SHALL set the `sport_type` field on the `Competition` record using the existing `SportType` choices without modification.

---

### Requirement 10: Ward Sports Council Chairperson Management

**User Story:** As a system admin, I want to create and assign WSCC accounts to specific wards, so that each ward has a designated authority to approve player longlists.

#### Acceptance Criteria

1. THE System SHALL allow an admin to create a `User` with `role = ward_sports_council_chair` and assign them to a specific `ward` and `sub_county`.
2. WHEN a WSCC is created, THE System SHALL enforce that only one active WSCC exists per ward at any given time.
3. WHEN a WSCC account is deactivated (`is_active = False`), THE System SHALL not automatically transfer pending longlist reviews; the admin must assign a replacement WSCC before outstanding reviews can be actioned. THE System SHALL only permit manual reassignment of pending reviews after a WSCC deactivation event; reassignment of reviews is not permitted while the original WSCC remains active.
4. THE System SHALL display in the admin panel the WSCC's assigned ward, sub-county, and a count of pending longlist reviews awaiting their action.
5. WHEN a WSCC's assigned ward is changed, THE System SHALL revoke access to longlists from the previous ward and grant access only to longlists from the newly assigned ward.

---

### Requirement 11: Sub-County to County Qualification

**User Story:** As a Sub_County_Sports_Officer and as a county Competition_Manager, I want to record which teams and players qualify from sub-county finals to the county finals, so that the county competition can be seeded with legitimate qualifiers.

#### Acceptance Criteria

1. WHEN a sub-county competition is marked `completed`, THE System SHALL allow the Sub_County_Sports_Officer to designate qualifying teams per discipline by marking them with a `qualified_to_county = True` flag.
2. WHEN a team is designated as a qualifier, THE System SHALL link the qualifying `Team` record to a county-level `Competition` of the same `sport_type` and season.
3. WHEN a Ward_Team_Manager or SCSO views the competition results page, THE System SHALL display the final standings and show a qualification indicator (e.g. a "Qualified" badge) next to each team that has been designated as a qualifier; qualification indicators SHALL also be visible on team-level views independently of the full standings table.
4. THE System SHALL prevent the same team from being linked to a county competition more than once per season per discipline.
5. WHEN a county Competition_Manager views pending team registrations, THE System SHALL display the originating sub-county for each qualified team, allowing the manager to accept or defer the team's entry.

---

### Requirement 12: Sub-County Officer Portal Scoping

**User Story:** As a Sub_County_Sports_Officer, I want my portal to be scoped entirely to my assigned sub-county, so that I cannot accidentally view or modify another sub-county's data.

#### Acceptance Criteria

1. WHEN a Sub_County_Sports_Officer accesses any portal view, THE System SHALL filter all querysets by `sub_county = request.user.sub_county` before rendering.
2. THE System SHALL return HTTP 403 if a Sub_County_Sports_Officer attempts to access a URL for a competition, fixture, team, or player that belongs to a different sub-county.
3. WHEN a Sub_County_Sports_Officer views the player verification dashboard, THE System SHALL display only players from `CountyDiscipline` records where `sub_county` matches the officer's assigned sub-county and `level = subcounty`.
4. WHEN a Sub_County_Sports_Officer views the standings page, THE System SHALL only display standings for pools within competitions scoped to the officer's sub-county.
5. THE System SHALL log an activity record whenever a Sub_County_Sports_Officer makes a create, update, or delete action, using the existing `ActivityLog` mechanism.

---

### Requirement 13: Notifications and Communications

**User Story:** As a Ward_Team_Manager, WSCC, and SCSO, I want timely email notifications for key lifecycle events, so that I can act promptly without polling the portal.

#### Acceptance Criteria

1. WHEN a Ward_Team_Manager submits a longlist, THE System SHALL send an email notification to the assigned WSCC for the ward indicating that a new longlist is awaiting review.
2. WHEN a WSCC approves a longlist, THE System SHALL send an email to the Ward_Team_Manager confirming approval and instructing them to prepare match-day squads.
3. WHEN a WSCC returns a longlist for correction, THE System SHALL send an email to the Ward_Team_Manager containing the WSCC's written reason.
4. WHEN a Sub_County_Sports_Officer publishes a fixture schedule, THE System SHALL send email notifications to the Ward_Team_Managers of both participating teams including the venue, date, and kick-off time.
5. WHEN a player's verification status changes (approved or rejected), THE System SHALL send an email to the Ward_Team_Manager of the player's team indicating the outcome and, in the case of rejection, the reason.
6. IF the email backend is unavailable when a notification is triggered, THEN THE System SHALL log the failure to the existing `ActivityLog`, schedule a retry on the next task run, display a non-blocking warning to the user indicating the notification could not be sent immediately, and continue processing the user's request normally.

