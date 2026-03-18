"""
MKJ SUPA CUP Appeals — URL Configuration
"""
from django.urls import path
from . import views
from . import jury_views

urlpatterns = [
    # ── Appeal listing & dashboard ────────────────────────────────────────
    path("",                                      views.appeals_list_view,              name="appeals_list"),
    path("jury-dashboard/",                       views.jury_dashboard_view,            name="jury_dashboard"),

    # ── Jury Chair data views ─────────────────────────────────────────────
    path("jury/teams/",               jury_views.jury_teams_view,            name="jury_teams"),
    path("jury/players/",             jury_views.jury_players_view,          name="jury_players"),
    path("jury/fixtures/",            jury_views.jury_fixtures_view,         name="jury_fixtures"),
    path("jury/match-reports/",       jury_views.jury_match_reports_view,    name="jury_match_reports"),
    path("jury/squads/",              jury_views.jury_squads_view,           name="jury_squads"),
    path("jury/squads/<int:pk>/",     jury_views.jury_squad_detail_view,     name="jury_squad_detail"),
    path("jury/disciplinary/",        jury_views.jury_disciplinary_view,     name="jury_disciplinary"),

    # ── Jury Chair exports — Excel ────────────────────────────────────────
    path("jury/export/teams/excel/",         jury_views.jury_export_teams_excel,         name="jury_export_teams_excel"),
    path("jury/export/players/excel/",       jury_views.jury_export_players_excel,       name="jury_export_players_excel"),
    path("jury/export/fixtures/excel/",      jury_views.jury_export_fixtures_excel,      name="jury_export_fixtures_excel"),
    path("jury/export/match-reports/excel/", jury_views.jury_export_match_reports_excel, name="jury_export_match_reports_excel"),
    path("jury/export/squads/excel/",        jury_views.jury_export_squads_excel,        name="jury_export_squads_excel"),
    path("jury/export/disciplinary/excel/",  jury_views.jury_export_disciplinary_excel,  name="jury_export_disciplinary_excel"),

    # ── Jury Chair exports — PDF ──────────────────────────────────────────
    path("jury/export/teams/pdf/",           jury_views.jury_export_teams_pdf,           name="jury_export_teams_pdf"),
    path("jury/export/players/pdf/",         jury_views.jury_export_players_pdf,         name="jury_export_players_pdf"),
    path("jury/export/fixtures/pdf/",        jury_views.jury_export_fixtures_pdf,        name="jury_export_fixtures_pdf"),
    path("jury/export/match-reports/pdf/",   jury_views.jury_export_match_reports_pdf,   name="jury_export_match_reports_pdf"),
    path("jury/export/squads/pdf/",          jury_views.jury_export_squads_pdf,          name="jury_export_squads_pdf"),
    path("jury/export/disciplinary/pdf/",    jury_views.jury_export_disciplinary_pdf,    name="jury_export_disciplinary_pdf"),

    # ── Appeal CRUD ───────────────────────────────────────────────────────
    path("new/",                                  views.submit_appeal_view,             name="submit_appeal"),
    path("<int:pk>/",                             views.appeal_detail_view,             name="appeal_detail"),
    path("<int:pk>/evidence/",                    views.upload_evidence_view,           name="upload_appeal_evidence"),
    path("<int:pk>/pay-fee/",                     views.pay_fee_view,                   name="pay_appeal_fee"),
    path("<int:pk>/submit/",                      views.finalize_appeal_view,           name="finalize_appeal"),

    # ── Response ──────────────────────────────────────────────────────────
    path("<int:pk>/respond/",                     views.submit_response_view,           name="submit_appeal_response"),
    path("<int:pk>/respond/evidence/",            views.upload_response_evidence_view,  name="upload_response_evidence"),

    # ── Jury decisions ────────────────────────────────────────────────────
    path("<int:pk>/decision/",                    views.jury_decision_view,             name="jury_decision"),
    path("<int:pk>/decision/<int:decision_pk>/evidence/",  views.upload_decision_evidence_view, name="upload_decision_evidence"),
    path("<int:pk>/decision/<int:decision_pk>/publish/",   views.publish_decision_view,         name="publish_decision"),

    # ── Hearing schedule (Jury Chair) ─────────────────────────────────────
    path("<int:pk>/schedule-hearing/",                     views.schedule_hearing_view,   name="schedule_hearing"),
    path("<int:pk>/hearing/<int:hearing_pk>/cancel/",      views.cancel_hearing_view,     name="cancel_hearing"),

    # ── Re-appeal ─────────────────────────────────────────────────────────
    path("<int:pk>/reappeal/",                    views.reappeal_view,                  name="reappeal"),

    # ── Fee verification (admin/treasurer) ────────────────────────────────
    path("<int:pk>/verify-fee/",                  views.verify_fee_view,                name="verify_appeal_fee"),
]
