# admin_dashboard/urls.py
from django.urls import path

from . import views

from . import admin_views
from . import reschedule_admin_views
from . import activity_views
from . import export_views
from . import audit_report_views


urlpatterns = [
    # Admin dashboard views (for specific admin operations)
    path('approve-registrations/', views.approve_registrations, name='approve_registrations'),
    path('approve-reports/', views.approve_reports, name='approve_reports'),
    path('suspensions/', views.view_suspensions, name='view_suspensions'),
    path('suspensions/manage/<int:player_id>/', views.manage_suspension, name='manage_suspension'),
    path('statistics/', views.statistics_dashboard, name='statistics_dashboard'),
    path('assign-zones/', views.assign_zones, name='assign_zones'),
    path('view-report/<int:report_id>/', views.view_report, name='view_report'),
    path('generate-fixtures/', admin_views.generate_fixtures_admin, name='generate_fixtures_admin'),
    path('reschedule-fixtures/', reschedule_admin_views.reschedule_fixtures_admin, name='reschedule_fixtures_admin'),
    
    # Activity Logs
    path('activity-logs/', activity_views.activity_logs, name='activity_logs'),
    path('activity-logs/<int:log_id>/', activity_views.activity_log_detail, name='activity_log_detail'),
    path('activity-logs/<int:log_id>/undo/', activity_views.undo_action, name='undo_action'),
    
    # Export Logs
    path('activity-logs/export/excel/', export_views.export_logs_excel, name='export_logs_excel'),
    path('activity-logs/export/pdf/', export_views.export_logs_pdf, name='export_logs_pdf'),
    
    # Audit Report (Super Admin)
    path('audit-report/', audit_report_views.audit_report, name='audit_report'),
    path('audit-report/export/excel/', audit_report_views.export_audit_excel, name='export_audit_excel'),
    path('audit-report/export/pdf/', audit_report_views.export_audit_pdf, name='export_audit_pdf'),
    
    # Registration Window Controls
    path('toggle-registration/', views.toggle_registration_window, name='toggle_registration'),
    path('update-deadlines/', views.update_registration_deadlines, name='update_deadlines'),
    
    # Transfer Management
    path('transfers/', views.manage_transfers, name='manage_transfers'),
    path('transfers/override/<int:transfer_id>/', views.admin_override_transfer, name='override_transfer'),
    
    # User Management (Super Admin Only)
    path('users/', views.manage_league_admins, name='manage_league_admins'),
    path('users/create/', views.create_league_admin, name='create_league_admin'),
    path('users/<int:user_id>/', views.user_detail_view, name='user_detail'),
    path('users/<int:user_id>/edit/', views.user_edit_profile, name='user_edit_profile'),
    path('users/<int:user_id>/toggle/', views.toggle_league_admin_status, name='toggle_league_admin_status'),
    path('users/<int:user_id>/reset-password/', views.reset_league_admin_password, name='reset_league_admin_password'),
    path('users/<int:user_id>/set-password/', views.user_force_password, name='user_force_password'),
    path('users/<int:user_id>/edit-roles/', views.edit_user_roles, name='edit_user_roles'),
    path('users/<int:user_id>/suspend/', views.user_suspend_toggle, name='user_suspend_toggle'),
    path('users/<int:user_id>/toggle-staff/', views.user_toggle_staff, name='user_toggle_staff'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),

    # Per-user activity log exports
    path('users/<int:user_id>/export/excel/', export_views.export_user_logs_excel, name='export_user_logs_excel'),
    path('users/<int:user_id>/export/pdf/', export_views.export_user_logs_pdf, name='export_user_logs_pdf'),
]