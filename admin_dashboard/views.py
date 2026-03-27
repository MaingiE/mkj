# admin_dashboard/views.py — Adapted for MKJ SUPA CUP CMS models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.utils.safestring import mark_safe
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings as django_settings

from accounts.models import User, UserRole, KenyaCounty, MakueniSubCounty, validate_kenya_phone_or_raise
from teams.models import Team, Player
from referees.models import RefereeProfile, RefereeAppointment
from competitions.models import Competition, Fixture, SportType
from matches.models import MatchReport
from .models import ActivityLog


COORDINATOR_DISCIPLINE_CHOICES = [
    ("football", "Soccer"),
    ("volleyball", "Volleyball"),
    ("basketball", "Basketball"),
    ("handball", "Handball"),
]

SCOUT_DISCIPLINE_CHOICES = [
    (SportType.FOOTBALL_MEN, "Soccer (Men)"),
    (SportType.FOOTBALL_WOMEN, "Soccer (Women)"),
    (SportType.VOLLEYBALL_MEN, "Volleyball (Men)"),
    (SportType.VOLLEYBALL_WOMEN, "Volleyball (Women)"),
    (SportType.BASKETBALL_MEN, "Basketball 5x5 (Men)"),
    (SportType.BASKETBALL_WOMEN, "Basketball 5x5 (Women)"),
    (SportType.BASKETBALL_3X3_MEN, "Basketball 3x3 (Men)"),
    (SportType.BASKETBALL_3X3_WOMEN, "Basketball 3x3 (Women)"),
    (SportType.HANDBALL_MEN, "Handball (Men)"),
    (SportType.HANDBALL_WOMEN, "Handball (Women)"),
]


def admin_required(user):
    """Check if user is superuser, staff, or admin role"""
    return user.is_superuser or user.is_staff or user.role == 'admin'


def superadmin_required(user):
    """Check if user is superuser"""
    return user.is_superuser


def send_welcome_email(user_obj, password, role):
    """Send welcome email to newly created user with login credentials."""
    from django.core.mail import EmailMultiAlternatives

    subject = f'Welcome to MKJ SUPA CUP Competition Management System - {role}'
    text_content = f"""
Dear {user_obj.first_name} {user_obj.last_name},

Welcome to the MKJ SUPA CUP Competition Management System!

Your account has been created:

Login Email: {user_obj.email}
Temporary Password: {password}
Role: {role}

Login URL: /portal/login/

Please change your password after your first login.

Best regards,
MKJ SUPA CUP Administration
"""
    try:
        email = EmailMultiAlternatives(
            subject, text_content,
            getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@mkj_supacup.org'),
            [user_obj.email]
        )
        email.send(fail_silently=True)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def send_password_reset_email(user_obj, new_password):
    """Send password reset email."""
    from django.core.mail import EmailMultiAlternatives

    subject = 'MKJ SUPA CUP CMS - Password Reset'
    text_content = f"""
Dear {user_obj.first_name} {user_obj.last_name},

Your password has been reset by an administrator.

Login Email: {user_obj.email}
New Password: {new_password}

Please change your password immediately after login.

Best regards,
MKJ SUPA CUP Administration
"""
    try:
        email = EmailMultiAlternatives(
            subject, text_content,
            getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@mkj_supacup.org'),
            [user_obj.email]
        )
        email.send(fail_silently=True)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


# Require discipline for scout/coordinator
def require_discipline_for_scout_coordinator(user_obj, assigned_discipline):
    """Check if discipline is provided for scout/coordinator."""
    if user_obj.role in ('scout', 'coordinator') and not assigned_discipline:
        messages.error(request, 'Discipline is required for scouts and coordinators.')
        return False
    return True


# ══════════════════════════════════════════════════════════════════════════════
#   ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    """Main admin dashboard with MKJ SUPA CUP statistics."""
    total_teams = Team.objects.count()
    registered_teams = Team.objects.filter(status='registered').count()
    pending_teams_count = Team.objects.filter(status='pending').count()
    total_players = Player.objects.count()
    total_referees = RefereeProfile.objects.count()
    approved_referees = RefereeProfile.objects.filter(is_approved=True).count()
    pending_referees_count = RefereeProfile.objects.filter(is_approved=False).count()
    total_competitions = Competition.objects.count()
    total_fixtures = Fixture.objects.count()

    # Recent activities
    recent_teams = Team.objects.order_by('-registered_at')[:5]
    recent_fixtures = Fixture.objects.select_related(
        'competition', 'home_team', 'away_team'
    ).order_by('-match_date')[:5]

    context = {
        'total_teams': total_teams,
        'registered_teams': registered_teams,
        'pending_teams': pending_teams_count,
        'total_players': total_players,
        'total_referees': total_referees,
        'approved_referees': approved_referees,
        'pending_referees': pending_referees_count,
        'total_competitions': total_competitions,
        'total_fixtures': total_fixtures,
        'recent_teams': recent_teams,
        'recent_fixtures': recent_fixtures,
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


# ══════════════════════════════════════════════════════════════════════════════
#   MATCH REPORT APPROVAL
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def approve_reports(request):
    """Approve match reports."""
    pending_reports = MatchReport.objects.filter(
        status='submitted'
    ).order_by('-submitted_at')

    if request.method == 'POST':
        report_id = request.POST.get('report_id')
        action = request.POST.get('action')
        report = get_object_or_404(MatchReport, id=report_id)

        if action == 'approve':
            report.status = 'approved'
            report.save()
            messages.success(request, f'Report approved.')
        elif action == 'reject':
            report.status = 'rejected'
            report.save()
            messages.warning(request, f'Report rejected.')

        return redirect('approve_reports')

    return render(request, 'admin_dashboard/approve_reports.html', {
        'pending_reports': pending_reports,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   PLAYER SUSPENSIONS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def view_suspensions(request):
    """View suspended players."""
    suspended_players = Player.objects.filter(status='suspended')
    context = {
        'suspended_players': suspended_players,
    }
    return render(request, 'admin_dashboard/suspensions.html', context)


@login_required
@user_passes_test(admin_required)
def manage_suspension(request, player_id):
    """Manage player suspension."""
    player = get_object_or_404(Player, id=player_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'suspend':
            player.status = 'suspended'
            player.save()
            messages.success(request, f'{player.get_full_name()} suspended.')

        elif action == 'clear':
            player.status = 'eligible'
            player.save()
            messages.success(request, f'{player.get_full_name()} suspension cleared.')

        return redirect('view_suspensions')

    return render(request, 'admin_dashboard/manage_suspension.html', {
        'player': player,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   STATISTICS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def statistics_dashboard(request):
    """Statistics and analytics dashboard."""
    # Team stats by county
    county_stats = (
        Team.objects.filter(status='registered')
        .values('county')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Player position distribution
    position_stats = (
        Player.objects.values('position')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Referee level distribution
    referee_stats = (
        RefereeProfile.objects.filter(is_approved=True)
        .values('level')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Competition stats
    competition_stats = {
        'total': Competition.objects.count(),
        'active': Competition.objects.filter(status='active').count(),
        'completed': Competition.objects.filter(status='completed').count(),
    }

    context = {
        'county_stats': county_stats,
        'position_stats': position_stats,
        'referee_stats': referee_stats,
        'competition_stats': competition_stats,
        'total_teams': Team.objects.filter(status='registered').count(),
        'total_players': Player.objects.count(),
        'total_referees': RefereeProfile.objects.filter(is_approved=True).count(),
    }
    return render(request, 'admin_dashboard/statistics.html', context)


# ══════════════════════════════════════════════════════════════════════════════
#   COMPETITION ASSIGNMENT (replaces FKFSYS Zone assignment)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def assign_zones(request):
    """Assign teams to competitions (MKJ SUPA CUP equivalent of zone assignment)."""
    unassigned_teams = Team.objects.filter(
        status='registered',
        payment_confirmed=True,
        competition__isnull=True
    ).order_by('name')

    competitions = Competition.objects.all()

    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        comp_id = request.POST.get('competition_id')

        team = get_object_or_404(Team, id=team_id)

        # Only treasurer-approved teams can participate
        if not team.payment_confirmed:
            messages.error(request, f'{team.name} cannot be assigned — payment has not been confirmed by the treasurer.')
            return redirect('assign_zones')
        if team.status != 'registered':
            messages.error(request, f'{team.name} is not approved. Only registered teams can participate.')
            return redirect('assign_zones')

        comp = get_object_or_404(Competition, id=comp_id) if comp_id else None

        team.competition = comp
        team.save()

        # Audit log
        ActivityLog.objects.create(
            user=request.user,
            action='ZONE_ASSIGN',
            description=f'{request.user.get_full_name()} assigned {team.name} to {comp.name if comp else "None"}',
            object_repr=str(team),
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

        messages.success(request, f'{team.name} assigned to {comp.name if comp else "None"}.')
        return redirect('assign_zones')

    # Get assignments
    comp_assignments = {}
    for comp in competitions:
        comp_assignments[comp] = Team.objects.filter(competition=comp, status='registered')

    return render(request, 'admin_dashboard/assign_zones.html', {
        'teams': unassigned_teams,
        'competitions': competitions,
        'comp_assignments': comp_assignments,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   VIEW MATCH REPORT
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def view_report(request, report_id):
    """View a specific match report in detail."""
    report = get_object_or_404(MatchReport, id=report_id)

    if not request.user.is_staff and not request.user.is_superuser:
        if hasattr(report, 'referee') and report.referee and hasattr(report.referee, 'user'):
            if report.referee.user != request.user:
                messages.error(request, "Permission denied.")
                return redirect('dashboard')

    return render(request, 'admin_dashboard/view_report.html', {
        'report': report,
        'title': f'Match Report #{report.id}',
    })


# ══════════════════════════════════════════════════════════════════════════════
#   USER MANAGEMENT (Super Admin Only)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(superadmin_required)
def manage_league_admins(request):
    """Manage all users — filter, search, view."""
    role_filter = request.GET.get('role', 'all')
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')

    users = User.objects.all()

    if role_filter != 'all':
        users = users.filter(role=role_filter)

    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    if search_query:
        users = users.filter(
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    users = users.order_by('-date_joined')

    coordinator_users = User.objects.filter(role='coordinator').order_by('assigned_discipline', 'first_name', 'last_name')
    coordinators_by_discipline = {
        code: [] for code, _ in COORDINATOR_DISCIPLINE_CHOICES
    }
    unassigned_coordinators = []
    for coord in coordinator_users:
        if coord.assigned_discipline in coordinators_by_discipline:
            coordinators_by_discipline[coord.assigned_discipline].append(coord)
        else:
            unassigned_coordinators.append(coord)

    sport_coordinator_rows = []
    for sport_code, sport_label in COORDINATOR_DISCIPLINE_CHOICES:
        assigned = coordinators_by_discipline.get(sport_code, [])
        sport_coordinator_rows.append({
            'sport_label': sport_label,
            'coordinators': assigned,
        })

    user_stats = {
        'total': User.objects.count(),
        'active': User.objects.filter(is_active=True).count(),
        'inactive': User.objects.filter(is_active=False).count(),
        'team_managers': User.objects.filter(role='team_manager').count(),
        'admins': User.objects.filter(role='admin').count(),
        'referees': User.objects.filter(role='referee').count(),
        'coordinators': User.objects.filter(role='coordinator').count(),
        'competition_managers': User.objects.filter(role='competition_manager').count(),
    }

    context = {
        'users': users,
        'user_stats': user_stats,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'role_choices': UserRole.choices,
        'sport_coordinator_rows': sport_coordinator_rows,
        'unassigned_coordinators': unassigned_coordinators,
        'coordinator_discipline_choices': COORDINATOR_DISCIPLINE_CHOICES,
        'scout_discipline_choices': SCOUT_DISCIPLINE_CHOICES,
        'county_choices': KenyaCounty.choices,
        'subcounty_choices': MakueniSubCounty.choices,
    }
    return render(request, 'admin_dashboard/manage_league_admins.html', context)


@login_required
@user_passes_test(superadmin_required)
def create_league_admin(request):
    """Create a new user with selected role."""
    import random, string

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', 'team_manager')
        county = 'Makueni'  # MKJ system is Makueni-only
        sub_county = request.POST.get('sub_county', '').strip()
        assigned_discipline = request.POST.get('assigned_discipline', '').strip()

        try:
            phone = validate_kenya_phone_or_raise(phone, 'Phone number')
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect('manage_league_admins')

        if User.objects.filter(email=email).exists():
            messages.error(request, f"Email '{email}' already registered.")
            return redirect('manage_league_admins')

        if role in (UserRole.SUBCOUNTY_SPORTS_OFFICER, UserRole.TEAM_MANAGER) and not sub_county:
            messages.error(request, 'Sub-county is required for this role.')
            return redirect('manage_league_admins')

        if role == UserRole.SUBCOUNTY_SPORTS_OFFICER and sub_county:
            existing = User.objects.filter(
                role=UserRole.SUBCOUNTY_SPORTS_OFFICER,
                sub_county=sub_county,
                is_active=True,
            ).exists()
            if existing:
                messages.error(request, f'A Sub-County Sports Officer already exists for {sub_county}. Only one is allowed per sub-county.')
                return redirect('manage_league_admins')

        if role in (UserRole.COORDINATOR, UserRole.SCOUT) and not assigned_discipline:
            if role == UserRole.COORDINATOR:
                messages.error(request, 'Choose a coordinator sport.')
            else:
                messages.error(request, 'Choose a scout sport and gender.')
            return redirect('manage_league_admins')

        if role == UserRole.COORDINATOR and assigned_discipline:
            valid_coordinator_codes = {code for code, _ in COORDINATOR_DISCIPLINE_CHOICES}
            if assigned_discipline not in valid_coordinator_codes:
                messages.error(request, 'Invalid coordinator sport selection.')
                return redirect('manage_league_admins')

        if role == UserRole.SCOUT and assigned_discipline:
            valid_scout_codes = {code for code, _ in SCOUT_DISCIPLINE_CHOICES}
            if assigned_discipline not in valid_scout_codes:
                messages.error(request, 'Invalid scout sport/gender selection.')
                return redirect('manage_league_admins')

        # ── One-user-per-role / per-discipline uniqueness checks ──────────
        # Roles with global uniqueness (only one person per system)
        SINGLETON_ROLES = {
            UserRole.COMPETITION_MANAGER,
            UserRole.TREASURER,
            UserRole.VERIFICATION_OFFICER,
            UserRole.SECRETARY_GENERAL,
            UserRole.MEDIA_MANAGER,
            UserRole.JURY_CHAIR,
        }
        if role in SINGLETON_ROLES:
            role_label = dict(UserRole.choices).get(role, role)
            if User.objects.filter(role=role, is_active=True).exists():
                messages.error(
                    request,
                    f'A user with the "{role_label}" role already exists. '
                    f'Deactivate the existing user before creating a new one.'
                )
                return redirect('manage_league_admins')

        # Coordinator: unique per assigned discipline
        if role == UserRole.COORDINATOR and assigned_discipline:
            if User.objects.filter(role=UserRole.COORDINATOR, assigned_discipline=assigned_discipline, is_active=True).exists():
                disc_label = dict(COORDINATOR_DISCIPLINE_CHOICES).get(assigned_discipline, assigned_discipline)
                messages.error(
                    request,
                    f'A Coordinator for "{disc_label}" already exists. '
                    f'Deactivate the existing coordinator first.'
                )
                return redirect('manage_league_admins')

        # Scout: unique per assigned discipline (sport + gender)
        if role == UserRole.SCOUT and assigned_discipline:
            if User.objects.filter(role=UserRole.SCOUT, assigned_discipline=assigned_discipline, is_active=True).exists():
                disc_label = dict(SCOUT_DISCIPLINE_CHOICES).get(assigned_discipline, assigned_discipline)
                messages.error(
                    request,
                    f'A Scout for "{disc_label}" already exists. '
                    f'Deactivate the existing scout first.'
                )
                return redirect('manage_league_admins')

        try:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            stored_county = 'Makueni'
            stored_sub_county = sub_county if role in (UserRole.SUBCOUNTY_SPORTS_OFFICER, UserRole.TEAM_MANAGER) else ''
            user_obj = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=role,
                county=stored_county,
                sub_county=stored_sub_county,
                assigned_discipline=assigned_discipline if role in (UserRole.COORDINATOR, UserRole.SCOUT) else '',
                is_active=True,
            )
            user_obj.must_change_password = True
            user_obj.save(update_fields=['must_change_password'])

            # Send credentials email
            email_sent = False
            try:
                from accounts.notifications import notify_account_created
                notify_account_created(user_obj, password, dict(UserRole.choices).get(role, role))
                email_sent = True
            except Exception:
                pass

            # Auto-create RefereeProfile when role is referee
            if role == 'referee':
                from referees.models import RefereeProfile
                RefereeProfile.objects.get_or_create(
                    user=user_obj,
                    defaults={
                        'county': user_obj.county or '',
                        'is_approved': True,
                        'approved_by': request.user,
                        'approved_at': timezone.now(),
                    },
                )

            if not email_sent:
                try:
                    send_welcome_email(user_obj, password, role)
                    email_sent = True
                except Exception:
                    pass

            if email_sent:
                messages.success(request, mark_safe(
                    f'User created!<br>'
                    f'Email: <code>{email}</code><br>'
                    f'Role: {role}<br>'
                    f'Temporary password has been sent to the user\'s email.'
                ))
            else:
                messages.warning(request, mark_safe(
                    f'User created but email delivery failed.<br>'
                    f'Email: <code>{email}</code><br>'
                    f'Role: {role}<br>'
                    f'Please reset their password manually or contact them directly.'
                ))
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return redirect('manage_league_admins')


@login_required
@user_passes_test(superadmin_required)
def toggle_league_admin_status(request, user_id):
    """Activate or deactivate a user."""
    user_obj = get_object_or_404(User, id=user_id)

    if user_obj == request.user:
        messages.error(request, "Cannot deactivate your own account!")
        return redirect('manage_league_admins')

    user_obj.is_active = not user_obj.is_active
    user_obj.save()

    status = "activated" if user_obj.is_active else "deactivated"
    messages.success(request, f"{user_obj.email} has been {status}.")
    return redirect('manage_league_admins')


@login_required
@user_passes_test(superadmin_required)
def reset_league_admin_password(request, user_id):
    """Reset password for any user."""
    import random, string

    user_obj = get_object_or_404(User, id=user_id)
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    user_obj.set_password(new_password)
    user_obj.must_change_password = True
    user_obj.save(update_fields=['password', 'must_change_password'])

    send_password_reset_email(user_obj, new_password)
    messages.success(request, mark_safe(
        f'Password reset for {user_obj.email}.<br>'
        f'New password has been sent to the user\'s email.'
    ))
    return redirect('manage_league_admins')


@login_required
@user_passes_test(superadmin_required)
def edit_user_roles(request, user_id):
    """Edit user's role assignment using MKJ SUPA CUP UserRole field."""
    user_obj = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        new_role = request.POST.get('role', user_obj.role)
        old_role = user_obj.role
        new_discipline = request.POST.get('assigned_discipline', '').strip()
        new_county = 'Makueni'
        new_sub_county = request.POST.get('sub_county', '').strip()

        if new_role not in dict(UserRole.choices):
            messages.error(request, f"Invalid role: {new_role}")
            return redirect('edit_user_roles', user_id=user_obj.id)

        # Enforce one Sub-County Sports Officer per sub-county
        if new_role == UserRole.SUBCOUNTY_SPORTS_OFFICER and new_sub_county:
            existing = User.objects.filter(
                role=UserRole.SUBCOUNTY_SPORTS_OFFICER,
                sub_county=new_sub_county,
                is_active=True,
            ).exclude(pk=user_obj.pk).exists()
            if existing:
                messages.error(request, f'A Sub-County Sports Officer already exists for {new_sub_county}. Only one is allowed per sub-county.')
                return redirect('edit_user_roles', user_id=user_obj.id)

        user_obj.role = new_role

        # Set is_staff for admin roles
        if new_role == 'admin':
            user_obj.is_staff = True
        else:
            user_obj.is_staff = False

        # Assign discipline for scout / coordinator roles
        update_fields = ['role', 'is_staff']
        if new_role in ('scout', 'coordinator'):
            if new_role == 'coordinator':
                valid_codes = {code for code, _ in COORDINATOR_DISCIPLINE_CHOICES}
                if new_discipline and new_discipline not in valid_codes:
                    messages.error(request, 'Invalid coordinator sport selection.')
                    return redirect('edit_user_roles', user_id=user_obj.id)
            if new_role == 'scout':
                valid_codes = {code for code, _ in SCOUT_DISCIPLINE_CHOICES}
                if new_discipline and new_discipline not in valid_codes:
                    messages.error(request, 'Invalid scout sport/gender selection.')
                    return redirect('edit_user_roles', user_id=user_obj.id)
            user_obj.assigned_discipline = new_discipline
            update_fields.append('assigned_discipline')
        elif old_role in ('scout', 'coordinator') and new_role not in ('scout', 'coordinator'):
            user_obj.assigned_discipline = ''
            update_fields.append('assigned_discipline')

        if new_role in (UserRole.SUBCOUNTY_SPORTS_OFFICER, 'team_manager'):
            user_obj.county = new_county
            user_obj.sub_county = new_sub_county
            update_fields.extend(['county', 'sub_county'])
        else:
            user_obj.county = new_county
            user_obj.sub_county = ''
            update_fields.extend(['county', 'sub_county'])

        user_obj.save(update_fields=update_fields)

        # Handle referee profile creation/removal
        if new_role == 'referee' and old_role != 'referee':
            from referees.models import RefereeProfile
            RefereeProfile.objects.get_or_create(
                user=user_obj,
                defaults={
                    'county': user_obj.county or '',
                    'is_approved': True,
                    'approved_by': request.user,
                    'approved_at': timezone.now(),
                },
            )

        # Audit log
        ActivityLog.objects.create(
            user=request.user,
            action='USER_UPDATE',
            description=(
                f'{request.user.get_full_name()} changed role for {user_obj.email}: '
                f'{dict(UserRole.choices).get(old_role, old_role)} → '
                f'{dict(UserRole.choices).get(new_role, new_role)}'
            ),
            object_repr=str(user_obj),
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

        messages.success(request, f"Role updated for {user_obj.email} → {dict(UserRole.choices).get(new_role, new_role)}.")
        return redirect('user_detail', user_id=user_obj.id)

    context = {
        'edit_user': user_obj,
        'role_choices': UserRole.choices,
        'sport_type_choices': COORDINATOR_DISCIPLINE_CHOICES,
        'scout_sport_type_choices': SCOUT_DISCIPLINE_CHOICES,
        'county_choices': KenyaCounty.choices,
        'subcounty_choices': MakueniSubCounty.choices,
    }
    return render(request, 'admin_dashboard/edit_user_roles.html', context)


@login_required
@user_passes_test(superadmin_required)
def delete_user(request, user_id):
    """Delete a user account."""
    user_obj = get_object_or_404(User, id=user_id)

    if user_obj == request.user:
        messages.error(request, "Cannot delete your own account!")
        return redirect('manage_league_admins')

    if user_obj.is_superuser:
        messages.error(request, "Cannot delete superuser accounts!")
        return redirect('manage_league_admins')

    email = user_obj.email

    # Audit log before deletion
    ActivityLog.objects.create(
        user=request.user,
        action='USER_DELETE',
        description=f'{request.user.get_full_name()} deleted user: {email} (role: {user_obj.get_role_display()})',
        object_repr=email,
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    user_obj.delete()
    messages.success(request, f"User '{email}' deleted.")
    return redirect('manage_league_admins')


# ══════════════════════════════════════════════════════════════════════════════
#   USER DETAIL / EDIT PROFILE (Super Admin)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(superadmin_required)
def user_detail_view(request, user_id):
    """Comprehensive user detail page — view and edit all profile fields."""
    from accounts.models import KenyaCounty
    from django.core.paginator import Paginator

    user_obj = get_object_or_404(User, id=user_id)

    # Gather related data
    managed_teams = None
    referee_profile = None

    try:
        managed_teams = Team.objects.filter(manager=user_obj)
    except Exception:
        pass

    try:
        referee_profile = user_obj.referee_profile
    except (RefereeProfile.DoesNotExist, AttributeError):
        pass

    # Appointment history (if referee)
    appointments = []
    if referee_profile:
        appointments = RefereeAppointment.objects.filter(
            referee=referee_profile
        ).select_related(
            'fixture__home_team', 'fixture__away_team', 'fixture__competition'
        ).order_by('-fixture__match_date')[:10]

    # ── Full Activity Log with filters & pagination ──
    all_logs = ActivityLog.objects.filter(user=user_obj).order_by('-timestamp')

    # Filters from query string
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_q = request.GET.get('search', '')

    if action_filter:
        all_logs = all_logs.filter(action=action_filter)
    if date_from:
        try:
            all_logs = all_logs.filter(timestamp__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            all_logs = all_logs.filter(timestamp__lt=datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            pass
    if search_q:
        all_logs = all_logs.filter(
            Q(description__icontains=search_q) | Q(object_repr__icontains=search_q)
        )

    total_log_count = all_logs.count()

    # Activity category counts (unfiltered, for summary cards)
    unfiltered_logs = ActivityLog.objects.filter(user=user_obj)
    activity_summary = {
        'total': unfiltered_logs.count(),
        'team': unfiltered_logs.filter(action__istartswith='TEAM').count(),
        'player': unfiltered_logs.filter(action__istartswith='PLAYER').count(),
        'match': unfiltered_logs.filter(action__icontains='MATCH').count() + unfiltered_logs.filter(action__istartswith='FIXTURE').count(),
        'user_mgmt': unfiltered_logs.filter(action__istartswith='USER').count() + unfiltered_logs.filter(action__in=['PASSWORD_CHANGE', 'LOGIN', 'LOGOUT']).count(),
        'referee': unfiltered_logs.filter(action__istartswith='REFEREE').count(),
        'payment': unfiltered_logs.filter(action__istartswith='PAYMENT').count(),
        'other': unfiltered_logs.exclude(
            action__istartswith='TEAM'
        ).exclude(
            action__istartswith='PLAYER'
        ).exclude(
            action__icontains='MATCH'
        ).exclude(
            action__istartswith='FIXTURE'
        ).exclude(
            action__istartswith='USER'
        ).exclude(
            action__in=['PASSWORD_CHANGE', 'LOGIN', 'LOGOUT']
        ).exclude(
            action__istartswith='REFEREE'
        ).exclude(
            action__istartswith='PAYMENT'
        ).count(),
    }

    # Unique action types for filter dropdown
    action_types_used = (
        ActivityLog.objects.filter(user=user_obj)
        .values_list('action', flat=True)
        .distinct()
        .order_by('action')
    )
    action_choices = [(a, dict(ActivityLog.ACTION_CHOICES).get(a, a)) for a in action_types_used]

    # Paginate
    paginator = Paginator(all_logs, 25)
    page_number = request.GET.get('page', 1)
    activity_page = paginator.get_page(page_number)

    context = {
        'detail_user': user_obj,
        'managed_teams': managed_teams,
        'referee_profile': referee_profile,
        'appointments': appointments,
        'activity_page': activity_page,
        'total_log_count': total_log_count,
        'activity_summary': activity_summary,
        'action_choices': action_choices,
        'action_filter': action_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_q': search_q,
        'role_choices': UserRole.choices,
        'county_choices': KenyaCounty.choices,
    }
    return render(request, 'admin_dashboard/user_detail.html', context)


@login_required
@user_passes_test(superadmin_required)
def user_edit_profile(request, user_id):
    """Edit user profile details (name, email, phone, sub-county, etc.)."""

    user_obj = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        old_email = user_obj.email
        new_email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        county = 'Makueni'
        sub_county = request.POST.get('sub_county', '').strip()

        if phone:
            try:
                phone = validate_kenya_phone_or_raise(phone, 'Phone number')
            except ValidationError as exc:
                messages.error(request, str(exc))
                return redirect('user_detail', user_id=user_obj.id)

        # Validate email uniqueness
        if new_email and new_email != old_email:
            if User.objects.filter(email=new_email).exclude(pk=user_obj.pk).exists():
                messages.error(request, f"Email '{new_email}' is already in use by another account.")
                return redirect('user_detail', user_id=user_obj.id)

        changes = []
        if new_email and new_email != user_obj.email:
            changes.append(f'email: {user_obj.email} → {new_email}')
            user_obj.email = new_email
        if first_name and first_name != user_obj.first_name:
            changes.append(f'first_name: {user_obj.first_name} → {first_name}')
            user_obj.first_name = first_name
        if last_name and last_name != user_obj.last_name:
            changes.append(f'last_name: {user_obj.last_name} → {last_name}')
            user_obj.last_name = last_name
        if phone != user_obj.phone:
            changes.append(f'phone: {user_obj.phone or "(empty)"} → {phone or "(empty)"}')
            user_obj.phone = phone
        if county != user_obj.county:
            changes.append(f'county: {user_obj.county or "(empty)"} → {county or "(empty)"}')
            user_obj.county = county
        if sub_county != (user_obj.sub_county or ''):
            changes.append(f'sub_county: {user_obj.sub_county or "(empty)"} → {sub_county or "(empty)"}')
            user_obj.sub_county = sub_county

        if changes:
            user_obj.save()
            ActivityLog.objects.create(
                user=request.user,
                action='USER_UPDATE',
                description=(
                    f'{request.user.get_full_name()} edited profile for {user_obj.email}: '
                    + '; '.join(changes)
                ),
                object_repr=str(user_obj),
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(request, f'Profile updated for {user_obj.get_full_name()}.')
        else:
            messages.info(request, 'No changes were made.')

        return redirect('user_detail', user_id=user_obj.id)

    # GET - show edit form
    context = {
        'detail_user': user_obj,
        'role_choices': UserRole.choices,
        'subcounty_choices': MakueniSubCounty.choices,
    }
    return render(request, 'admin_dashboard/user_edit_profile.html', context)


@login_required
@user_passes_test(superadmin_required)
def user_suspend_toggle(request, user_id):
    """Suspend or unsuspend a user account."""
    user_obj = get_object_or_404(User, id=user_id)

    if user_obj == request.user:
        messages.error(request, "Cannot suspend your own account!")
        return redirect('user_detail', user_id=user_obj.id)

    if user_obj.is_superuser:
        messages.error(request, "Cannot suspend superuser accounts!")
        return redirect('user_detail', user_id=user_obj.id)

    user_obj.is_suspended = not user_obj.is_suspended
    user_obj.save(update_fields=['is_suspended'])

    action_word = 'suspended' if user_obj.is_suspended else 'unsuspended'
    ActivityLog.objects.create(
        user=request.user,
        action='USER_UPDATE',
        description=f'{request.user.get_full_name()} {action_word} user: {user_obj.email}',
        object_repr=str(user_obj),
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    if user_obj.is_suspended:
        messages.warning(request, f'🚫 {user_obj.email} has been suspended. They can no longer log in.')
    else:
        messages.success(request, f'✅ {user_obj.email} has been unsuspended. Access restored.')

    return redirect('user_detail', user_id=user_obj.id)


@login_required
@user_passes_test(superadmin_required)
def user_force_password(request, user_id):
    """Set a specific password for a user (super admin only)."""
    user_obj = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        force_change = request.POST.get('force_change', '') == 'on'

        if not new_password:
            messages.error(request, 'Password cannot be empty.')
            return redirect('user_detail', user_id=user_obj.id)

        if len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('user_detail', user_id=user_obj.id)

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('user_detail', user_id=user_obj.id)

        user_obj.set_password(new_password)
        user_obj.must_change_password = force_change
        user_obj.save(update_fields=['password', 'must_change_password'])

        ActivityLog.objects.create(
            user=request.user,
            action='PASSWORD_CHANGE',
            description=f'{request.user.get_full_name()} manually set password for {user_obj.email}',
            object_repr=str(user_obj),
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

        messages.success(request, f'Password set for {user_obj.email}.' +
                         (' They must change it on next login.' if force_change else ''))
        return redirect('user_detail', user_id=user_obj.id)

    return redirect('user_detail', user_id=user_obj.id)


@login_required
@user_passes_test(superadmin_required)
def user_toggle_staff(request, user_id):
    """Toggle is_staff status for a user."""
    user_obj = get_object_or_404(User, id=user_id)

    if user_obj == request.user:
        messages.error(request, "Cannot modify your own staff status!")
        return redirect('user_detail', user_id=user_obj.id)

    user_obj.is_staff = not user_obj.is_staff
    user_obj.save(update_fields=['is_staff'])

    status = 'granted' if user_obj.is_staff else 'revoked'
    ActivityLog.objects.create(
        user=request.user,
        action='USER_UPDATE',
        description=f'{request.user.get_full_name()} {status} staff access for {user_obj.email}',
        object_repr=str(user_obj),
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    messages.success(request, f'Staff access {status} for {user_obj.email}.')
    return redirect('user_detail', user_id=user_obj.id)


# ══════════════════════════════════════════════════════════════════════════════
#   PLACEHOLDER VIEWS for features referenced in urls.py
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def manage_transfers(request):
    """Placeholder: Transfer management (future feature)."""
    messages.info(request, "Transfer system coming soon.")
    return redirect('dashboard')


@login_required
@user_passes_test(admin_required)
def admin_override_transfer(request, transfer_id):
    """Placeholder: Transfer override (future feature)."""
    messages.info(request, "Transfer system coming soon.")
    return redirect('dashboard')
