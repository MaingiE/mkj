"""
MKJ SUPA CUP CMS - Root URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from teams.verification_views import (
    player_clearance_dashboard as _clearance_dashboard,
    player_clearance_detail as _clearance_detail,
    huduma_verify_player as _huduma_verify,
    fifa_connect_check_player as _fifa_connect_check,
    player_final_clearance as _final_clearance,
    player_verification_logs as _verification_logs,
    bulk_huduma_check as _bulk_huduma,
    bulk_fifa_connect_check as _bulk_fifa,
    api_fifa_connect_quick_check as _api_fifa_quick,
    api_iprs_lookup as _api_iprs_lookup,
)

from news_media.portal_views import (
    media_dashboard_view,
    article_list_view as media_article_list_view,
    article_create_view as media_article_create_view,
    article_edit_view as media_article_edit_view,
    article_delete_view as media_article_delete_view,
    category_manage_view as media_category_manage_view,
    category_delete_view as media_category_delete_view,
    album_list_view as media_album_list_view,
    album_create_view as media_album_create_view,
    album_edit_view as media_album_edit_view,
    album_delete_view as media_album_delete_view,
    photo_delete_view as media_photo_delete_view,
    video_list_view as media_video_list_view,
    video_create_view as media_video_create_view,
    video_edit_view as media_video_edit_view,
    video_delete_view as media_video_delete_view,
)

from .web_views import (
    # Public website
    home_view, about_view, public_competitions_view,
    public_fixtures_results_view,
    public_competition_detail_view, public_results_view,
    public_statistics_view, public_competition_standings_view,
    public_live_matches_view, public_live_matches_page_view,
    contact_view, public_gallery_view,
    # SEO
    robots_txt_view, sitemap_xml_view,
    # CMS portal
    web_login_view, web_logout_view, dashboard_view,
    force_change_password_view,
    competitions_list_view, competition_detail_view,
    teams_list_view, team_detail_view,
    referees_list_view,
    matches_list_view,
    profile_view, change_password_view,
    # Player management
    add_player_view, edit_player_view, delete_player_view,
    # Admin approval
    pending_teams_view, pending_referees_view,
    # Player verification
    player_verification_list_view, verify_player_view,
    # Squad selection & approval
    squad_select_view, squad_review_list_view, squad_review_view,
    substitution_request_view, substitution_approve_view, substitution_match_list_view,
    # Match reporting
    match_report_form_view, match_report_detail_view, match_report_review_view,
    # Referee appointments & portal
    appointment_action_view,
    referee_dashboard_view, referee_edit_profile_view,
    # Appointment management
    referee_appointments_view, referee_appoint_view,
    # Treasurer portal
    treasurer_dashboard_view,
    treasurer_teams_view,
    treasurer_county_payments_view,
    # Competition Manager specific views
    competition_standings_view,
    competition_reports_view,
    competition_report_approve_view,
    # Competition Manager - full portal
    cm_dashboard_view,
    cm_create_competition_view,
    cm_edit_competition_view,
    cm_competition_manage_view,
    cm_manage_pools_view,
    cm_generate_fixtures_view,
    cm_manage_venues_view,
    cm_allocate_venue_view,
    cm_edit_standings_view,
    cm_edit_fixture_view,
    cm_delete_fixture_view,
    cm_competition_rules_view,
    # Shared subcounty views (bench, delegation, verification, kit)
    county_admin_add_bench_member_view,
    county_admin_delete_bench_member_view,
    county_admin_kit_colors_view,
    county_admin_delegation_members_view,
    county_admin_delete_delegation_member_view,
    county_admin_verification_view,
    # Discipline Coordinator portal
    coordinator_dashboard_view,
    coordinator_competitions_view,
    coordinator_create_competition_view,
    coordinator_edit_competition_view,
    coordinator_competition_manage_view,
    coordinator_manage_pools_view,
    coordinator_generate_fixtures_view,
    coordinator_venues_view,
    coordinator_allocate_venue_view,
    coordinator_edit_fixture_view,
    coordinator_create_fixture_view,
    coordinator_delete_fixture_view,
    coordinator_reschedule_fixture_view,
    coordinator_live_match_view,
    coordinator_generate_semis_view,
    coordinator_edit_standings_view,
    coordinator_match_reports_view,
    coordinator_squads_view,
    coordinator_fixture_squads_view,
    coordinator_statistics_view,
    coordinator_referees_view,
    coordinator_appointments_view,
    coordinator_competition_rules_view,
    # Player profile
    player_profile_view,
    # Team Manager portal
    team_manager_dashboard_view,
    team_manager_match_squad_view,
    team_manager_opponent_view,
    team_manager_sanctions_view,
    team_manager_file_appeal_view,
    # PDF download
    team_list_pdf_view,
    # Secretary General portal
    sg_dashboard_view,
    sg_verifications_view,
    sg_appeals_view,
    sg_treasurer_actions_view,
    sg_user_actions_view,
    sg_exceptional_overrides_view,
    sg_verified_players_view,
    cec_sports_portal_view,
    # Scout portal
    scout_dashboard_view,
    scout_players_view,
    scout_shortlist_view,
    scout_submit_shortlist_view,
    scout_request_shortlist_edit_view,
    scout_add_to_shortlist_view,
    scout_edit_shortlist_view,
    scout_remove_from_shortlist_view,
    # Scout scouting portal (live matches, evaluation, reports)
    scout_live_matches_view,
    scout_match_squad_view,
    scout_evaluate_player_view,
    scout_reports_view,
    scout_report_detail_view,
    # Leadership scouting reports
    leadership_scout_reports_view,
    leadership_scout_report_detail_view,
    # New MKJ SUPA CUP portals
    subcounty_officer_dashboard_view,
    subcounty_officer_disciplines_view,
    subcounty_officer_discipline_players_view,
    subcounty_officer_add_player_view,
    subcounty_officer_delete_player_view,
    subcounty_officer_referees_view,
    # Sub-county competition management (Tasks 10.1, 10.3, 10.5, 10.7, 10.8, 10.12)
    sc_competitions_view,
    sc_create_competition_view,
    sc_competition_manage_view,
    sc_manage_pools_view,
    sc_generate_fixtures_view,
    sc_live_match_view,
    sc_edit_standings_view,
    sc_appoint_referee_view,
    sc_qualify_teams_view,
    sc_verification_dashboard_view,
    sc_verify_player_view,
    sc_promote_player_view,
    director_sports_dashboard_view,
    chief_officer_sports_dashboard_view,
    chief_sports_officer_dashboard_view,
    governor_dashboard_view,
    waziri_sports_dashboard_view,
    # Verification Officer portal
    vo_dashboard_view,
    vo_verify_county_player_view,
    vo_players_by_subcounty_view,
    # Verified player lists
    subcounty_verified_players_view,
    team_manager_verified_players_view,
    director_sports_verified_players_view,
    director_sports_approve_player_view,
    director_sports_disapprove_player_view,
    director_sports_bulk_approve_view,
    director_sports_lock_list_view,
    director_sports_unlock_list_view,
    director_sports_shortlist_requests_view,
    director_sports_review_shortlist_request_view,
    director_sports_audit_view,
    director_sports_system_users_view,
    director_sports_delegations_view,
    director_sports_technical_bench_view,
    verified_players_pdf_view,
    # Bulk upload
    cso_bulk_upload_list_view,
    cso_bulk_upload_view,
    cso_bulk_upload_detail_view,
    cso_bulk_upload_edit_row_view,
    cso_bulk_upload_delete_view,
    director_bulk_upload_list_view,
    director_bulk_upload_review_view,
    # Coordinator bulk upload & team manager
    coordinator_bulk_upload_list_view,
    coordinator_bulk_upload_view,
    coordinator_bulk_upload_detail_view,
    coordinator_bulk_upload_delete_view,
    coordinator_assign_team_manager_view,
    cso_approve_coordinator_upload_view,
    ds_approve_coordinator_upload_view,
    edit_county_player_view,
    # Match day squad PDF
    match_squad_pdf_view,
    # Ligi Mashinani: Ward Team Manager portal
    ward_tm_dashboard_view,
    ward_tm_longlist_view,
    ward_tm_add_player_view,
    ward_tm_edit_player_view,
    ward_tm_delete_player_view,
    ward_tm_submit_longlist_view,
    ward_tm_fixtures_view,
    ward_tm_ward_squad_view,
    # Ligi Mashinani: Ward Sports Council Chair (WSCC) portal
    wscc_dashboard_view,
    wscc_longlists_view,
    wscc_longlist_detail_view,
    wscc_approve_longlist_view,
    wscc_return_longlist_view,
    # Ligi Mashinani: Admin registration management portal
    ligi_registrations_list_view,
    ligi_registration_detail_view,
    ligi_registration_approve_view,
    ligi_registration_reject_view,
    ligi_registration_ward_verify_view,
    # Ligi Mashinani: Settings / Window Control
    ligi_settings_view,
    # Ligi Mashinani: Transfer system
    ward_tm_transfers_view,
    ward_tm_request_transfer_view,
    ward_tm_withdraw_transfer_view,
    wscc_transfers_view,
    wscc_transfer_action_view,
    scso_transfers_view,
    scso_transfer_action_view,
    # Ligi Mashinani: Player Register (read-only, all roles)
    ligi_player_register_view,
    # Ligi Mashinani: Ward substitution system
    ward_tm_substitution_view,
    ward_sub_approve_view,
    # Ligi Mashinani: WSCC Ward Competition Engine
    wscc_ward_competition_setup_view,
    wscc_ward_comp_manage_view,
    wscc_ward_comp_pools_view,
    wscc_ward_comp_generate_fixtures_view,
    wscc_ward_match_sheet_view,
    # Ligi Mashinani: Senior transfers (CSO/Director/Admin)
    senior_transfers_view,
    senior_transfer_action_view,
    # Ligi Mashinani: Transfer tracking (Director of Sports)
    transfer_tracking_dashboard_view,
)

from teams.ligi_views import ligi_register_view

urlpatterns = [
    # ── HEALTHCHECK (Railway internal probe — must return 200, no redirects) ──
    path("health/", lambda request: __import__('django.http', fromlist=['HttpResponse']).HttpResponse("ok"), name="healthcheck"),

    # ── PUBLIC WEBSITE ────────────────────────────────────────────────────────
    path("robots.txt",                    robots_txt_view,                name="robots_txt"),
    path("ligi/register/",               ligi_register_view,             name="ligi_register"),
    path("ligi/dashboard/",              ward_tm_dashboard_view,         name="ward_tm_dashboard"),
    path("ligi/longlist/",               ward_tm_longlist_view,          name="ward_tm_longlist"),
    path("ligi/longlist/add-player/",    ward_tm_add_player_view,        name="ward_tm_add_player"),
    path("ligi/longlist/<int:player_pk>/edit/",   ward_tm_edit_player_view,   name="ward_tm_edit_player"),
    path("ligi/longlist/<int:player_pk>/delete/", ward_tm_delete_player_view, name="ward_tm_delete_player"),
    path("ligi/longlist/submit/",                 ward_tm_submit_longlist_view, name="ward_tm_submit_longlist"),
    # ── LIGI MASHINANI: Ward Team Manager — fixtures & squad selection ──────
    path("ligi/fixtures/",                                  ward_tm_fixtures_view,        name="ward_tm_fixtures"),
    path("ligi/fixtures/<int:fixture_pk>/squad/",           ward_tm_ward_squad_view,      name="ward_tm_ward_squad"),
    # ── LIGI MASHINANI: Ward Sports Council Chair (WSCC) portal ─────────────
    path("ligi/wscc/dashboard/",                            wscc_dashboard_view,           name="wscc_dashboard"),
    path("ligi/wscc/longlists/",                            wscc_longlists_view,           name="wscc_longlists"),
    path("ligi/wscc/longlists/<int:longlist_pk>/",          wscc_longlist_detail_view,     name="wscc_longlist_detail"),
    path("ligi/wscc/longlists/<int:longlist_pk>/approve/",  wscc_approve_longlist_view,    name="wscc_approve_longlist"),
    path("ligi/wscc/longlists/<int:longlist_pk>/return/",   wscc_return_longlist_view,     name="wscc_return_longlist"),
    path("sitemap.xml",                   sitemap_xml_view,               name="sitemap_xml"),
    path("",                              home_view,                      name="home"),
    path("about/",                        about_view,                     name="about"),
    path("fixtures/",                     public_fixtures_results_view,   name="public_fixtures_results"),
    path("competitions/public/",          public_fixtures_results_view,   name="public_competitions"),
    path("competitions/public/<int:pk>/", public_competition_detail_view, name="public_competition_detail"),
    path("results/",                      public_results_view,            name="public_results"),
    path("statistics/",                    public_statistics_view,         name="public_statistics"),
    path("results/statistics/",            public_statistics_view,         name="public_statistics_legacy"),
    path("results/competitions/<int:pk>/standings/", public_competition_standings_view, name="public_competition_standings"),
    path("contact/",                      contact_view,                   name="contact"),
    path("gallery/",                      public_gallery_view,            name="public_gallery"),
    path("live/",                         public_live_matches_page_view,  name="public_live_matches"),
    path("api/live-matches/",             public_live_matches_view,       name="public_live_matches_api"),

    # ── NEWS & MEDIA ──────────────────────────────────────────────────────────
    path("media-hub/", include("news_media.urls")),

    # ── CMS PORTAL (Authenticated) ───────────────────────────────────────────
    path("portal/login/",                   web_login_view,         name="web_login"),
    path("portal/logout/",                  web_logout_view,        name="web_logout"),
    path("portal/force-change-password/",   force_change_password_view, name="force_change_password"),
    path("portal/",                         dashboard_view,         name="dashboard"),
    path("portal/competitions/",            competitions_list_view, name="competitions_list"),
    path("portal/competitions/<int:pk>/",   competition_detail_view, name="competition_detail"),
    path("portal/teams/",                   teams_list_view,        name="teams_list"),
    path("portal/teams/<int:pk>/",          team_detail_view,       name="team_detail"),
    path("portal/teams/<int:team_pk>/add-player/", add_player_view,  name="add_player"),
    path("portal/players/<int:player_pk>/edit/",    edit_player_view, name="edit_player"),
    path("portal/players/<int:player_pk>/delete/",  delete_player_view, name="delete_player"),
    path("portal/referees/",                referees_list_view,     name="referees_list"),
    path("portal/matches/",                 matches_list_view,      name="matches_list"),
    path("portal/profile/",                 profile_view,           name="web_profile"),
    path("portal/profile/change-password/", change_password_view,  name="web_change_password"),

    # ── PORTAL: APPROVAL WORKFLOWS ───────────────────────────────────────────
    path("portal/teams/pending/",    pending_teams_view,    name="pending_teams"),
    path("portal/referees/pending/", pending_referees_view, name="pending_referees"),
    # ── PORTAL: PLAYER VERIFICATION ─────────────────────────────────────
    path("portal/players/verification/",              player_verification_list_view, name="player_verification_list"),
    path("portal/players/<int:player_pk>/verify/",    verify_player_view,            name="verify_player"),

    # ── PORTAL: PLAYER CLEARANCE (Huduma Kenya + FIFA Connect) ────────────
    path("portal/players/clearance/",                             _clearance_dashboard,       name="player_clearance_dashboard"),
    path("portal/players/<int:player_pk>/clearance/",             _clearance_detail,          name="player_clearance_detail"),
    path("portal/players/<int:player_pk>/huduma-verify/",         _huduma_verify,             name="huduma_verify_player"),
    path("portal/players/<int:player_pk>/fifa-connect-check/",    _fifa_connect_check,        name="fifa_connect_check_player"),
    path("portal/players/<int:player_pk>/final-clearance/",       _final_clearance,           name="player_final_clearance"),
    path("portal/players/<int:player_pk>/verification-logs/",     _verification_logs,         name="player_verification_logs"),
    path("portal/players/bulk-huduma-check/",                     _bulk_huduma,               name="bulk_huduma_check"),
    path("portal/players/bulk-fifa-connect-check/",               _bulk_fifa,                 name="bulk_fifa_connect_check"),
    path("api/v1/fifa-connect/quick-check/",                      _api_fifa_quick,            name="api_fifa_connect_quick_check"),
    path("api/v1/iprs/lookup/",                                   _api_iprs_lookup,           name="api_iprs_lookup"),

    # ── PORTAL: SQUAD SELECTION & APPROVAL ────────────────────────────────
    path("portal/fixtures/<int:fixture_pk>/squad/",       squad_select_view,      name="squad_select"),
    path("portal/squads/review/",                         squad_review_list_view,  name="squad_review_list"),
    path("portal/squads/<int:squad_pk>/review/",          squad_review_view,       name="squad_review"),

    # ── PORTAL: MATCH REPORTS ─────────────────────────────────────────────
    path("portal/fixtures/<int:fixture_pk>/report/",      match_report_form_view,    name="match_report_form"),
    path("portal/reports/<int:report_pk>/",               match_report_detail_view,  name="match_report_detail"),
    path("portal/reports/<int:report_pk>/review/",        match_report_review_view,  name="match_report_review"),

    # ── PORTAL: REFEREE APPOINTMENTS ──────────────────────────────────────
    path("portal/appointments/<int:appointment_pk>/",     appointment_action_view,    name="appointment_action"),

    # ── PORTAL: ADMIN APPOINTMENT MANAGEMENT ─────────────────────────────
    path("portal/admin/referee-appointments/",                    referee_appointments_view, name="referee_appointments"),
    path("portal/admin/referee-appointments/<int:fixture_pk>/",   referee_appoint_view,      name="referee_appoint"),

    # ── PORTAL: REFEREE DASHBOARD & PROFILE ──────────────────────────────
    path("portal/referee/",                               referee_dashboard_view,     name="referee_portal"),
    path("portal/referee/profile/",                       referee_edit_profile_view,  name="referee_edit_profile"),

    # ── TREASURER PORTAL ────────────────────────────────────────────────────
    path("portal/treasurer/",                treasurer_dashboard_view,       name="treasurer_dashboard"),
    path("portal/treasurer/teams/",          treasurer_teams_view,           name="treasurer_teams"),
    path("portal/treasurer/county-payments/", treasurer_county_payments_view, name="treasurer_county_payments"),

    # ── COUNTY SPORTS ADMIN PORTAL (REMOVED - merged into subcounty officer) ──

    # ── PLAYER PROFILE ────────────────────────────────────────────────────
    path("portal/players/<int:player_pk>/profile/", player_profile_view, name="player_profile"),

    # ── TEAM MANAGER PORTAL ───────────────────────────────────────────────
    path("portal/team-manager/",                                    team_manager_dashboard_view,    name="team_manager_dashboard"),
    path("portal/team-manager/fixtures/<int:fixture_pk>/squad/",    team_manager_match_squad_view,  name="team_manager_match_squad"),
    path("portal/team-manager/fixtures/<int:fixture_pk>/opponent/", team_manager_opponent_view,     name="team_manager_opponent"),
    path("portal/team-manager/sanctions/",                          team_manager_sanctions_view,    name="team_manager_sanctions"),
    path("portal/team-manager/appeal/",                             team_manager_file_appeal_view,  name="team_manager_file_appeal"),
    path("portal/team-manager/verified-players/",                   team_manager_verified_players_view, name="team_manager_verified_players"),

    # ── VERIFIED PLAYERS PDF (shared across portals) ──────────────────
    path("portal/verified-players/pdf/", verified_players_pdf_view, name="verified_players_pdf"),

    # ── MATCH DAY SQUAD PDF ───────────────────────────────────────────
    path("portal/squads/<int:squad_pk>/pdf/", match_squad_pdf_view, name="match_squad_pdf"),

    # ── SUBSTITUTIONS ────────────────────────────────────────────────
    path("portal/fixtures/<int:fixture_pk>/substitutions/request/", substitution_request_view, name="substitution_request"),
    path("portal/fixtures/<int:fixture_pk>/substitutions/", substitution_match_list_view, name="substitution_match_list"),
    path("portal/substitutions/<int:sub_pk>/approve/", substitution_approve_view, name="substitution_approve"),

    # ── CEC SPORTS CAUCUS PORTAL (REMOVED) ─────────────────────────────
    # path("portal/cec-sports/", cec_sports_portal_view, name="cec_sports_portal"),

    # ── COMPETITION MANAGER PORTAL ────────────────────────────────────────
    path("portal/competitions/<int:pk>/standings/",   competition_standings_view,      name="competition_standings"),
    path("portal/competitions/<int:pk>/reports/",     competition_reports_view,        name="competition_reports"),
    path("portal/competitions/<int:pk>/reports/<int:report_pk>/approve/",
         competition_report_approve_view, name="competition_report_approve"),

    # ── COMPETITION MANAGER - FULL MANAGEMENT ─────────────────────────────
    path("portal/cm/",                                     cm_dashboard_view,             name="cm_dashboard"),
    path("portal/cm/create/",                              cm_create_competition_view,    name="cm_create_competition"),
    path("portal/cm/competitions/<int:pk>/edit/",          cm_edit_competition_view,      name="cm_edit_competition"),
    path("portal/cm/competitions/<int:pk>/",               cm_competition_manage_view,    name="cm_competition_manage"),
    path("portal/cm/competitions/<int:pk>/pools/",         cm_manage_pools_view,          name="cm_manage_pools"),
    path("portal/cm/competitions/<int:pk>/fixtures/generate/", cm_generate_fixtures_view, name="cm_generate_fixtures"),
    path("portal/cm/competitions/<int:pk>/venues/",        cm_allocate_venue_view,        name="cm_allocate_venues"),
    path("portal/cm/competitions/<int:pk>/standings/edit/", cm_edit_standings_view,       name="cm_edit_standings"),
    path("portal/cm/competitions/<int:pk>/fixtures/<int:fixture_pk>/edit/",
         cm_edit_fixture_view, name="cm_edit_fixture"),
    path("portal/cm/competitions/<int:pk>/fixtures/<int:fixture_pk>/delete/",
         cm_delete_fixture_view, name="cm_delete_fixture"),
    path("portal/cm/competitions/<int:pk>/rules/",         cm_competition_rules_view,     name="cm_competition_rules"),
    path("portal/cm/venues/",                              cm_manage_venues_view,         name="cm_venues"),



    # ── DISCIPLINE COORDINATOR PORTAL ─────────────────────────────────────
    path("portal/coordinator/",                                          coordinator_dashboard_view,           name="coordinator_dashboard"),
    path("portal/coordinator/competitions/",                             coordinator_competitions_view,        name="coordinator_competitions"),
    path("portal/coordinator/competitions/create/",                      coordinator_create_competition_view,  name="coordinator_create_competition"),
    path("portal/coordinator/competitions/<int:pk>/edit/",               coordinator_edit_competition_view,    name="coordinator_edit_competition"),
    path("portal/coordinator/competitions/<int:pk>/",                    coordinator_competition_manage_view,  name="coordinator_competition_manage"),
    path("portal/coordinator/competitions/<int:pk>/pools/",              coordinator_manage_pools_view,        name="coordinator_manage_pools"),
    path("portal/coordinator/competitions/<int:pk>/fixtures/generate/",  coordinator_generate_fixtures_view,   name="coordinator_generate_fixtures"),
    path("portal/coordinator/competitions/<int:pk>/venues/",             coordinator_allocate_venue_view,      name="coordinator_allocate_venues"),
    path("portal/coordinator/competitions/<int:pk>/standings/edit/",     coordinator_edit_standings_view,      name="coordinator_edit_standings"),
    path("portal/coordinator/competitions/<int:pk>/fixtures/create/",
         coordinator_create_fixture_view, name="coordinator_create_fixture"),
    path("portal/coordinator/competitions/<int:pk>/fixtures/generate-semis/",
         coordinator_generate_semis_view, name="coordinator_generate_semis"),
    path("portal/coordinator/competitions/<int:pk>/fixtures/<int:fixture_pk>/edit/",
         coordinator_edit_fixture_view, name="coordinator_edit_fixture"),
    path("portal/coordinator/competitions/<int:pk>/fixtures/<int:fixture_pk>/delete/",
         coordinator_delete_fixture_view, name="coordinator_delete_fixture"),
    path("portal/coordinator/competitions/<int:pk>/fixtures/<int:fixture_pk>/reschedule/",
         coordinator_reschedule_fixture_view, name="coordinator_reschedule_fixture"),
    path("portal/coordinator/competitions/<int:pk>/fixtures/<int:fixture_pk>/live/",
         coordinator_live_match_view, name="coordinator_live_match"),
    path("portal/coordinator/competitions/<int:pk>/fixtures/<int:fixture_pk>/squads/",
         coordinator_fixture_squads_view, name="coordinator_fixture_squads"),
    path("portal/coordinator/competitions/<int:pk>/stats/",              coordinator_statistics_view,          name="coordinator_statistics"),
    path("portal/coordinator/competitions/<int:pk>/rules/",              coordinator_competition_rules_view,   name="coordinator_competition_rules"),
    path("portal/coordinator/venues/",                                   coordinator_venues_view,              name="coordinator_venues"),
    path("portal/coordinator/match-reports/",                            coordinator_match_reports_view,       name="coordinator_match_reports"),
    path("portal/coordinator/squads/",                                   coordinator_squads_view,              name="coordinator_squads"),
    path("portal/coordinator/referees/",                                 coordinator_referees_view,            name="coordinator_referees"),
    path("portal/coordinator/appointments/",                             coordinator_appointments_view,        name="coordinator_appointments"),
    path("portal/coordinator/appointments/<int:fixture_pk>/",            referee_appoint_view,                 name="coordinator_appoint"),
    # Coordinator bulk upload & team manager
    path("portal/coordinator/bulk-uploads/",                             coordinator_bulk_upload_list_view,    name="coordinator_bulk_upload_list"),
    path("portal/coordinator/bulk-upload/",                              coordinator_bulk_upload_view,         name="coordinator_bulk_upload"),
    path("portal/coordinator/bulk-uploads/<int:pk>/",                    coordinator_bulk_upload_detail_view,  name="coordinator_bulk_upload_detail"),
    path("portal/coordinator/bulk-uploads/<int:pk>/delete/",             coordinator_bulk_upload_delete_view,  name="coordinator_bulk_upload_delete"),
    path("portal/coordinator/assign-team-manager/",                      coordinator_assign_team_manager_view, name="coordinator_assign_team_manager"),

    # ── SECRETARY GENERAL PORTAL ─────────────────────────────────────────────
    path("portal/sg/",                          sg_dashboard_view,          name="sg_dashboard"),
    path("portal/sg/verifications/",             sg_verifications_view,      name="sg_verifications"),
    path("portal/sg/appeals/",                   sg_appeals_view,            name="sg_appeals"),
    path("portal/sg/treasurer-actions/",         sg_treasurer_actions_view,  name="sg_treasurer_actions"),
    path("portal/sg/user-actions/",              sg_user_actions_view,       name="sg_user_actions"),
    path("portal/sg/exceptional-overrides/",     sg_exceptional_overrides_view, name="sg_exceptional_overrides"),
    path("portal/sg/verified-players/",          sg_verified_players_view,   name="sg_verified_players"),

    # ── MEDIA MANAGER PORTAL ─────────────────────────────────────────────────
    path("portal/media/",                          media_dashboard_view,          name="media_dashboard"),
    path("portal/media/articles/",                  media_article_list_view,       name="media_article_list"),
    path("portal/media/articles/create/",           media_article_create_view,     name="media_article_create"),
    path("portal/media/articles/<int:pk>/edit/",    media_article_edit_view,       name="media_article_edit"),
    path("portal/media/articles/<int:pk>/delete/",  media_article_delete_view,     name="media_article_delete"),
    path("portal/media/categories/",                media_category_manage_view,    name="media_categories"),
    path("portal/media/categories/<int:pk>/delete/",media_category_delete_view,    name="media_category_delete"),
    path("portal/media/albums/",                    media_album_list_view,         name="media_album_list"),
    path("portal/media/albums/create/",             media_album_create_view,       name="media_album_create"),
    path("portal/media/albums/<int:pk>/edit/",      media_album_edit_view,         name="media_album_edit"),
    path("portal/media/albums/<int:pk>/delete/",    media_album_delete_view,       name="media_album_delete"),
    path("portal/media/photos/<int:pk>/delete/",    media_photo_delete_view,       name="media_photo_delete"),
    path("portal/media/videos/",                    media_video_list_view,         name="media_video_list"),
    path("portal/media/videos/create/",             media_video_create_view,       name="media_video_create"),
    path("portal/media/videos/<int:pk>/edit/",      media_video_edit_view,         name="media_video_edit"),
    path("portal/media/videos/<int:pk>/delete/",    media_video_delete_view,       name="media_video_delete"),

    # ── SCOUT PORTAL ─────────────────────────────────────────────────────────
    path("portal/scout/",                              scout_dashboard_view,              name="scout_dashboard"),
    path("portal/scout/players/",                      scout_players_view,                name="scout_players"),
    path("portal/scout/shortlist/",                    scout_shortlist_view,              name="scout_shortlist"),
    path("portal/scout/shortlist/submit/",             scout_submit_shortlist_view,       name="scout_submit_shortlist"),
    path("portal/scout/shortlist/request-edit/",       scout_request_shortlist_edit_view, name="scout_request_shortlist_edit"),
    path("portal/scout/shortlist/add/<int:player_pk>/",scout_add_to_shortlist_view,       name="scout_add_to_shortlist"),
    path("portal/scout/shortlist/<int:pk>/edit/",      scout_edit_shortlist_view,         name="scout_edit_shortlist"),
    path("portal/scout/shortlist/<int:pk>/remove/",    scout_remove_from_shortlist_view,  name="scout_remove_from_shortlist"),
    path("portal/scout/matches/",                      scout_live_matches_view,           name="scout_live_matches"),
    path("portal/scout/match/<int:fixture_pk>/squad/",  scout_match_squad_view,            name="scout_match_squad"),
    path("portal/scout/match/<int:fixture_pk>/evaluate/<int:player_pk>/", scout_evaluate_player_view, name="scout_evaluate_player"),
    path("portal/scout/reports/",                       scout_reports_view,                name="scout_reports"),
    path("portal/scout/reports/<int:pk>/",              scout_report_detail_view,          name="scout_report_detail"),

    # ── SUB-COUNTY SPORTS OFFICER PORTAL ──────────────────────────────────
    path("portal/subcounty-officer/", subcounty_officer_dashboard_view, name="subcounty_officer_dashboard"),
    path("portal/subcounty-officer/disciplines/", subcounty_officer_disciplines_view, name="subcounty_officer_disciplines"),
    path("portal/subcounty-officer/discipline/<int:discipline_pk>/", subcounty_officer_discipline_players_view, name="subcounty_officer_discipline_players"),
    path("portal/subcounty-officer/discipline/<int:discipline_pk>/add-player/", subcounty_officer_add_player_view, name="subcounty_officer_add_player"),
    path("portal/subcounty-officer/player/<int:player_pk>/delete/", subcounty_officer_delete_player_view, name="subcounty_officer_delete_player"),
    path("portal/subcounty-officer/verified-players/", subcounty_verified_players_view, name="subcounty_verified_players"),
    path("portal/subcounty-officer/discipline/<int:discipline_pk>/add-bench-member/", county_admin_add_bench_member_view, name="subcounty_officer_add_bench_member"),
    path("portal/subcounty-officer/bench-member/<int:member_pk>/delete/", county_admin_delete_bench_member_view,  name="subcounty_officer_delete_bench_member"),
    path("portal/subcounty-officer/delegation/",                         county_admin_delegation_members_view,    name="subcounty_officer_delegation_members"),
    path("portal/subcounty-officer/delegation/<int:member_pk>/delete/",  county_admin_delete_delegation_member_view, name="subcounty_officer_delete_delegation_member"),
    path("portal/subcounty-officer/verification/",                       county_admin_verification_view,          name="subcounty_officer_verification"),
    path("portal/subcounty-officer/discipline/<int:discipline_pk>/team-list.pdf", team_list_pdf_view, name="team_list_pdf"),
    path("portal/subcounty-officer/discipline/<int:discipline_pk>/kit-colors/",   county_admin_kit_colors_view,   name="subcounty_officer_kit_colors"),
    path("portal/subcounty-officer/referees/",                                     subcounty_officer_referees_view, name="subcounty_officer_referees"),

    # ── SUB-COUNTY COMPETITION MANAGEMENT (Tasks 10.1, 10.3, 10.5, 10.7, 10.8, 10.12) ────────
    path("portal/subcounty/competitions/",
         sc_competitions_view,        name="sc_competitions"),
    path("portal/subcounty/competitions/create/",
         sc_create_competition_view,  name="sc_create_competition"),
    path("portal/subcounty/competitions/<int:pk>/",
         sc_competition_manage_view,  name="sc_competition_manage"),
    path("portal/subcounty/competitions/<int:pk>/pools/",
         sc_manage_pools_view,        name="sc_manage_pools"),
    path("portal/subcounty/competitions/<int:pk>/fixtures/generate/",
         sc_generate_fixtures_view,   name="sc_generate_fixtures"),
    path("portal/subcounty/competitions/<int:pk>/fixtures/<int:fixture_pk>/live/",
         sc_live_match_view,          name="sc_live_match"),
    path("portal/subcounty/competitions/<int:pk>/standings/edit/",
         sc_edit_standings_view,      name="sc_edit_standings"),
    path("portal/subcounty/competitions/<int:pk>/fixtures/<int:fixture_pk>/appoint-referee/",
         sc_appoint_referee_view,     name="sc_appoint_referee"),
    path("portal/subcounty/competitions/<int:pk>/qualify/",
         sc_qualify_teams_view,       name="sc_qualify_teams"),
    path("portal/subcounty/verification/",
         sc_verification_dashboard_view, name="sc_verification_dashboard"),
    path("portal/subcounty/verification/<int:player_pk>/",
         sc_verify_player_view,       name="sc_verify_player"),
    path("portal/subcounty/promote/<int:player_pk>/",
         sc_promote_player_view,      name="sc_promote_player"),

    # ── DIRECTOR OF SPORTS PORTAL ─────────────────────────────────────────
    path("portal/director-sports/", director_sports_dashboard_view, name="director_sports_dashboard"),
    path("portal/director-sports/verified-players/", director_sports_verified_players_view, name="director_sports_verified_players"),
    path("portal/director-sports/verified-players/<int:pk>/approve/", director_sports_approve_player_view, name="director_sports_approve_player"),
    path("portal/director-sports/verified-players/<int:pk>/disapprove/", director_sports_disapprove_player_view, name="director_sports_disapprove_player"),
    path("portal/director-sports/verified-players/bulk-approve/", director_sports_bulk_approve_view, name="director_sports_bulk_approve"),
    path("portal/director-sports/verified-players/lock/", director_sports_lock_list_view, name="director_sports_lock_list"),
    path("portal/director-sports/verified-players/unlock/", director_sports_unlock_list_view, name="director_sports_unlock_list"),
    path("portal/director-sports/scout-shortlist-requests/", director_sports_shortlist_requests_view, name="director_sports_shortlist_requests"),
    path("portal/director-sports/scout-shortlist-requests/<int:pk>/review/", director_sports_review_shortlist_request_view, name="director_sports_review_shortlist_request"),
    path("portal/director-sports/audit/", director_sports_audit_view, name="director_sports_audit"),
    path("portal/director-sports/system-users/", director_sports_system_users_view, name="director_sports_system_users"),
    path("portal/director-sports/delegations/", director_sports_delegations_view, name="director_sports_delegations"),
    path("portal/director-sports/technical-bench/", director_sports_technical_bench_view, name="director_sports_technical_bench"),
    path("portal/director-sports/bulk-uploads/", director_bulk_upload_list_view, name="director_bulk_upload_list"),
    path("portal/director-sports/bulk-uploads/<int:pk>/review/", director_bulk_upload_review_view, name="director_bulk_upload_review"),

    # ── EDIT SUB-COUNTY PLAYER (shared) ────────────────────────────────────
    path("portal/county-player/<int:pk>/edit/", edit_county_player_view, name="edit_county_player"),

    # ── CHIEF OFFICER SPORTS PORTAL ───────────────────────────────────────
    path("portal/chief-officer-sports/", chief_officer_sports_dashboard_view, name="chief_officer_sports_dashboard"),

    # ── CHIEF SPORTS OFFICER PORTAL ───────────────────────────────────────
    path("portal/chief-sports-officer/", chief_sports_officer_dashboard_view, name="chief_sports_officer_dashboard"),
    path("portal/chief-sports-officer/bulk-uploads/", cso_bulk_upload_list_view, name="cso_bulk_upload_list"),
    path("portal/chief-sports-officer/bulk-upload/", cso_bulk_upload_view, name="cso_bulk_upload"),
    path("portal/chief-sports-officer/bulk-uploads/<int:pk>/", cso_bulk_upload_detail_view, name="cso_bulk_upload_detail"),
    path("portal/chief-sports-officer/bulk-uploads/<int:pk>/delete/", cso_bulk_upload_delete_view, name="cso_bulk_upload_delete"),
    path("portal/chief-sports-officer/bulk-uploads/row/<int:row_pk>/edit/", cso_bulk_upload_edit_row_view, name="cso_bulk_upload_edit_row"),
    path("portal/chief-sports-officer/coordinator-uploads/<int:pk>/review/", cso_approve_coordinator_upload_view, name="cso_approve_coordinator_upload"),

    # ── DIRECTOR SPORTS: Coordinator upload approval ──────────────────────
    path("portal/director-sports/coordinator-uploads/<int:pk>/review/", ds_approve_coordinator_upload_view, name="ds_approve_coordinator_upload"),

    # ── GOVERNOR PORTAL ───────────────────────────────────────────────────
    path("portal/governor/", governor_dashboard_view, name="governor_dashboard"),

    # ── WAZIRI SPORTS PORTAL ──────────────────────────────────────────────
    path("portal/waziri-sports/", waziri_sports_dashboard_view, name="waziri_sports_dashboard"),

    # ── VERIFICATION OFFICER PORTAL ───────────────────────────────────────
    path("portal/verification-officer/", vo_dashboard_view, name="vo_dashboard"),
    path("portal/verification-officer/players-by-subcounty/", vo_players_by_subcounty_view, name="vo_players_by_subcounty"),
    path("portal/verification-officer/player/<int:player_pk>/verify/", vo_verify_county_player_view, name="vo_verify_county_player"),

    # ── LEADERSHIP SCOUTING REPORTS ───────────────────────────────────────
    path("portal/leadership/scout-reports/",            leadership_scout_reports_view,       name="leadership_scout_reports"),
    path("portal/leadership/scout-reports/<int:pk>/",   leadership_scout_report_detail_view, name="leadership_scout_report_detail"),

    # ── ADMIN DASHBOARD ───────────────────────────────────────────────────────
    path("portal/admin-dashboard/", include("admin_dashboard.urls")),

    # ── LIGI MASHINANI REGISTRATIONS (Admin portal) ───────────────────────────
    path("portal/ligi-registrations/",
         ligi_registrations_list_view,       name="ligi_registrations_list"),
    path("portal/ligi-registrations/<int:pk>/",
         ligi_registration_detail_view,      name="ligi_registration_detail"),
    path("portal/ligi-registrations/<int:pk>/approve/",
         ligi_registration_approve_view,     name="ligi_registration_approve"),
    path("portal/ligi-registrations/<int:pk>/reject/",
         ligi_registration_reject_view,      name="ligi_registration_reject"),
    path("portal/ligi-registrations/<int:pk>/ward-verify/",
         ligi_registration_ward_verify_view, name="ligi_registration_ward_verify"),

    # ── LIGI MASHINANI: Settings / Window Control ─────────────────────────────
    path("portal/ligi/settings/",  ligi_settings_view, name="ligi_settings"),

    # ── LIGI MASHINANI: Transfer System ──────────────────────────────────────
    path("ligi/transfers/",                           ward_tm_transfers_view,       name="ward_tm_transfers"),
    path("ligi/transfers/request/",                   ward_tm_request_transfer_view, name="ward_tm_request_transfer"),
    path("ligi/transfers/<int:transfer_pk>/withdraw/", ward_tm_withdraw_transfer_view, name="ward_tm_withdraw_transfer"),
    path("ligi/wscc/transfers/",                      wscc_transfers_view,          name="wscc_transfers"),
    path("ligi/wscc/transfers/<int:transfer_pk>/action/", wscc_transfer_action_view, name="wscc_transfer_action"),
    path("portal/subcounty/transfers/",               scso_transfers_view,          name="scso_transfers"),
    path("portal/subcounty/transfers/<int:transfer_pk>/action/", scso_transfer_action_view, name="scso_transfer_action"),

    # ── LIGI MASHINANI: Player Register (read-only, multi-role) ──────────────
    path("ligi/player-register/", ligi_player_register_view, name="ligi_player_register"),

    # ── LIGI MASHINANI: Ward Competition Engine (WSCC) ───────────────────────
    path("ligi/wscc/ward-competition/",                              wscc_ward_competition_setup_view,      name="wscc_ward_competition_setup"),
    path("ligi/wscc/ward-competition/<int:comp_pk>/",               wscc_ward_comp_manage_view,             name="wscc_ward_comp_manage"),
    path("ligi/wscc/ward-competition/<int:comp_pk>/pools/",         wscc_ward_comp_pools_view,              name="wscc_ward_comp_pools"),
    path("ligi/wscc/ward-competition/<int:comp_pk>/generate/",      wscc_ward_comp_generate_fixtures_view,  name="wscc_ward_comp_generate"),
    path("ligi/wscc/match-sheet/<int:fixture_pk>/",                 wscc_ward_match_sheet_view,             name="wscc_ward_match_sheet"),

    # ── LIGI MASHINANI: Senior Transfer Portal (CSO / Director / Admin) ──────
    path("portal/ligi/transfers/senior/",                          senior_transfers_view,          name="senior_transfers"),
    path("portal/ligi/transfers/senior/<int:transfer_pk>/action/", senior_transfer_action_view,    name="senior_transfer_action"),

    # ── LIGI MASHINANI: Transfer Tracking Dashboard (Director of Sports) ──────
    path("portal/ligi/transfers/tracking/", transfer_tracking_dashboard_view, name="transfer_tracking"),
    # ── LIGI MASHINANI: Ward Squad Substitutions ──────────────────────────────
    path("ligi/fixtures/<int:fixture_pk>/substitutions/", ward_tm_substitution_view, name="ward_tm_substitution"),
    path("ligi/substitutions/<int:sub_pk>/action/", ward_sub_approve_view, name="ward_sub_approve"),

    # ── APPEALS & JURY ────────────────────────────────────────────────────────
    path("portal/appeals/", include("appeals.urls")),

    # ── DJANGO ADMIN ─────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── API v1 ────────────────────────────────────────────────────────────────
    path("api/v1/auth/",         include("accounts.urls")),
    path("api/v1/competitions/", include("competitions.urls")),
    path("api/v1/referees/",     include("referees.urls")),
    path("api/v1/teams/",        include("teams.urls")),
    path("api/v1/matches/",      include("matches.urls")),

    # ── API DOCUMENTATION ─────────────────────────────────────────────────────
    path("api/schema/", SpectacularAPIView.as_view(),                        name="schema"),
    path("api/docs/",   SpectacularSwaggerView.as_view(url_name="schema"),   name="swagger-ui"),
    path("api/redoc/",  SpectacularRedocView.as_view(url_name="schema"),     name="redoc"),
]

# ── SERVE MEDIA IN DEVELOPMENT ────────────────────────────────────────────────
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ── ADMIN CUSTOMISATION ───────────────────────────────────────────────────────
# Custom error handler: logs the actual exception behind 400 responses
handler400 = "mkj_cms.web_views.custom_bad_request_view"

admin.site.site_header = "MKJ SUPA CUP - Governor Mutula Kilonzo Junior Supa Cup"
admin.site.site_title  = "MKJ SUPA CUP Admin"
admin.site.index_title = "Makueni County Sports Administration"