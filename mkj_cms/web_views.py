"""
MKJ SUPA CUP CMS — Web Frontend Views (Template-Based Portals)
Includes public website pages, public registration, and authenticated CMS portal views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.core.mail import EmailMultiAlternatives
from django.conf import settings as django_settings
from functools import wraps
import csv
import secrets, string, json, re

from accounts.models import User, UserRole, KenyaCounty
from competitions.models import (
    Competition, Fixture, SportType, EXHIBITION_SPORTS, COUNTY_REGISTRATION_FEE_CAP,
    CountyPayment, PaymentStatus, CompetitionStatus,
)
from teams.models import (
    Team, Player, VerificationStatus, RejectionReason, PLAYER_MIN_AGE, PLAYER_MAX_AGE,
    CountyRegistration, CountyRegStatus, CountyDiscipline, CountyPlayer, SQUAD_LIMITS,
    TechnicalBenchMember, TechnicalBenchRole, PlayerStatus,
    CountyDelegationMember, CountyDelegationRole,
)
from teams.forms import (
    PlayerRegistrationForm,
    CountyAdminRegistrationForm, CountyPaymentForm, CountyPlayerForm,
    TechnicalBenchForm, CountyDelegationMemberForm,
)
from referees.models import (
    RefereeProfile, RefereeAppointment, RefereeAvailability,
    AppointmentStatus, AvailabilityStatus, AppointmentRole, RefereeType,
    get_required_roles, get_head_official_role, HEAD_OFFICIAL_ROLES,
)
from referees.forms import RefereeRegistrationForm
from matches.models import MatchReport, MatchEvent, MatchReportStatus, SquadSubmission, SquadPlayer, SquadStatus, get_sport_family
from datetime import date, timedelta


# ── ROLE DECORATOR ────────────────────────────────────────────────────────────
def role_required(*roles):
    """Allow access only to users with the given role(s)."""
    def decorator(view):
        @wraps(view)
        @login_required(login_url='web_login')
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles and not request.user.is_superuser:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('dashboard')
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def send_credentials_email(user, temporary_password, role_label):
    """Send login credentials to the registrant's email address and print to terminal."""
    subject = f'MKJ SUPA CUP Portal Access - {role_label}'
    text_content = (
        f'Dear {user.first_name} {user.last_name},\n\n'
        f'Your MKJ SUPA CUP portal account is ready.\n\n'
        f'Login Email: {user.email}\n'
        f'Temporary Password: {temporary_password}\n'
        f'Role: {role_label}\n\n'
        f'Login URL: /portal/login/\n\n'
        f'Please change your password immediately after first login.\n\n'
        f'MKJ SUPA CUP Administration'
    )
    print("\n=== NEW USER ACCOUNT EMAIL ===\n" + text_content + "\n============================\n")
    email = EmailMultiAlternatives(
        subject,
        text_content,
        getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@mkjsupacup.go.ke'),
        [user.email],
    )
    email.send(fail_silently=False)


COORDINATOR_DISCIPLINE_CHOICES = [
    ("football", "Football"),
    ("volleyball", "Volleyball"),
    ("basketball", "Basketball"),
    ("handball", "Handball"),
]

COORDINATOR_DISCIPLINE_VARIANTS = {
    "football": [SportType.FOOTBALL_MEN, SportType.FOOTBALL_WOMEN],
    "volleyball": [SportType.VOLLEYBALL_MEN, SportType.VOLLEYBALL_WOMEN],
    "basketball": [
        SportType.BASKETBALL_MEN,
        SportType.BASKETBALL_WOMEN,
        SportType.BASKETBALL_3X3_MEN,
        SportType.BASKETBALL_3X3_WOMEN,
    ],
    "handball": [SportType.HANDBALL_MEN, SportType.HANDBALL_WOMEN],
}


def _normalize_coordinator_discipline(value):
    raw_value = (value or "").strip()
    if not raw_value:
        return None
    if raw_value in COORDINATOR_DISCIPLINE_VARIANTS:
        return raw_value
    sport_family = get_sport_family(raw_value)
    if sport_family in ("basketball_5x5", "basketball_3x3"):
        return "basketball"
    return sport_family if sport_family in COORDINATOR_DISCIPLINE_VARIANTS else raw_value


def _coordinator_variants(discipline):
    normalized = _normalize_coordinator_discipline(discipline)
    if not normalized:
        return []
    return COORDINATOR_DISCIPLINE_VARIANTS.get(normalized, [normalized])


def _coordinator_label(discipline):
    normalized = _normalize_coordinator_discipline(discipline)
    return dict(COORDINATOR_DISCIPLINE_CHOICES).get(normalized, normalized or "Not Assigned")


def _get_primary_registration_for_user(user, auto_create=False):
    if user.role == UserRole.COUNTY_SPORTS_DIRECTOR:
        return get_object_or_404(CountyRegistration, user=user)

    county = (getattr(user, "county", "") or "").strip()
    if not county:
        return None

    registration = CountyRegistration.objects.filter(county__iexact=county).order_by("created_at").first()
    if registration or not auto_create:
        return registration

    return CountyRegistration.objects.create(
        user=user,
        county=county,
        director_name=user.get_full_name() or user.email,
        director_phone=user.phone or "+254700000000",
        status=CountyRegStatus.APPROVED,
        approved_by=user if user.is_superuser else None,
        approved_at=timezone.now(),
    )


def _discipline_queryset_for_user(user):
    disciplines = CountyDiscipline.objects.select_related("registration", "linked_team")
    if user.role == UserRole.COUNTY_SPORTS_DIRECTOR:
        return disciplines.filter(registration__user=user)
    if user.role == UserRole.SUBCOUNTY_SPORTS_OFFICER:
        return disciplines.filter(
            registration__county=user.county,
            sub_county=user.sub_county,
        )
    return disciplines


def _get_managed_discipline(user, discipline_pk):
    return get_object_or_404(_discipline_queryset_for_user(user), pk=discipline_pk)


# ══════════════════════════════════════════════════════════════════════════════
#   PUBLIC WEBSITE VIEWS (No login required)
# ══════════════════════════════════════════════════════════════════════════════

def home_view(request):
    """Public homepage with hero, upcoming fixtures, recent results, stats."""
    now = timezone.now()
    stats = {
        'competitions': Competition.objects.count(),
        'teams': Team.objects.count(),
        'players': Player.objects.count(),
    }
    upcoming_fixtures = Fixture.objects.filter(
        match_date__gte=now
    ).select_related(
        'competition', 'home_team', 'away_team', 'venue'
    ).order_by('match_date')[:6]

    recent_results = Fixture.objects.filter(
        status='completed'
    ).select_related(
        'competition', 'home_team', 'away_team', 'venue'
    ).order_by('-match_date')[:6]

    return render(request, 'public/home.html', {
        'active_page': 'home',
        'stats': stats,
        'upcoming_fixtures': upcoming_fixtures,
        'recent_results': recent_results,
    })


def about_view(request):
    """Public about page with mission, values, and county list."""
    stats = {
        'competitions': Competition.objects.count(),
        'teams': Team.objects.count(),
        'players': Player.objects.count(),
    }
    return render(request, 'public/about.html', {
        'active_page': 'about',
        'stats': stats,
        'counties': KenyaCounty.choices,
    })


def public_competitions_view(request):
    """Public competitions listing — grouped by sport, with exhibition marker."""
    all_comps = Competition.objects.all()
    active    = all_comps.filter(status='active')
    upcoming  = all_comps.filter(status__in=['upcoming', 'registration'])
    completed = all_comps.filter(status='completed')

    # Flat catalogue — used for per-sport competition sections
    SPORT_CATALOGUE = [
        {'key': SportType.FOOTBALL_MEN,       'label': 'Football (Men)',          'icon': '\u26BD', 'exhibition': False},
        {'key': SportType.FOOTBALL_WOMEN,     'label': 'Football (Women)',        'icon': '\u26BD', 'exhibition': False},
        {'key': SportType.VOLLEYBALL_MEN,     'label': 'Volleyball (Men)',        'icon': '\U0001F3D0', 'exhibition': False},
        {'key': SportType.VOLLEYBALL_WOMEN,   'label': 'Volleyball (Women)',      'icon': '\U0001F3D0', 'exhibition': False},
        {'key': SportType.BASKETBALL_MEN,     'label': 'Basketball 5\u00D75 (Men)',   'icon': '\U0001F3C0', 'exhibition': False},
        {'key': SportType.BASKETBALL_WOMEN,   'label': 'Basketball 5\u00D75 (Women)', 'icon': '\U0001F3C0', 'exhibition': False},
        {'key': SportType.BASKETBALL_3X3_MEN,   'label': 'Basketball 3\u00D73 (Men)',   'icon': '\U0001F3C0', 'exhibition': False},
        {'key': SportType.BASKETBALL_3X3_WOMEN, 'label': 'Basketball 3\u00D73 (Women)', 'icon': '\U0001F3C0', 'exhibition': False},
        {'key': SportType.HANDBALL_MEN,       'label': 'Handball (Men)',          'icon': '\U0001F93E', 'exhibition': False},
        {'key': SportType.HANDBALL_WOMEN,     'label': 'Handball (Women)',        'icon': '\U0001F93E', 'exhibition': False},
    ]

    # Grouped disciplines — for the top tile grid with dropdowns
    DISCIPLINES = [
        {
            'name': 'Football', 'icon': '\u26BD', 'exhibition': False,
            'variants': [
                {'key': SportType.FOOTBALL_MEN,   'label': 'Men'},
                {'key': SportType.FOOTBALL_WOMEN, 'label': 'Women'},
            ],
        },
        {
            'name': 'Volleyball', 'icon': '\U0001F3D0', 'exhibition': False,
            'variants': [
                {'key': SportType.VOLLEYBALL_MEN,   'label': 'Men'},
                {'key': SportType.VOLLEYBALL_WOMEN, 'label': 'Women'},
            ],
        },
        {
            'name': 'Basketball 5\u00D75', 'icon': '\U0001F3C0', 'exhibition': False,
            'variants': [
                {'key': SportType.BASKETBALL_MEN,   'label': 'Men'},
                {'key': SportType.BASKETBALL_WOMEN, 'label': 'Women'},
            ],
        },
        {
            'name': 'Basketball 3\u00D73', 'icon': '\U0001F3C0', 'exhibition': False,
            'variants': [
                {'key': SportType.BASKETBALL_3X3_MEN,   'label': 'Men'},
                {'key': SportType.BASKETBALL_3X3_WOMEN, 'label': 'Women'},
            ],
        },
        {
            'name': 'Handball', 'icon': '\U0001F93E', 'exhibition': False,
            'variants': [
                {'key': SportType.HANDBALL_MEN,   'label': 'Men'},
                {'key': SportType.HANDBALL_WOMEN, 'label': 'Women'},
            ],
        },
    ]

    return render(request, 'public/competitions.html', {
        'active_page': 'competitions',
        'active_competitions': active,
        'upcoming_competitions': upcoming,
        'completed_competitions': completed,
        'sport_catalogue': SPORT_CATALOGUE,
        'disciplines': DISCIPLINES,
        'all_competitions': all_comps,
    })


def public_competition_detail_view(request, pk):
    """Public competition detail with teams and fixtures."""
    competition = get_object_or_404(Competition, pk=pk)
    teams = Team.objects.filter(competition=competition)
    fixtures = Fixture.objects.filter(competition=competition).select_related(
        'home_team', 'away_team', 'venue'
    ).order_by('match_date')
    return render(request, 'public/competition_detail.html', {
        'active_page': 'competitions',
        'competition': competition,
        'teams': teams,
        'fixtures': fixtures,
    })


def public_results_view(request):
    """Public results page — completed matches, upcoming fixtures, and competition links."""
    now = timezone.now()
    sport_filter = request.GET.get('sport', '').strip()
    valid_sports = {c.value for c in SportType}
    sport_filter = sport_filter if sport_filter in valid_sports else ''

    completed_qs = Fixture.objects.filter(status='completed')
    upcoming_qs = Fixture.objects.filter(match_date__gte=now).exclude(status='completed')
    active_comps_qs = Competition.objects.filter(status__in=['active', 'group_stage', 'knockout'])
    completed_comps_qs = Competition.objects.filter(status='completed')

    if sport_filter:
        completed_qs = completed_qs.filter(competition__sport_type=sport_filter)
        upcoming_qs = upcoming_qs.filter(competition__sport_type=sport_filter)
        active_comps_qs = active_comps_qs.filter(sport_type=sport_filter)
        completed_comps_qs = completed_comps_qs.filter(sport_type=sport_filter)

    completed = completed_qs.select_related(
        'competition', 'home_team', 'away_team', 'venue'
    ).order_by('-match_date')[:30]

    upcoming = upcoming_qs.select_related(
        'competition', 'home_team', 'away_team', 'venue'
    ).order_by('match_date')[:15]

    active_competitions = active_comps_qs.order_by('name')
    completed_competitions = completed_comps_qs.order_by('-end_date')[:10]

    # Build display label for active filter
    sport_display = ''
    if sport_filter:
        sport_display = dict(SportType.choices).get(sport_filter, sport_filter)

    return render(request, 'public/results.html', {
        'active_page': 'results',
        'completed_fixtures': completed,
        'upcoming_fixtures': upcoming,
        'active_competitions': active_competitions,
        'completed_competitions': completed_competitions,
        'sport_filter': sport_filter,
        'sport_display': sport_display,
        'sport_choices': SportType.choices,
    })


def public_statistics_view(request):
    """
    Public statistics hub — top scorers, assist leaders, disciplinary,
    and clean sheet leaders across all active/completed competitions.
    Users can filter by competition.
    """
    from competitions.models import Pool, PoolTeam
    from matches.models import PlayerStatistics
    from matches.stats_engine import (
        get_top_scorers, get_top_assisters,
        get_disciplinary_table, get_clean_sheet_leaders, get_fair_play_table,
    )
    from django.db.models import F, Sum

    # Competitions available for filtering
    competitions = Competition.objects.filter(
        status__in=['active', 'group_stage', 'knockout', 'completed']
    ).order_by('-start_date')

    # Optional competition filter
    comp_id = request.GET.get('competition', '')
    selected_competition = None

    if comp_id:
        try:
            selected_competition = Competition.objects.get(pk=comp_id)
        except Competition.DoesNotExist:
            pass

    if selected_competition:
        top_scorers = get_top_scorers(selected_competition, limit=20)
        top_assisters = get_top_assisters(selected_competition, limit=20)
        disciplinary = get_disciplinary_table(selected_competition, limit=20)
        clean_sheets = get_clean_sheet_leaders(selected_competition, limit=10)
    else:
        # Aggregate across all active/completed competitions
        top_scorers = PlayerStatistics.objects.filter(
            goals__gt=0,
            competition__status__in=['active', 'group_stage', 'knockout', 'completed'],
        ).select_related('player', 'team', 'competition').order_by('-goals', '-assists')[:20]

        top_assisters = PlayerStatistics.objects.filter(
            assists__gt=0,
            competition__status__in=['active', 'group_stage', 'knockout', 'completed'],
        ).select_related('player', 'team', 'competition').order_by('-assists', '-goals')[:20]

        disciplinary = PlayerStatistics.objects.filter(
            competition__status__in=['active', 'group_stage', 'knockout', 'completed'],
        ).annotate(
            total_cards=F('yellow_cards') + F('red_cards')
        ).filter(total_cards__gt=0).select_related(
            'player', 'team', 'competition'
        ).order_by('-red_cards', '-yellow_cards')[:20]

        clean_sheets = PlayerStatistics.objects.filter(
            clean_sheets__gt=0,
            player__position='GK',
            competition__status__in=['active', 'group_stage', 'knockout', 'completed'],
        ).select_related('player', 'team', 'competition').order_by('-clean_sheets')[:10]

    # Summary stats
    total_goals = PlayerStatistics.objects.filter(
        competition__status__in=['active', 'group_stage', 'knockout', 'completed'],
    ).aggregate(total=Sum('goals'))['total'] or 0
    total_matches = Fixture.objects.filter(status='completed').count()
    total_cards = PlayerStatistics.objects.filter(
        competition__status__in=['active', 'group_stage', 'knockout', 'completed'],
    ).aggregate(
        yellows=Sum('yellow_cards'),
        reds=Sum('red_cards'),
    )

    return render(request, 'public/statistics.html', {
        'active_page': 'results',
        'competitions': competitions,
        'selected_competition': selected_competition,
        'top_scorers': top_scorers,
        'top_assisters': top_assisters,
        'disciplinary': disciplinary,
        'clean_sheets': clean_sheets,
        'total_goals': total_goals,
        'total_matches': total_matches,
        'total_yellows': total_cards['yellows'] or 0,
        'total_reds': total_cards['reds'] or 0,
    })


def public_competition_standings_view(request, pk):
    """
    Public competition standings — pool tables, knockout bracket, and top stats.
    Auto-updated from approved match reports.
    """
    from competitions.models import Pool, PoolTeam, KnockoutRound
    from matches.stats_engine import (
        get_top_scorers, get_top_assisters,
        get_disciplinary_table, get_clean_sheet_leaders,
    )

    competition = get_object_or_404(Competition, pk=pk)

    # Pool standings
    pools = Pool.objects.filter(competition=competition).prefetch_related(
        'pool_teams__team'
    ).order_by('name')

    pool_standings = []
    for pool in pools:
        teams = pool.pool_teams.select_related('team').all()
        sorted_teams = sorted(
            teams,
            key=lambda pt: (pt.points, pt.goal_difference, pt.goals_for),
            reverse=True,
        )
        pool_standings.append({'pool': pool, 'teams': sorted_teams})

    # Knockout bracket
    knockout_fixtures = Fixture.objects.filter(
        competition=competition, is_knockout=True
    ).select_related(
        'home_team', 'away_team', 'venue', 'winner'
    ).order_by('knockout_round', 'bracket_position', 'match_date')

    knockout_rounds = {}
    for f in knockout_fixtures:
        round_name = f.get_knockout_round_display() if f.knockout_round else 'Unknown'
        if round_name not in knockout_rounds:
            knockout_rounds[round_name] = []
        knockout_rounds[round_name].append(f)

    # Recent results for this competition
    recent_results = Fixture.objects.filter(
        competition=competition, status='completed'
    ).select_related('home_team', 'away_team', 'venue').order_by('-match_date')[:10]

    # Upcoming fixtures
    upcoming = Fixture.objects.filter(
        competition=competition,
        match_date__gte=timezone.now(),
    ).exclude(status='completed').select_related(
        'home_team', 'away_team', 'venue'
    ).order_by('match_date')[:10]

    # Statistics
    top_scorers = get_top_scorers(competition, limit=10)
    top_assisters = get_top_assisters(competition, limit=10)
    disciplinary = get_disciplinary_table(competition, limit=10)
    clean_sheets = get_clean_sheet_leaders(competition, limit=5)
    fair_play_table = get_fair_play_table(competition, limit=10)

    return render(request, 'public/competition_standings.html', {
        'active_page': 'results',
        'competition': competition,
        'pool_standings': pool_standings,
        'knockout_rounds': knockout_rounds,
        'recent_results': recent_results,
        'upcoming_fixtures': upcoming,
        'top_scorers': top_scorers,
        'top_assisters': top_assisters,
        'disciplinary': disciplinary,
        'clean_sheets': clean_sheets,
        'fair_play_table': fair_play_table,
    })


def contact_view(request):
    """Public contact page with form."""
    contact_sent = False
    if request.method == 'POST':
        # In production: send email, save to DB, etc.
        contact_sent = True
        messages.success(request, 'Thank you for your message! We will get back to you soon.')
    return render(request, 'public/contact.html', {
        'active_page': 'contact',
        'contact_sent': contact_sent,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   CMS PORTAL VIEWS (Login required)
# ══════════════════════════════════════════════════════════════════════════════

# ── AUTH VIEWS ────────────────────────────────────────────────────────────────

def web_login_view(request):
    """Login page — redirects to dashboard if already authenticated."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if getattr(user, 'is_suspended', False):
                return render(request, 'accounts/login.html', {
                    'error': 'Your account has been suspended. Please contact the administrator.',
                    'email': email,
                })
            login(request, user)
            if getattr(user, 'must_change_password', False):
                messages.warning(request, 'You must change your password before continuing.')
                return redirect('force_change_password')
            messages.success(request, f'Welcome back, {user.first_name}!')
            return redirect('dashboard')
        else:
            return render(request, 'accounts/login.html', {
                'error': 'Invalid email or password. Please try again.',
                'email': email,
            })

    return render(request, 'accounts/login.html')


@login_required(login_url='web_login')
def force_change_password_view(request):
    """Force users with one-time passwords to set a new password."""
    if not getattr(request.user, 'must_change_password', False):
        return redirect('dashboard')

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        elif len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            request.user.set_password(new_password)
            request.user.must_change_password = False
            request.user.save(update_fields=['password', 'must_change_password'])
            login(request, request.user)
            messages.success(request, 'Password changed successfully! Welcome to MKJ SUPA CUP CMS.')
            return redirect('dashboard')

    return render(request, 'accounts/force_change_password.html')


def web_logout_view(request):
    """Logout and redirect to home page."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@login_required(login_url='web_login')
def dashboard_view(request):
    """Role-based dashboard with stats and recent fixtures."""
    user = request.user

    stats = {
        'competitions': Competition.objects.count(),
        'teams': Team.objects.count(),
        'referees': RefereeProfile.objects.filter(is_approved=True).count(),
        'fixtures': Fixture.objects.count(),
        'players': Player.objects.count(),
    }

    # For team managers, show only their team's data
    if user.role == 'treasurer':
        return redirect('treasurer_dashboard')

    if user.role == 'referee':
        return redirect('referee_portal')

    if user.role == 'competition_manager':
        return redirect('cm_dashboard')

    if user.role == 'verification_officer':
        return redirect('vo_registered_counties')

    if user.role == 'coordinator':
        return redirect('coordinator_dashboard')

    if user.role == 'county_sports_admin':
        return redirect('county_admin_dashboard')

    if user.role == 'cec_sports':
        return redirect('dashboard')

    if user.role == 'team_manager':
        return redirect('team_manager_dashboard')

    if user.role == 'secretary_general':
        return redirect('sg_dashboard')

    if user.role == 'jury_chair':
        return redirect('jury_dashboard')

    if user.role == 'media_manager':
        return redirect('media_dashboard')

    if user.role == 'scout':
        return redirect('scout_dashboard')

    if user.role == 'subcounty_sports_officer':
        return redirect('subcounty_officer_dashboard')

    if user.role == 'chief_sports_officer':
        return redirect('chief_officer_sports_dashboard')

    if user.role == 'director_sports':
        return redirect('director_sports_dashboard')

    if user.role == 'chief_officer_sports':
        return redirect('chief_officer_sports_dashboard')

    recent_fixtures = Fixture.objects.select_related(
        'competition', 'home_team', 'away_team'
    ).order_by('-match_date')[:10]

    return render(request, 'dashboard/index.html', {
        'stats': stats,
        'recent_fixtures': recent_fixtures,
    })


# ── COMPETITIONS ──────────────────────────────────────────────────────────────

@login_required(login_url='web_login')
def competitions_list_view(request):
    """List all competitions."""
    competitions = Competition.objects.all()
    return render(request, 'competitions/list.html', {
        'competitions': competitions,
    })


@login_required(login_url='web_login')
def competition_detail_view(request, pk):
    """Competition detail with teams and fixtures."""
    competition = get_object_or_404(Competition, pk=pk)
    teams = Team.objects.filter(competition=competition)
    fixtures = Fixture.objects.filter(competition=competition).select_related(
        'home_team', 'away_team', 'venue'
    )
    return render(request, 'competitions/detail.html', {
        'competition': competition,
        'teams': teams,
        'fixtures': fixtures,
    })


# ── TEAMS ─────────────────────────────────────────────────────────────────────

@login_required(login_url='web_login')
def teams_list_view(request):
    """List teams — team managers see only their teams."""
    user = request.user
    if user.role == 'team_manager':
        teams = Team.objects.filter(manager=user)
    else:
        teams = Team.objects.all()
    return render(request, 'teams/list.html', {'teams': teams})


@login_required(login_url='web_login')
def team_detail_view(request, pk):
    """Team detail with players and player management."""
    team = get_object_or_404(Team, pk=pk)
    players = Player.objects.filter(team=team).order_by('shirt_number')

    # Check if user can manage this team
    can_manage = (
        request.user.is_superuser or
        request.user.role in ('admin', 'competition_manager') or
        team.manager == request.user
    )

    return render(request, 'teams/detail.html', {
        'team': team,
        'players': players,
        'can_manage': can_manage,
    })


# ── PLAYER MANAGEMENT ────────────────────────────────────────────────────────

@login_required(login_url='web_login')
def add_player_view(request, team_pk):
    """Add a player to a team (team manager or admin)."""
    team = get_object_or_404(Team, pk=team_pk)

    # Only team manager or admins can add players
    is_manager = team.manager == request.user
    is_admin = request.user.is_superuser or request.user.role in ('admin', 'competition_manager')
    if not is_manager and not is_admin:
        messages.error(request, 'You do not have permission to manage this team.')
        return redirect('teams_list')

    # Suspended teams cannot add players
    if team.status == 'suspended':
        messages.warning(request, 'This team is suspended. Players cannot be added.')
        return redirect('team_detail', pk=team.pk)

    from teams.forms import PlayerRegistrationForm

    if request.method == 'POST':
        form = PlayerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            player = form.save(commit=False)
            player.team = team

            # Check jersey number uniqueness within team
            if Player.objects.filter(team=team, shirt_number=player.shirt_number).exists():
                messages.error(request, f'Shirt number {player.shirt_number} is already taken in this team.')
            elif player.national_id_number and Player.objects.filter(national_id_number=player.national_id_number).exists():
                messages.error(request, f'A player with National ID {player.national_id_number} is already registered.')
            else:
                player.save()

                # ── Save IPRS photo if auto-populated from lookup ────
                iprs_photo_b64 = request.POST.get('iprs_photo_base64', '').strip()
                if iprs_photo_b64:
                    try:
                        from teams.utils import save_base64_photo
                        if save_base64_photo(player, iprs_photo_b64):
                            player.save(update_fields=['iprs_photo'])
                    except Exception:
                        pass  # Don't block player registration

                # ── Auto-trigger FIFA Connect pre-screening ──────────────
                try:
                    from teams.fifa_connect_service import FIFAConnectService
                    from teams.models import FIFAConnectStatus, PlayerVerificationLog, VerificationStep
                    svc = FIFAConnectService()
                    fc_result = svc.check_player(player)
                    if fc_result.is_flagged:
                        player.fifa_connect_status = FIFAConnectStatus.FLAGGED
                        player.fifa_connect_leagues = fc_result.leagues_found
                        player.fifa_connect_notes = fc_result.flag_reason
                        if fc_result.fifa_connect_id:
                            player.fifa_connect_id = fc_result.fifa_connect_id
                        player.save()
                        PlayerVerificationLog.objects.create(
                            player=player,
                            step=VerificationStep.FIFA_CONNECT,
                            action='auto_screen_on_add',
                            result='flagged',
                            details={'leagues_found': fc_result.leagues_found},
                            notes=fc_result.flag_reason,
                        )
                        messages.warning(request, (
                            f'🚩 FIFA Connect WARNING: {player.get_full_name()} '
                            f'may be registered in a higher-level league. '
                            f'Requires clearance review before participation.'
                        ))
                    elif fc_result.is_clear:
                        player.fifa_connect_status = FIFAConnectStatus.CLEAR
                        if fc_result.fifa_connect_id:
                            player.fifa_connect_id = fc_result.fifa_connect_id
                        player.fifa_connect_notes = "Auto-screened on registration — clear."
                        player.save()
                except Exception:
                    pass  # Don't block player registration on API errors

                if not player.is_age_eligible:
                    messages.warning(request, (
                        f'{player.get_full_name()} added but AUTO-REJECTED — '
                        f'age {player.age} is outside the {PLAYER_MIN_AGE}-{PLAYER_MAX_AGE} bracket.'
                    ))
                elif not player.documents_uploaded:
                    messages.info(request, (
                        f'{player.get_full_name()} added to {team.name}. '
                        f'Documents pending — upload ID, birth certificate & photo for verification.'
                    ))
                else:
                    messages.success(request, (
                        f'{player.get_full_name()} added to {team.name}. '
                        f'Documents submitted — pending admin verification.'
                    ))

                action = request.POST.get('action', 'add_more')
                if action == 'finish':
                    return redirect('team_detail', pk=team.pk)
                # Reset form for another player
                form = PlayerRegistrationForm()
    else:
        form = PlayerRegistrationForm()

    existing_players = Player.objects.filter(team=team).order_by('shirt_number')

    return render(request, 'portal/add_player.html', {
        'form': form,
        'team': team,
        'players': existing_players,
        'player_count': existing_players.count(),
    })


@login_required(login_url='web_login')
def edit_player_view(request, player_pk):
    """Edit a player's details."""
    player = get_object_or_404(Player, pk=player_pk)
    team = player.team

    is_manager = team.manager == request.user
    is_admin = request.user.is_superuser or request.user.role in ('admin', 'competition_manager')
    if not is_manager and not is_admin:
        messages.error(request, 'You do not have permission to edit this player.')
        return redirect('teams_list')

    from teams.forms import PlayerRegistrationForm

    if request.method == 'POST':
        form = PlayerRegistrationForm(request.POST, request.FILES, instance=player)
        if form.is_valid():
            # Check jersey number uniqueness (exclude current player)
            new_shirt = form.cleaned_data['shirt_number']
            if Player.objects.filter(team=team, shirt_number=new_shirt).exclude(pk=player.pk).exists():
                messages.error(request, f'Shirt number {new_shirt} is already taken.')
            else:
                form.save()
                messages.success(request, f'{player.get_full_name()} updated.')
                return redirect('team_detail', pk=team.pk)
    else:
        form = PlayerRegistrationForm(instance=player)

    return render(request, 'portal/edit_player.html', {
        'form': form,
        'player': player,
        'team': team,
    })


@login_required(login_url='web_login')
def delete_player_view(request, player_pk):
    """Delete a player from a team."""
    player = get_object_or_404(Player, pk=player_pk)
    team = player.team

    is_manager = team.manager == request.user
    is_admin = request.user.is_superuser or request.user.role in ('admin', 'competition_manager')
    if not is_manager and not is_admin:
        messages.error(request, 'Permission denied.')
        return redirect('teams_list')

    if request.method == 'POST':
        name = player.get_full_name()
        player.delete()
        messages.success(request, f'{name} removed from {team.name}.')
        return redirect('team_detail', pk=team.pk)

    return render(request, 'portal/delete_player.html', {
        'player': player,
        'team': team,
    })


# ── REFEREES ──────────────────────────────────────────────────────────────────

@login_required(login_url='web_login')
def referees_list_view(request):
    """List referees and appointments — sub-county officers do not access referees."""
    user = request.user
    # Sub-county sports officers should not manage or view referees
    if user.role == 'subcounty_sports_officer':
        messages.warning(request, "Referees are managed by Discipline Coordinators.")
        return redirect('subcounty_officer_dashboard')
    if user.role == 'referee':
        try:
            referees = [user.referee_profile]
            appointments = RefereeAppointment.objects.filter(
                referee=user.referee_profile
            ).select_related('fixture__home_team', 'fixture__away_team')
        except RefereeProfile.DoesNotExist:
            referees = []
            appointments = []
    else:
        referees = RefereeProfile.objects.select_related('user').all()
        appointments = RefereeAppointment.objects.select_related(
            'fixture__home_team', 'fixture__away_team', 'referee__user'
        ).order_by('-appointed_at')[:20]

    return render(request, 'referees/list.html', {
        'referees': referees,
        'appointments': appointments,
    })


# ── MATCHES ───────────────────────────────────────────────────────────────────

@login_required(login_url='web_login')
def matches_list_view(request):
    """List fixtures and match reports — with role-appropriate actions."""
    user = request.user

    if user.role == 'team_manager':
        my_teams = Team.objects.filter(manager=user)
        fixtures = Fixture.objects.filter(
            Q(home_team__in=my_teams) | Q(away_team__in=my_teams)
        ).select_related('competition', 'home_team', 'away_team', 'venue').order_by('-match_date')
    elif user.role == 'referee':
        try:
            fixtures = Fixture.objects.filter(
                referee_appointments__referee=user.referee_profile
            ).select_related('competition', 'home_team', 'away_team', 'venue').order_by('-match_date')
        except RefereeProfile.DoesNotExist:
            fixtures = Fixture.objects.none()
    else:
        fixtures = Fixture.objects.select_related(
            'competition', 'home_team', 'away_team', 'venue'
        ).order_by('-match_date')

    # Annotate fixtures with squad / report info for template buttons
    now = timezone.now()
    fixture_data = []
    for f in fixtures:
        fd = {'fixture': f}
        # Squad submission status for this user's team
        if user.role == 'team_manager':
            my_team = f.home_team if f.home_team in my_teams else (f.away_team if f.away_team in my_teams else None)
            if my_team:
                squad = SquadSubmission.objects.filter(fixture=f, team=my_team).first()
                fd['squad'] = squad
                fd['my_team'] = my_team
                try:
                    fd['deadline_passed'] = now > f.squad_deadline
                except Exception:
                    fd['deadline_passed'] = True
        # Match report
        try:
            fd['report'] = f.match_report
        except MatchReport.DoesNotExist:
            fd['report'] = None
        fixture_data.append(fd)

    match_reports = MatchReport.objects.select_related(
        'fixture__home_team', 'fixture__away_team', 'referee__user'
    ).order_by('-submitted_at')[:30]

    # For coordinator: pending reports
    pending_reports = MatchReport.objects.filter(
        status=MatchReportStatus.SUBMITTED
    ).select_related('fixture__home_team', 'fixture__away_team', 'referee__user') if user.role in ('coordinator', 'admin') else []

    return render(request, 'matches/list.html', {
        'fixture_data': fixture_data,
        'fixtures': fixtures,  # Keep backward compat
        'match_reports': match_reports,
        'pending_reports': pending_reports,
    })


# ── PROFILE ───────────────────────────────────────────────────────────────────

@login_required(login_url='web_login')
def profile_view(request):
    """User profile page."""
    return render(request, 'accounts/profile.html')


@login_required(login_url='web_login')
def change_password_view(request):
    """Handle password change."""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not request.user.check_password(old_password):
            messages.error(request, 'Current password is incorrect.')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
        elif len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            request.user.set_password(new_password)
            request.user.must_change_password = False
            request.user.save(update_fields=['password', 'must_change_password'])
            login(request, request.user)
            messages.success(request, 'Password updated successfully!')

    return redirect('web_profile')


# ══════════════════════════════════════════════════════════════════════════════
#   PUBLIC REGISTRATION VIEWS (No login required)
# ══════════════════════════════════════════════════════════════════════════════

def team_register_view(request):
    """Deprecated — team registration is now handled via county registration."""
    return redirect('county_admin_register')


def team_register_success_view(request):
    """Deprecated — redirects to county registration."""
    return redirect('county_admin_register')


def referee_register_view(request):
    """Public referee registration — creates User + RefereeProfile (pending)."""
    if request.method == 'POST':
        form = RefereeRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            # Create user account (inactive until approved)
            random_pw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            user = User.objects.create_user(
                email=cd['email'],
                password=random_pw,
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                phone=cd.get('phone', ''),
                county=cd.get('county', ''),
                role=UserRole.REFEREE,
                is_active=False,
            )
            # Create referee profile
            profile = RefereeProfile.objects.create(
                user=user,
                license_number=cd['license_number'],
                level=cd.get('level') or 'County',
                county=cd.get('county', ''),
                id_number=cd.get('id_number', ''),
                years_experience=cd.get('years_experience') or 0,
                is_approved=False,
            )
            # Save profile picture if uploaded
            if cd.get('profile_picture'):
                profile.profile_picture = cd['profile_picture']
                profile.save(update_fields=['profile_picture'])
            messages.success(request, mark_safe(
                f'<strong>Registration Successful!</strong><br>'
                f'Thank you, <strong>{cd["first_name"]} {cd["last_name"]}</strong>!<br>'
                f'License: <code>{cd["license_number"]}</code><br><br>'
                f'<strong>Next Steps:</strong><br>'
                f'1. Wait for admin approval<br>'
                f'2. You will receive login credentials via email<br>'
                f'3. Log in and change your password'
            ))
            return redirect('referee_register_success')
    else:
        form = RefereeRegistrationForm()
    return render(request, 'public/referee_register.html', {
        'form': form,
        'active_page': 'register',
    })


def referee_register_success_view(request):
    """Success page after referee registration."""
    return render(request, 'public/referee_register_success.html', {
        'active_page': 'register',
    })


# ══════════════════════════════════════════════════════════════════════════════
#   ADMIN / MANAGER — TEAM APPROVAL VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@role_required('admin', 'competition_manager', 'chief_sports_officer')
def pending_teams_view(request):
    """Legacy endpoint kept for compatibility; county registration is now the only channel."""
    messages.info(request, 'Legacy team registration flow has been retired. Use county registrations.')
    return redirect('treasurer_county_registrations')


# ══════════════════════════════════════════════════════════════════════════════
#   ADMIN / MANAGER — REFEREE APPROVAL VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@role_required('admin', 'coordinator')
def pending_referees_view(request):
    """List referees awaiting approval."""
    pending = RefereeProfile.objects.filter(
        is_approved=False
    ).select_related('user').order_by('-created_at')

    if request.method == 'POST':
        profile_id = request.POST.get('profile_id')
        action = request.POST.get('action')
        profile = get_object_or_404(RefereeProfile, pk=profile_id)

        if action == 'approve':
            profile.is_approved = True
            profile.approved_by = request.user
            profile.approved_at = timezone.now()
            profile.save()

            # Activate the user account
            user = profile.user
            user.is_active = True
            temp_pw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
            user.set_password(temp_pw)
            user.must_change_password = True
            user.save(update_fields=['is_active', 'password', 'must_change_password'])

            email_sent = True
            try:
                send_credentials_email(user, temp_pw, 'Referee')
            except Exception:
                email_sent = False

            messages.success(request, mark_safe(
                f'✅ <strong>{user.get_full_name()}</strong> approved!<br>'
                f'Login: <code>{user.email}</code><br>'
                f'Temporary password sent to email. Ask them to change their password on first login.'
            ))
            if not email_sent:
                messages.warning(request, 'Could not send referee credentials email. Please resend manually.')

        elif action == 'reject':
            user = profile.user
            user_name = user.get_full_name()
            profile.delete()
            user.delete()
            messages.warning(request, f'❌ {user_name} registration rejected and removed.')

        return redirect('pending_referees')

    return render(request, 'portal/pending_referees.html', {
        'pending_referees': pending,
        'stats': {
            'pending': pending.count(),
            'approved': RefereeProfile.objects.filter(is_approved=True).count(),
            'total': RefereeProfile.objects.count(),
        },
    })


# ══════════════════════════════════════════════════════════════════════════════
#   ADMIN — PLAYER VERIFICATION VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@role_required('admin', 'competition_manager', 'chief_sports_officer', 'secretary_general', 'verification_officer')
def player_verification_list_view(request):
    """Canonical player verification entry — uses county player verification queue."""
    if request.user.role == 'secretary_general':
        messages.info(request, 'Use the Secretary General verification view for read-only verification summaries.')
        return redirect('sg_verifications')

    return redirect('county_player_verification_list')


@role_required('admin', 'competition_manager', 'chief_sports_officer', 'verification_officer')
def verify_player_view(request, player_pk):
    """Admin view to inspect a single player's documents and verify/reject."""
    player = get_object_or_404(Player, pk=player_pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'verify':
            player.verification_status = VerificationStatus.VERIFIED
            player.rejection_reason = ''
            player.rejection_notes = ''
            player.verified_by = request.user
            player.verified_at = timezone.now()
            player.status = 'eligible'
            player.save()
            # Log to audit trail
            from teams.models import PlayerVerificationLog, VerificationStep
            PlayerVerificationLog.objects.create(
                player=player, step=VerificationStep.DOCUMENT,
                action='verified', result='verified',
                notes='Documents verified by admin.',
                performed_by=request.user,
            )
            messages.success(request, f'✅ {player.get_full_name()} has been verified.')

        elif action == 'reject':
            reason = request.POST.get('rejection_reason', RejectionReason.OTHER)
            notes = request.POST.get('rejection_notes', '')
            player.verification_status = VerificationStatus.REJECTED
            player.rejection_reason = reason
            player.rejection_notes = notes
            player.status = 'ineligible'
            player.verified_by = request.user
            player.verified_at = timezone.now()
            player.save()
            from teams.models import PlayerVerificationLog, VerificationStep
            PlayerVerificationLog.objects.create(
                player=player, step=VerificationStep.DOCUMENT,
                action='rejected', result='rejected',
                details={'reason': reason},
                notes=notes,
                performed_by=request.user,
            )
            messages.warning(request, f'❌ {player.get_full_name()} has been rejected: {player.get_rejection_reason_display()}')

        elif action == 'reset':
            # Allow re-submission — set back to pending
            player.verification_status = VerificationStatus.PENDING
            player.rejection_reason = ''
            player.rejection_notes = ''
            player.verified_by = None
            player.verified_at = None
            player.status = 'eligible'
            player.save()
            from teams.models import PlayerVerificationLog, VerificationStep
            PlayerVerificationLog.objects.create(
                player=player, step=VerificationStep.DOCUMENT,
                action='reset', result='pending',
                notes='Reset to pending by admin.',
                performed_by=request.user,
            )
            messages.info(request, f'🔄 {player.get_full_name()} reset to pending verification.')

        return redirect('player_verification_list')

    return render(request, 'portal/verify_player.html', {
        'player': player,
        'rejection_reasons': RejectionReason.choices,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   SQUAD SELECTION (Team Manager)
# ══════════════════════════════════════════════════════════════════════════════

@role_required('team_manager')
def squad_select_view(request, fixture_pk):
    """Team Manager picks starters & subs with formation, kit, and GK validation."""
    from django.conf import settings as conf

    fixture = get_object_or_404(Fixture, pk=fixture_pk)
    user = request.user

    # Determine the manager's team in this fixture
    my_teams = Team.objects.filter(manager=user)
    if fixture.home_team in my_teams:
        team = fixture.home_team
    elif fixture.away_team in my_teams:
        team = fixture.away_team
    else:
        messages.error(request, 'Your team is not involved in this fixture.')
        return redirect('matches_list')

    # Only treasurer-approved teams can submit squads / play
    if not team.payment_confirmed:
        messages.error(request, 'Your team cannot participate — payment has not been confirmed by the treasurer.')
        return redirect('matches_list')

    deadline = fixture.squad_deadline
    now = timezone.now()
    deadline_passed = now > deadline

    # Existing submission
    existing = SquadSubmission.objects.filter(fixture=fixture, team=team).first()

    # Only FULLY CLEARED players (docs verified + Huduma verified + FIFA Connect clear + eligible status)
    players = Player.objects.filter(
        team=team, status='eligible', verification_status='verified',
        huduma_status='verified', fifa_connect_status='clear',
    ).order_by('shirt_number')

    starter_ids = []
    sub_ids = []
    saved_formation = ''
    saved_kit = 'home'
    if existing:
        starter_ids = list(existing.squad_players.filter(is_starter=True).values_list('player_id', flat=True))
        sub_ids = list(existing.squad_players.filter(is_starter=False).values_list('player_id', flat=True))
        saved_formation = existing.formation
        saved_kit = existing.kit_choice

    if request.method == 'POST':
        if deadline_passed:
            messages.error(request, f'Squad submission deadline has passed ({deadline.strftime("%d %b %Y %H:%M")}).')
            return redirect('matches_list')

        selected_starters = request.POST.getlist('starters')
        selected_subs = request.POST.getlist('subs')
        formation = request.POST.get('formation', '').strip()
        kit_choice = request.POST.get('kit_choice', 'home')

        starters_int = [int(x) for x in selected_starters if x]
        subs_int = [int(x) for x in selected_subs if x]

        # Validate no overlap
        overlap = set(starters_int) & set(subs_int)
        errors = []
        if overlap:
            errors.append('A player cannot be both a starter and a substitute.')

        min_starters = getattr(conf, 'SQUAD_MIN_STARTERS', 7)
        if len(starters_int) < min_starters:
            errors.append(f'At least {min_starters} starters required. You selected {len(starters_int)}.')
        if len(starters_int) > conf.SQUAD_MAX_STARTERS:
            errors.append(f'Maximum {conf.SQUAD_MAX_STARTERS} starters allowed.')
        if len(subs_int) > conf.SQUAD_MAX_SUBS:
            errors.append(f'Maximum {conf.SQUAD_MAX_SUBS} substitutes allowed.')

        # Validate at least one GK in starters
        starter_players = Player.objects.filter(pk__in=starters_int, team=team)
        sub_players = Player.objects.filter(pk__in=subs_int, team=team)

        starter_gk_count = starter_players.filter(position='GK').count()
        if starter_gk_count < 1:
            errors.append('At least one goalkeeper (GK) must be in the starting lineup.')

        # Validate at least one GK in subs (if there are subs)
        if subs_int:
            sub_gk_count = sub_players.filter(position='GK').count()
            if sub_gk_count < 1:
                errors.append('Substitutes must include at least one goalkeeper (GK).')

        # Validate formation is provided
        if not formation:
            errors.append('Playing formation / units is required (e.g. 4-3-3, 4-4-2).')

        # Validate kit choice
        if kit_choice not in ('home', 'away', 'third'):
            errors.append('Please select a valid kit option.')

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            # Create or update
            if existing:
                existing.squad_players.all().delete()
                submission = existing
            else:
                submission = SquadSubmission.objects.create(fixture=fixture, team=team)

            submission.status = SquadStatus.SUBMITTED
            submission.submitted_at = timezone.now()
            submission.rejection_reason = ''
            submission.formation = formation
            submission.kit_choice = kit_choice
            submission.save()

            for p in starter_players:
                SquadPlayer.objects.create(submission=submission, player=p, is_starter=True, shirt_number=p.shirt_number)
            for p in sub_players:
                SquadPlayer.objects.create(submission=submission, player=p, is_starter=False, shirt_number=p.shirt_number)

            messages.success(request, f'✅ Squad submitted for {fixture.home_team} vs {fixture.away_team}.')
            return redirect('matches_list')

    # Kit info for display
    kit_options = []
    if team.home_kit_complete:
        kit_options.append(('home', 'Home Kit', team.home_outfield_colour))
    else:
        kit_options.append(('home', 'Home Kit', team.home_colour or 'Not set'))
    if team.away_kit_complete:
        kit_options.append(('away', 'Away Kit', team.away_outfield_colour))
    else:
        kit_options.append(('away', 'Away Kit', team.away_colour or 'Not set'))
    if team.third_outfield_colour:
        kit_options.append(('third', 'Third Kit', team.third_outfield_colour))

    return render(request, 'portal/squad_select.html', {
        'fixture': fixture,
        'team': team,
        'players': players,
        'existing': existing,
        'deadline': deadline,
        'deadline_passed': deadline_passed,
        'starter_ids': starter_ids,
        'sub_ids': sub_ids,
        'saved_formation': saved_formation,
        'saved_kit': saved_kit,
        'kit_options': kit_options,
        'settings': {
            'min_starters': getattr(conf, 'SQUAD_MIN_STARTERS', 7),
            'min_players': conf.SQUAD_MIN_PLAYERS,
            'max_players': conf.SQUAD_MAX_PLAYERS,
            'max_starters': conf.SQUAD_MAX_STARTERS,
            'max_subs': conf.SQUAD_MAX_SUBS,
        },
    })


# ══════════════════════════════════════════════════════════════════════════════
#   SQUAD APPROVAL (Referee / CR)
# ══════════════════════════════════════════════════════════════════════════════

@role_required('referee', 'admin', 'competition_manager', 'chief_sports_officer')
def squad_review_list_view(request):
    """List squads awaiting referee approval."""
    user = request.user
    if user.role == 'referee':
        try:
            profile = user.referee_profile
            # Show squads for fixtures the referee is the head official
            appointed_fixture_ids = RefereeAppointment.objects.filter(
                referee=profile, role__in=HEAD_OFFICIAL_ROLES
            ).values_list('fixture_id', flat=True)
            pending_squads = SquadSubmission.objects.filter(
                fixture_id__in=appointed_fixture_ids,
                status=SquadStatus.SUBMITTED,
            ).select_related('fixture__home_team', 'fixture__away_team', 'team')
        except RefereeProfile.DoesNotExist:
            pending_squads = SquadSubmission.objects.none()
    else:
        pending_squads = SquadSubmission.objects.filter(
            status=SquadStatus.SUBMITTED,
        ).select_related('fixture__home_team', 'fixture__away_team', 'team')

    all_squads = SquadSubmission.objects.exclude(
        status=SquadStatus.DRAFT
    ).select_related('fixture__home_team', 'fixture__away_team', 'team').order_by('-submitted_at')[:30]

    return render(request, 'portal/squad_review_list.html', {
        'pending_squads': pending_squads,
        'all_squads': all_squads,
    })


@role_required('referee', 'admin', 'competition_manager', 'chief_sports_officer')
def squad_review_view(request, squad_pk):
    """Referee reviews a submitted squad — approve or reject."""
    squad = get_object_or_404(SquadSubmission, pk=squad_pk)
    squad_players = squad.squad_players.select_related('player').order_by('-is_starter', 'shirt_number')
    starters = [sp for sp in squad_players if sp.is_starter]
    subs = [sp for sp in squad_players if not sp.is_starter]

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            squad.status = SquadStatus.APPROVED
            squad.reviewed_by = request.user
            squad.reviewed_at = timezone.now()
            squad.save()
            messages.success(request, f'✅ Squad approved: {squad.team.name} for {squad.fixture}')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            squad.status = SquadStatus.REJECTED
            squad.reviewed_by = request.user
            squad.reviewed_at = timezone.now()
            squad.rejection_reason = reason
            squad.save()
            messages.warning(request, f'❌ Squad rejected: {squad.team.name}')
        return redirect('squad_review_list')

    return render(request, 'portal/squad_review.html', {
        'squad': squad,
        'starters': starters,
        'subs': subs,
        'formation': squad.formation,
        'kit_choice': squad.get_kit_choice_display() if hasattr(squad, 'get_kit_choice_display') else squad.kit_choice,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   MATCH REPORT (Referee submits)
# ══════════════════════════════════════════════════════════════════════════════

@role_required('referee', 'admin')
def match_report_form_view(request, fixture_pk):
    """Referee creates / edits a match report for a fixture they officiated."""
    from matches.models import get_sport_config, get_event_types_for_sport, PeriodScore
    from referees.models import HEAD_OFFICIAL_ROLES

    fixture = get_object_or_404(Fixture, pk=fixture_pk)
    user = request.user
    sport_type = fixture.competition.sport_type
    sport_cfg = get_sport_config(sport_type)
    sport_event_types = get_event_types_for_sport(sport_type)

    # Only the head official (or admin) may submit the match report
    if user.role == 'referee':
        is_head = RefereeAppointment.objects.filter(
            fixture=fixture,
            referee=user.referee_profile,
            role__in=HEAD_OFFICIAL_ROLES,
        ).exclude(status='replaced').exists()
        if not is_head:
            messages.error(request, 'Only the head official (centre referee) appointed to this fixture may submit the match report.')
            return redirect('referee_portal')

    # Get or create report
    try:
        report = MatchReport.objects.get(fixture=fixture)
    except MatchReport.DoesNotExist:
        report = None

    # If report already approved, don't allow edits
    if report and report.status == MatchReportStatus.APPROVED:
        messages.info(request, 'This match report has already been approved.')
        return redirect('match_report_detail', report_pk=report.pk)

    # Get players from both teams for event recording
    home_players = Player.objects.filter(team=fixture.home_team).order_by('shirt_number')
    away_players = Player.objects.filter(team=fixture.away_team).order_by('shirt_number')

    if request.method == 'POST':
        # ── Parse main report fields ──
        home_score = int(request.POST.get('home_score', 0))
        away_score = int(request.POST.get('away_score', 0))
        home_yellow = int(request.POST.get('home_yellow_cards', 0))
        away_yellow = int(request.POST.get('away_yellow_cards', 0))
        home_red = int(request.POST.get('home_red_cards', 0))
        away_red = int(request.POST.get('away_red_cards', 0))
        match_duration = int(request.POST.get('match_duration', sport_cfg['default_duration'] or 90))
        added_time_ht = int(request.POST.get('added_time_ht', 0))
        added_time_ft = int(request.POST.get('added_time_ft', 0))
        pitch_condition = request.POST.get('pitch_condition', 'good')
        weather = request.POST.get('weather', '')
        attendance = request.POST.get('attendance', '') or None
        referee_notes = request.POST.get('referee_notes', '')
        is_abandoned = request.POST.get('is_abandoned') == 'on'
        abandonment_reason = request.POST.get('abandonment_reason', '')

        # Sport-specific fields
        home_sets = int(request.POST.get('home_sets', 0))
        away_sets = int(request.POST.get('away_sets', 0))
        home_suspensions = int(request.POST.get('home_suspensions', 0))
        away_suspensions = int(request.POST.get('away_suspensions', 0))
        overtime_played = request.POST.get('overtime_played') == 'on'
        overtime_periods = int(request.POST.get('overtime_periods', 0))

        if report:
            # Update
            report.home_score = home_score
            report.away_score = away_score
            report.home_yellow_cards = home_yellow
            report.away_yellow_cards = away_yellow
            report.home_red_cards = home_red
            report.away_red_cards = away_red
            report.match_duration = match_duration
            report.added_time_ht = added_time_ht
            report.added_time_ft = added_time_ft
            report.pitch_condition = pitch_condition
            report.weather = weather
            report.attendance = int(attendance) if attendance else None
            report.referee_notes = referee_notes
            report.is_abandoned = is_abandoned
            report.abandonment_reason = abandonment_reason
            report.home_sets = home_sets
            report.away_sets = away_sets
            report.home_suspensions = home_suspensions
            report.away_suspensions = away_suspensions
            report.overtime_played = overtime_played
            report.overtime_periods = overtime_periods
        else:
            # Determine referee profile
            ref_profile = None
            if hasattr(user, 'referee_profile'):
                ref_profile = user.referee_profile
            report = MatchReport(
                fixture=fixture,
                referee=ref_profile,
                home_score=home_score,
                away_score=away_score,
                home_yellow_cards=home_yellow,
                away_yellow_cards=away_yellow,
                home_red_cards=home_red,
                away_red_cards=away_red,
                match_duration=match_duration,
                added_time_ht=added_time_ht,
                added_time_ft=added_time_ft,
                pitch_condition=pitch_condition,
                weather=weather,
                attendance=int(attendance) if attendance else None,
                referee_notes=referee_notes,
                is_abandoned=is_abandoned,
                abandonment_reason=abandonment_reason,
                home_sets=home_sets,
                away_sets=away_sets,
                home_suspensions=home_suspensions,
                away_suspensions=away_suspensions,
                overtime_played=overtime_played,
                overtime_periods=overtime_periods,
            )

        action = request.POST.get('submit_action', 'draft')
        if action == 'submit':
            report.status = MatchReportStatus.SUBMITTED
            report.submitted_at = timezone.now()
        else:
            report.status = MatchReportStatus.DRAFT

        report.save()

        # ── Parse period scores ──
        report.period_scores.all().delete()
        period_count = int(request.POST.get('period_count', 0))
        for i in range(1, period_count + 1):
            ph = request.POST.get(f'period_{i}_home', '')
            pa = request.POST.get(f'period_{i}_away', '')
            pl = request.POST.get(f'period_{i}_label', f'Period {i}')
            is_ot = request.POST.get(f'period_{i}_overtime') == 'on'
            if ph != '' and pa != '':
                PeriodScore.objects.create(
                    report=report,
                    period_number=i,
                    period_label=pl,
                    home_score=int(ph),
                    away_score=int(pa),
                    is_overtime=is_ot,
                )

        # ── Parse events ──
        report.events.all().delete()  # Replace all events
        event_count = int(request.POST.get('event_count', 0))
        for i in range(event_count):
            evt_type = request.POST.get(f'event_{i}_type', '')
            evt_team = request.POST.get(f'event_{i}_team', '')
            evt_player = request.POST.get(f'event_{i}_player', '')
            evt_minute = request.POST.get(f'event_{i}_minute', '')
            evt_notes = request.POST.get(f'event_{i}_notes', '')
            if evt_type and evt_minute:
                MatchEvent.objects.create(
                    report=report,
                    team_id=int(evt_team) if evt_team else fixture.home_team_id,
                    player_id=int(evt_player) if evt_player else None,
                    event_type=evt_type,
                    minute=int(evt_minute),
                    notes=evt_notes,
                )

        if action == 'submit':
            messages.success(request, '✅ Match report submitted for review.')
        else:
            messages.info(request, '📝 Match report saved as draft.')
        return redirect('matches_list')

    # Get existing events
    events = report.events.all().order_by('minute') if report else []

    # ── Auto-populate from approved squads (FKF pattern) ──
    home_squad = SquadSubmission.objects.filter(
        fixture=fixture, team=fixture.home_team, status=SquadStatus.APPROVED
    ).first()
    away_squad = SquadSubmission.objects.filter(
        fixture=fixture, team=fixture.away_team, status=SquadStatus.APPROVED
    ).first()
    home_starters = home_squad.squad_players.filter(is_starter=True).select_related('player').order_by('shirt_number') if home_squad else []
    home_subs = home_squad.squad_players.filter(is_starter=False).select_related('player').order_by('shirt_number') if home_squad else []
    away_starters = away_squad.squad_players.filter(is_starter=True).select_related('player').order_by('shirt_number') if away_squad else []
    away_subs = away_squad.squad_players.filter(is_starter=False).select_related('player').order_by('shirt_number') if away_squad else []

    # Other officials appointed to this match
    match_officials = RefereeAppointment.objects.filter(
        fixture=fixture
    ).select_related('referee__user').order_by('role')

    # Existing period scores
    period_scores = report.period_scores.all().order_by('period_number') if report else []

    # Build period scaffolding for the form
    periods_for_form = []
    existing_ps = {ps.period_number: ps for ps in period_scores}
    for i, label in enumerate(sport_cfg['period_labels'], start=1):
        ps = existing_ps.get(i)
        periods_for_form.append({
            'number': i,
            'label': label,
            'home_score': ps.home_score if ps else '',
            'away_score': ps.away_score if ps else '',
            'is_overtime': False,
        })
    # Add overtime periods if they exist
    for ps in period_scores:
        if ps.is_overtime:
            periods_for_form.append({
                'number': ps.period_number,
                'label': ps.period_label,
                'home_score': ps.home_score,
                'away_score': ps.away_score,
                'is_overtime': True,
            })

    return render(request, 'portal/match_report_form.html', {
        'fixture': fixture,
        'report': report,
        'events': events,
        'home_players': home_players,
        'away_players': away_players,
        'pitch_choices': [('excellent', 'Excellent'), ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor')],
        'event_types': sport_event_types,
        'sport_cfg': sport_cfg,
        'sport_family': sport_cfg['label'],
        'periods_for_form': periods_for_form,
        'period_count': len(periods_for_form),
        # Squad data
        'home_squad': home_squad,
        'away_squad': away_squad,
        'home_starters': home_starters,
        'home_subs': home_subs,
        'away_starters': away_starters,
        'away_subs': away_subs,
        'match_officials': match_officials,
    })


@login_required(login_url='web_login')
def match_report_detail_view(request, report_pk):
    """View a match report (read-only)."""
    report = get_object_or_404(MatchReport, pk=report_pk)
    events = report.events.select_related('team', 'player').order_by('minute')
    sport_cfg = get_sport_config(report.fixture.competition.sport_type)
    period_scores = report.period_scores.order_by('period_number')
    return render(request, 'portal/match_report_detail.html', {
        'report': report,
        'events': events,
        'sport_cfg': sport_cfg,
        'period_scores': period_scores,
    })


@role_required('coordinator', 'admin')
def match_report_review_view(request, report_pk):
    """Referee Manager approves or returns a match report."""
    report = get_object_or_404(MatchReport, pk=report_pk)
    events = report.events.select_related('team', 'player').order_by('minute')

    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('reviewer_notes', '')

        if action == 'approve':
            report.status = MatchReportStatus.APPROVED
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.reviewer_notes = notes

            # Update fixture with final score
            fixture = report.fixture
            fixture.home_score = report.home_score
            fixture.away_score = report.away_score
            fixture.status = 'completed'
            fixture.save(update_fields=['home_score', 'away_score', 'status'])

            # Auto-update pool standings + player statistics
            from matches.stats_engine import process_approved_report
            process_approved_report(report)

            report.save()
            messages.success(request, f'✅ Match report approved — {fixture.home_team} {report.home_score}-{report.away_score} {fixture.away_team}')

        elif action == 'return':
            report.status = MatchReportStatus.RETURNED
            report.reviewer_notes = notes
            report.save()
            messages.warning(request, f'🔄 Match report returned for revision.')

        return redirect('coordinator_match_reports')

    sport_cfg = get_sport_config(report.fixture.competition.sport_type)
    period_scores = report.period_scores.order_by('period_number')
    return render(request, 'portal/match_report_review.html', {
        'report': report,
        'events': events,
        'sport_cfg': sport_cfg,
        'period_scores': period_scores,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   REFEREE APPOINTMENT CONFIRM / DECLINE
# ══════════════════════════════════════════════════════════════════════════════

@role_required('referee')
def appointment_action_view(request, appointment_pk):
    """Referee confirms or declines a match appointment."""
    user = request.user
    try:
        appointment = RefereeAppointment.objects.select_related(
            'fixture__home_team', 'fixture__away_team', 'fixture__venue', 'fixture__competition'
        ).get(pk=appointment_pk, referee=user.referee_profile)
    except (RefereeAppointment.DoesNotExist, RefereeProfile.DoesNotExist):
        messages.error(request, 'Appointment not found.')
        return redirect('referees_list')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm':
            appointment.status = 'confirmed'
            appointment.confirmed_at = timezone.now()
            appointment.save()
            messages.success(request, f'✅ Appointment confirmed: {appointment.fixture}')
        elif action == 'decline':
            appointment.status = 'declined'
            appointment.notes = request.POST.get('notes', '')
            appointment.save()
            messages.warning(request, f'❌ Appointment declined: {appointment.fixture}')
        return redirect('referees_list')

    return render(request, 'portal/appointment_action.html', {
        'appointment': appointment,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   REFEREE DASHBOARD  (Comprehensive — borrowed from FKF)
# ══════════════════════════════════════════════════════════════════════════════

@role_required('referee')
def referee_dashboard_view(request):
    """
    Full referee portal dashboard showing:
    – pending confirmations, upcoming / current / completed matches
    – pending match reports, squad approvals, availability summary
    """
    user = request.user
    try:
        profile = user.referee_profile
    except RefereeProfile.DoesNotExist:
        # Render an empty-state dashboard instead of redirecting (avoids loop)
        return render(request, 'portal/referee_dashboard.html', {
            'profile': None,
            'no_profile': True,
            'pending_confirmation': [],
            'upcoming_matches': [],
            'current_matches': [],
            'completed_matches': [],
            'pending_reports': [],
            'draft_reports': [],
            'returned_reports': [],
            'pending_squads': [],
            'availability_calendar': [],
            'total_appointments': 0,
        })

    today = date.today()

    appointments = RefereeAppointment.objects.filter(
        referee=profile
    ).select_related(
        'fixture__home_team', 'fixture__away_team',
        'fixture__venue', 'fixture__competition',
    ).order_by('fixture__match_date')

    pending_confirmation = []
    upcoming_matches = []
    completed_matches = []
    current_matches = []

    for appt in appointments:
        match_date = appt.fixture.match_date
        info = {
            'appointment': appt,
            'fixture': appt.fixture,
            'role': appt.get_role_display(),
            'status': appt.status,
            'match_date': match_date,
        }
        if match_date == today:
            current_matches.append(info)
            if appt.status == AppointmentStatus.PENDING:
                pending_confirmation.append(info)
        elif match_date > today:
            if appt.status == AppointmentStatus.PENDING:
                pending_confirmation.append(info)
            upcoming_matches.append(info)
        else:
            completed_matches.append(info)

    # Pending match reports  (fixtures where this official is the head official)
    referee_fixture_ids = RefereeAppointment.objects.filter(
        referee=profile, role__in=HEAD_OFFICIAL_ROLES,
    ).values_list('fixture_id', flat=True)

    pending_reports = Fixture.objects.filter(
        pk__in=referee_fixture_ids,
        match_date__lt=today,
        status='completed',
    ).exclude(
        match_report__status__in=[MatchReportStatus.SUBMITTED, MatchReportStatus.APPROVED]
    ).select_related('home_team', 'away_team')

    draft_reports = MatchReport.objects.filter(
        referee=profile, status=MatchReportStatus.DRAFT,
    ).select_related('fixture__home_team', 'fixture__away_team')

    returned_reports = MatchReport.objects.filter(
        referee=profile, status=MatchReportStatus.RETURNED,
    ).select_related('fixture__home_team', 'fixture__away_team')

    # Squads awaiting approval (match referee only)
    pending_squads = SquadSubmission.objects.filter(
        fixture_id__in=referee_fixture_ids,
        status=SquadStatus.SUBMITTED,
    ).select_related('fixture__home_team', 'fixture__away_team', 'team')

    return render(request, 'portal/referee_dashboard.html', {
        'profile': profile,
        'pending_confirmation': pending_confirmation,
        'upcoming_matches': upcoming_matches,
        'current_matches': current_matches,
        'completed_matches': completed_matches[:10],
        'pending_reports': pending_reports,
        'draft_reports': draft_reports,
        'returned_reports': returned_reports,
        'pending_squads': pending_squads,
        'total_appointments': appointments.count(),
    })


# ══════════════════════════════════════════════════════════════════════════════
#   REFEREE PROFILE EDIT
# ══════════════════════════════════════════════════════════════════════════════

@role_required('referee')
def referee_edit_profile_view(request):
    """Referee edits own profile — including referee_type (Referee / Assistant Referee)."""
    user = request.user
    try:
        profile = user.referee_profile
    except RefereeProfile.DoesNotExist:
        messages.error(request, 'No referee profile found.')
        return redirect('dashboard')

    if request.method == 'POST':
        # Basic profile fields
        profile.referee_type = request.POST.get('referee_type', profile.referee_type)
        profile.level = request.POST.get('level', profile.level)
        profile.county = request.POST.get('county', profile.county)
        profile.bio = request.POST.get('bio', profile.bio)
        years_exp = request.POST.get('years_experience', '')
        if years_exp.isdigit():
            profile.years_experience = int(years_exp)

        # Profile picture
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']

        profile.save()

        # Update user name / phone
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        new_phone = request.POST.get('phone', user.phone).strip()
        # Normalize phone so users can enter 7XXXXXXXX or 07XXXXXXXX.
        if new_phone.startswith('0') and len(new_phone) == 10:
            new_phone = f'+254{new_phone[1:]}'
        elif new_phone.startswith('7') and len(new_phone) == 9:
            new_phone = f'+254{new_phone}'
        elif new_phone.startswith('254') and len(new_phone) == 12:
            new_phone = f'+{new_phone}'

        # Validate normalized phone format.
        import re
        if new_phone and not re.match(r'^\+254\d{9}$', new_phone):
            messages.error(request, 'Phone number must be valid. Use 7XXXXXXXX, 07XXXXXXXX or +254XXXXXXXXX.')
            return redirect('referee_edit_profile')
        user.phone = new_phone
        user.save(update_fields=['first_name', 'last_name', 'phone'])

        messages.success(request, 'Profile updated successfully.')
        return redirect('referee_edit_profile')

    from referees.models import RefereeLevel, RefereeType as RT
    from accounts.models import KenyaCounty as KC

    return render(request, 'portal/referee_edit_profile.html', {
        'profile': profile,
        'referee_types': RT.choices,
        'levels': RefereeLevel.choices,
        'counties': KC.choices,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   DISCIPLINE COORDINATOR PORTAL
# ══════════════════════════════════════════════════════════════════════════════

def _coordinator_discipline(user):
    """Return the coordinator's assigned discipline or None."""
    return _normalize_coordinator_discipline(getattr(user, 'assigned_discipline', ''))


def _auto_generate_pool_fixtures(pool, competition, user):
    """
    Auto-generate round-robin fixtures for a pool when it has >=2 teams.
    Re-generates fixtures for the pool (clearing old ones first) so
    every new team addition produces a complete round-robin.
    Returns list of created fixtures (empty if <2 teams).
    """
    from competitions.models import Fixture, PoolTeam
    from itertools import combinations
    from datetime import datetime, timedelta

    teams = [pt.team for pt in pool.pool_teams.all()]
    if len(teams) < 2:
        return []

    # Clear existing pool fixtures and regenerate
    Fixture.objects.filter(competition=competition, pool=pool, is_knockout=False).delete()

    start_date = competition.start_date or timezone.now().date()
    kickoff_time = datetime.strptime('14:00', '%H:%M').time()
    current_date = start_date
    round_number = 1
    created = []

    matchups = list(combinations(teams, 2))
    for home, away in matchups:
        fixture = Fixture.objects.create(
            competition=competition,
            pool=pool,
            home_team=home,
            away_team=away,
            match_date=current_date,
            kickoff_time=kickoff_time,
            status='pending',
            round_number=round_number,
            is_knockout=False,
            created_by=user,
        )
        created.append(fixture)
        round_number += 1
        if round_number % 3 == 0:
            current_date += timedelta(days=7)

    return created


@role_required('coordinator', 'admin')
def coordinator_dashboard_view(request):
    """Discipline Coordinator dashboard — overview scoped to assigned discipline."""
    from competitions.models import (
        Competition, Fixture, Venue, Pool, PoolTeam,
        SportType, CompetitionStatus, CountyPayment,
    )
    from matches.models import MatchReport

    discipline = _coordinator_discipline(request.user)
    discipline_label = _coordinator_label(discipline)
    coordinator_name = request.user.get_full_name() or request.user.email
    discipline_variants = _coordinator_variants(discipline)

    if not discipline:
        messages.warning(request, 'Your account has no discipline assigned. Contact an administrator.')

    # Competitions for this discipline
    competitions = Competition.objects.filter(sport_type__in=discipline_variants) if discipline_variants else Competition.objects.none()
    active = competitions.filter(status__in=['active', 'group_stage', 'knockout'])
    registration = competitions.filter(status='registration')

    comp_ids = competitions.values_list('pk', flat=True)

    # Key counts
    stats = {
        'total_competitions': competitions.count(),
        'active_competitions': active.count(),
        'total_fixtures': Fixture.objects.filter(competition__in=comp_ids).count(),
        'completed_fixtures': Fixture.objects.filter(competition__in=comp_ids, status='completed').count(),
        'upcoming_fixtures': Fixture.objects.filter(
            competition__in=comp_ids, match_date__gte=date.today()
        ).exclude(status__in=['completed', 'cancelled']).count(),
        'pending_reports': MatchReport.objects.filter(
            fixture__competition__in=comp_ids, status='submitted'
        ).count(),
        'pending_referees': RefereeProfile.objects.filter(is_approved=False).count(),
        'total_venues': Venue.objects.filter(is_active=True).count(),
        'total_teams': Team.objects.filter(
            status='registered', sport_type__in=discipline_variants
        ).count() if discipline_variants else 0,
    }

    # Recent fixture results
    recent_results = Fixture.objects.filter(
        competition__in=comp_ids, status='completed'
    ).select_related(
        'competition', 'home_team', 'away_team'
    ).order_by('-updated_at')[:8]

    # Pending reports needing approval
    pending_reports = MatchReport.objects.filter(
        fixture__competition__in=comp_ids, status='submitted'
    ).select_related(
        'fixture__competition', 'fixture__home_team', 'fixture__away_team',
        'referee__user'
    ).order_by('-submitted_at')[:5]

    return render(request, 'portal/coordinator/dashboard.html', {
        'stats': stats,
        'discipline': discipline,
        'discipline_label': discipline_label,
        'coordinator_name': coordinator_name,
        'active_competitions': active,
        'registration_competitions': registration,
        'recent_results': recent_results,
        'pending_reports': pending_reports,
    })


@role_required('coordinator', 'admin')
def coordinator_competitions_view(request):
    """List all competitions for the coordinator's discipline."""
    from competitions.models import Competition, SportType, CompetitionStatus

    discipline = _coordinator_discipline(request.user)
    competitions = Competition.objects.filter(
        sport_type__in=_coordinator_variants(discipline)
    ).order_by('-start_date') if discipline else Competition.objects.none()

    status_filter = request.GET.get('status', '')
    if status_filter:
        competitions = competitions.filter(status=status_filter)

    return render(request, 'portal/coordinator/competitions.html', {
        'competitions': competitions,
        'discipline_label': _coordinator_label(discipline),
        'status_choices': CompetitionStatus.choices,
        'current_status': status_filter,
    })


@role_required('coordinator', 'admin')
def coordinator_competition_manage_view(request, pk):
    """Central hub for a coordinator to manage a single competition in their discipline."""
    from competitions.models import (
        Competition, Pool, PoolTeam, Fixture, Venue, KnockoutRound,
    )
    from matches.models import MatchReport

    competition = get_object_or_404(Competition, pk=pk)

    # Verify discipline ownership
    discipline = _coordinator_discipline(request.user)
    if discipline and competition.sport_type not in _coordinator_variants(discipline) and not request.user.is_superuser:
        messages.error(request, 'This competition is not in your discipline.')
        return redirect('coordinator_dashboard')

    # Pools & teams
    pools = Pool.objects.filter(competition=competition).prefetch_related(
        'pool_teams__team'
    ).order_by('name')

    pool_data = []
    for pool in pools:
        teams = pool.pool_teams.select_related('team').all()
        sorted_teams = sorted(
            teams,
            key=lambda pt: (pt.points, pt.goal_difference, pt.goals_for),
            reverse=True,
        )
        pool_data.append({'pool': pool, 'teams': sorted_teams})

    # Eligible teams
    eligible_teams = Team.objects.filter(
        status='registered', sport_type=competition.sport_type,
    ).exclude(
        pk__in=PoolTeam.objects.filter(pool__competition=competition).values_list('team_id', flat=True)
    ).order_by('county', 'name')

    teams_in_comp = Team.objects.filter(pool_memberships__pool__competition=competition).distinct()

    # Fixtures
    group_fixtures = Fixture.objects.filter(
        competition=competition, is_knockout=False
    ).select_related('home_team', 'away_team', 'venue', 'pool').order_by('match_date', 'kickoff_time')

    knockout_fixtures = Fixture.objects.filter(
        competition=competition, is_knockout=True
    ).select_related('home_team', 'away_team', 'venue', 'winner').order_by('knockout_round', 'bracket_position')

    venues = Venue.objects.filter(is_active=True).order_by('county', 'name')

    pending_reports = MatchReport.objects.filter(
        fixture__competition=competition, status='submitted'
    ).count()
    approved_reports = MatchReport.objects.filter(
        fixture__competition=competition, status='approved'
    ).count()

    return render(request, 'portal/coordinator/manage_competition.html', {
        'competition': competition,
        'pool_data': pool_data,
        'eligible_teams': eligible_teams,
        'teams_in_comp': teams_in_comp,
        'group_fixtures': group_fixtures,
        'knockout_fixtures': knockout_fixtures,
        'venues': venues,
        'pending_reports': pending_reports,
        'approved_reports': approved_reports,
    })


@role_required('coordinator', 'admin')
def coordinator_manage_pools_view(request, pk):
    """Coordinator: Create/delete pools and assign/remove teams for their discipline competition."""
    from competitions.models import Competition, Pool, PoolTeam

    competition = get_object_or_404(Competition, pk=pk)
    discipline = _coordinator_discipline(request.user)
    if discipline and competition.sport_type not in _coordinator_variants(discipline) and not request.user.is_superuser:
        messages.error(request, 'This competition is not in your discipline.')
        return redirect('coordinator_dashboard')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create_pool':
            pool_name = request.POST.get('pool_name', '').strip()
            if not pool_name:
                messages.error(request, 'Pool name is required.')
            elif Pool.objects.filter(competition=competition, name=pool_name).exists():
                messages.error(request, f'Pool "{pool_name}" already exists.')
            else:
                Pool.objects.create(competition=competition, name=pool_name)
                messages.success(request, f'Pool "{pool_name}" created.')

        elif action == 'delete_pool':
            pool_id = request.POST.get('pool_id')
            try:
                pool = Pool.objects.get(pk=pool_id, competition=competition)
                name = pool.name
                pool.delete()
                messages.success(request, f'Pool "{name}" deleted.')
            except Pool.DoesNotExist:
                messages.error(request, 'Pool not found.')

        elif action == 'add_team':
            pool_id = request.POST.get('pool_id')
            team_id = request.POST.get('team_id')
            try:
                pool = Pool.objects.get(pk=pool_id, competition=competition)
                team = Team.objects.get(pk=team_id)
                if team.status != 'registered':
                    messages.error(request, f'{team.name} is not approved.')
                elif PoolTeam.objects.filter(pool__competition=competition, team=team).exists():
                    messages.error(request, f'{team.name} is already in a pool.')
                else:
                    PoolTeam.objects.create(pool=pool, team=team)
                    messages.success(request, f'{team.name} added to {pool.name}.')
                    # Auto-generate fixtures if pool now has >=2 teams
                    auto_fixtures = _auto_generate_pool_fixtures(pool, competition, request.user)
                    if auto_fixtures:
                        messages.info(request, f'{len(auto_fixtures)} fixtures auto-generated for {pool.name}. You can modify dates/times from the fixtures page.')
            except (Pool.DoesNotExist, Team.DoesNotExist):
                messages.error(request, 'Pool or team not found.')

        elif action == 'remove_team':
            pt_id = request.POST.get('pool_team_id')
            try:
                pt = PoolTeam.objects.get(pk=pt_id, pool__competition=competition)
                name = pt.team.name
                pool_name = pt.pool.name
                pt.delete()
                messages.success(request, f'{name} removed from {pool_name}.')
            except PoolTeam.DoesNotExist:
                messages.error(request, 'Team assignment not found.')

        return redirect('coordinator_manage_pools', pk=competition.pk)

    pools = Pool.objects.filter(competition=competition).prefetch_related('pool_teams__team').order_by('name')
    assigned_ids = PoolTeam.objects.filter(pool__competition=competition).values_list('team_id', flat=True)
    eligible_teams = Team.objects.filter(
        status='registered', sport_type=competition.sport_type,
    ).exclude(pk__in=assigned_ids).order_by('county', 'name')

    return render(request, 'portal/coordinator/manage_pools.html', {
        'competition': competition,
        'pools': pools,
        'eligible_teams': eligible_teams,
    })


@role_required('coordinator', 'admin')
def coordinator_generate_fixtures_view(request, pk):
    """Coordinator: Generate fixtures for a competition in their discipline."""
    from competitions.models import Competition, Fixture, Venue, Pool
    from competitions.fixture_engine import generate_all_fixtures

    competition = get_object_or_404(Competition, pk=pk)
    discipline = _coordinator_discipline(request.user)
    if discipline and competition.sport_type not in _coordinator_variants(discipline) and not request.user.is_superuser:
        messages.error(request, 'This competition is not in your discipline.')
        return redirect('coordinator_dashboard')

    existing_count = Fixture.objects.filter(competition=competition).count()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'generate':
            start_date_str = request.POST.get('start_date', '')
            kickoff_time_str = request.POST.get('kickoff_time', '14:00')
            group_interval = int(request.POST.get('group_interval', 7))
            knockout_interval = int(request.POST.get('knockout_interval', 3))
            venue_id = request.POST.get('venue_id', '')
            knockout_teams = request.POST.get('knockout_teams', '')

            from datetime import datetime
            try:
                start_date_val = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                messages.error(request, 'Invalid start date.')
                return redirect('coordinator_generate_fixtures', pk=pk)

            try:
                kickoff_time = datetime.strptime(kickoff_time_str, '%H:%M').time()
            except (ValueError, TypeError):
                kickoff_time = datetime.strptime('14:00', '%H:%M').time()

            venue = None
            if venue_id:
                try:
                    venue = Venue.objects.get(pk=venue_id)
                except Venue.DoesNotExist:
                    pass

            ko_teams = int(knockout_teams) if knockout_teams else None

            try:
                fixtures = generate_all_fixtures(
                    competition, start_date_val, kickoff_time,
                    group_interval=group_interval,
                    knockout_interval=knockout_interval,
                    knockout_teams=ko_teams,
                    venue=venue,
                    created_by=request.user,
                )
                from admin_dashboard.models import ActivityLog
                ActivityLog.objects.create(
                    user=request.user,
                    action='FIXTURES_GENERATED',
                    description=(
                        f'{request.user.get_full_name()} generated {len(fixtures)} '
                        f'fixtures for {competition.name}'
                    ),
                    object_repr=str(competition),
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                )
                messages.success(request, f'{len(fixtures)} fixtures generated for {competition.name}.')
            except ValueError as e:
                messages.error(request, str(e))

            return redirect('coordinator_competition_manage', pk=pk)

        elif action == 'clear':
            count = Fixture.objects.filter(competition=competition).count()
            Fixture.objects.filter(competition=competition).delete()
            messages.warning(request, f'{count} fixtures deleted.')
            return redirect('coordinator_generate_fixtures', pk=pk)

    venues = Venue.objects.filter(is_active=True).order_by('county', 'name')
    pools = Pool.objects.filter(competition=competition).prefetch_related('pool_teams')
    total_pool_teams = sum(p.pool_teams.count() for p in pools)

    return render(request, 'portal/coordinator/generate_fixtures.html', {
        'competition': competition,
        'existing_count': existing_count,
        'venues': venues,
        'pools': pools,
        'total_pool_teams': total_pool_teams,
    })


@role_required('coordinator', 'admin')
def coordinator_venues_view(request):
    """Coordinator: View and manage venues (shared across disciplines)."""
    from competitions.models import Venue

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            county = request.POST.get('county', '').strip()
            city = request.POST.get('city', '').strip()
            capacity = request.POST.get('capacity', 0)
            surface = request.POST.get('surface', 'Natural Grass')
            address = request.POST.get('address', '')
            facilities = request.POST.get('facilities', '')
            if not name or not county:
                messages.error(request, 'Venue name and county are required.')
            else:
                Venue.objects.create(
                    name=name, county=county, city=city,
                    capacity=int(capacity) if capacity else 0,
                    surface=surface, address=address, facilities=facilities,
                )
                messages.success(request, f'Venue "{name}" created.')

        elif action == 'toggle':
            venue_id = request.POST.get('venue_id')
            try:
                venue = Venue.objects.get(pk=venue_id)
                venue.is_active = not venue.is_active
                venue.save(update_fields=['is_active'])
                status_txt = 'activated' if venue.is_active else 'deactivated'
                messages.success(request, f'Venue "{venue.name}" {status_txt}.')
            except Venue.DoesNotExist:
                messages.error(request, 'Venue not found.')

        elif action == 'update':
            venue_id = request.POST.get('venue_id')
            try:
                venue = Venue.objects.get(pk=venue_id)
                venue.name = request.POST.get('name', venue.name).strip()
                venue.county = request.POST.get('county', venue.county).strip()
                venue.city = request.POST.get('city', venue.city).strip()
                venue.capacity = int(request.POST.get('capacity', venue.capacity) or 0)
                venue.surface = request.POST.get('surface', venue.surface)
                venue.address = request.POST.get('address', venue.address)
                venue.facilities = request.POST.get('facilities', venue.facilities)
                venue.save()
                messages.success(request, f'Venue "{venue.name}" updated.')
            except Venue.DoesNotExist:
                messages.error(request, 'Venue not found.')

        return redirect('coordinator_venues')

    venues = Venue.objects.all().order_by('county', 'name')
    return render(request, 'portal/coordinator/venues.html', {
        'active_venues': venues.filter(is_active=True),
        'inactive_venues': venues.filter(is_active=False),
        'total_venues': venues.count(),
        'county_choices': KenyaCounty.choices,
    })


@role_required('coordinator', 'admin')
def coordinator_allocate_venue_view(request, pk):
    """Coordinator: Allocate venues to fixtures."""
    from competitions.models import Competition, Fixture, Venue

    competition = get_object_or_404(Competition, pk=pk)
    discipline = _coordinator_discipline(request.user)
    if discipline and competition.sport_type not in _coordinator_variants(discipline) and not request.user.is_superuser:
        messages.error(request, 'This competition is not in your discipline.')
        return redirect('coordinator_dashboard')

    if request.method == 'POST':
        fixtures = Fixture.objects.filter(competition=competition)
        updated = 0
        for fixture in fixtures:
            venue_id = request.POST.get(f'venue_{fixture.pk}', '')
            if venue_id:
                try:
                    venue = Venue.objects.get(pk=venue_id)
                    if fixture.venue != venue:
                        fixture.venue = venue
                        fixture.save(update_fields=['venue'])
                        updated += 1
                except Venue.DoesNotExist:
                    pass
            elif fixture.venue:
                fixture.venue = None
                fixture.save(update_fields=['venue'])
                updated += 1
        messages.success(request, f'{updated} fixture venue(s) updated.')
        return redirect('coordinator_competition_manage', pk=pk)

    fixtures = Fixture.objects.filter(competition=competition).select_related(
        'home_team', 'away_team', 'venue', 'pool'
    ).order_by('match_date', 'kickoff_time')
    venues = Venue.objects.filter(is_active=True).order_by('county', 'name')

    return render(request, 'portal/coordinator/allocate_venues.html', {
        'competition': competition,
        'fixtures': fixtures,
        'venues': venues,
    })


@role_required('coordinator', 'admin')
def coordinator_edit_fixture_view(request, pk, fixture_pk):
    """Coordinator: Edit a specific fixture."""
    from competitions.models import Competition, Fixture, Venue, FixtureStatus

    competition = get_object_or_404(Competition, pk=pk)
    discipline = _coordinator_discipline(request.user)
    if discipline and competition.sport_type not in _coordinator_variants(discipline) and not request.user.is_superuser:
        messages.error(request, 'This competition is not in your discipline.')
        return redirect('coordinator_dashboard')

    fixture = get_object_or_404(Fixture, pk=fixture_pk, competition=competition)

    if request.method == 'POST':
        original_status = fixture.status
        original_home_score = fixture.home_score
        original_away_score = fixture.away_score

        fixture.match_date = request.POST.get('match_date', fixture.match_date)
        kickoff = request.POST.get('kickoff_time', '')
        if kickoff:
            from datetime import datetime
            try:
                fixture.kickoff_time = datetime.strptime(kickoff, '%H:%M').time()
            except ValueError:
                pass

        venue_id = request.POST.get('venue_id', '')
        if venue_id:
            try:
                fixture.venue = Venue.objects.get(pk=venue_id)
            except Venue.DoesNotExist:
                pass
        else:
            fixture.venue = None

        status = request.POST.get('status', fixture.status)
        if status:
            fixture.status = status

        # For knockout: allow team reassignment
        if fixture.is_knockout:
            home_id = request.POST.get('home_team_id', '')
            away_id = request.POST.get('away_team_id', '')
            if home_id:
                try:
                    fixture.home_team = Team.objects.get(pk=home_id)
                except Team.DoesNotExist:
                    pass
            if away_id:
                try:
                    fixture.away_team = Team.objects.get(pk=away_id)
                except Team.DoesNotExist:
                    pass

        # Score update
        home_score = request.POST.get('home_score', '')
        away_score = request.POST.get('away_score', '')
        if home_score != '':
            fixture.home_score = int(home_score)
        if away_score != '':
            fixture.away_score = int(away_score)

        score_changed = (
            fixture.home_score != original_home_score or
            fixture.away_score != original_away_score
        )
        status_changed = fixture.status != original_status
        if score_changed or status_changed:
            exceptional_reason = request.POST.get('exceptional_reason', '').strip()
            confirm_exceptional = request.POST.get('confirm_exceptional') == '1'
            if not confirm_exceptional:
                messages.error(request, 'Result edits are only allowed for exceptional cases. Tick the exceptional-case confirmation box.')
                return redirect('coordinator_edit_fixture', pk=pk, fixture_pk=fixture_pk)
            if len(exceptional_reason) < 12:
                messages.error(request, 'Provide a clear exceptional-case reason (at least 12 characters) before editing results.')
                return redirect('coordinator_edit_fixture', pk=pk, fixture_pk=fixture_pk)

        fixture.save()
        if score_changed or status_changed:
            from admin_dashboard.models import ActivityLog
            ActivityLog.objects.create(
                user=request.user,
                action='RESULT_OVERRIDE',
                description=(
                    f'{request.user.get_full_name()} made exceptional result/status changes '
                    f'for fixture {fixture} and submitted this override to SG tracking. '
                    f'Reason: {exceptional_reason}'
                ),
                object_repr=str(fixture),
                ip_address=request.META.get('REMOTE_ADDR', ''),
                extra_data={
                    'submitted_to_sg': True,
                    'exceptional_case': True,
                    'reason': exceptional_reason,
                    'status_before': original_status,
                    'status_after': fixture.status,
                    'home_score_before': original_home_score,
                    'away_score_before': original_away_score,
                    'home_score_after': fixture.home_score,
                    'away_score_after': fixture.away_score,
                },
            )
        messages.success(request, f'Fixture updated: {fixture}')
        return redirect('coordinator_competition_manage', pk=pk)

    venues = Venue.objects.filter(is_active=True).order_by('county', 'name')
    teams = Team.objects.filter(status='registered').order_by('name')

    return render(request, 'portal/coordinator/edit_fixture.html', {
        'competition': competition,
        'fixture': fixture,
        'venues': venues,
        'teams': teams,
        'status_choices': FixtureStatus.choices,
    })


@role_required('coordinator', 'admin')
def coordinator_edit_standings_view(request, pk):
    """Coordinator: Edit pool standings for a competition."""
    from competitions.models import Competition, Pool, PoolTeam

    competition = get_object_or_404(Competition, pk=pk)
    discipline = _coordinator_discipline(request.user)
    if discipline and competition.sport_type not in _coordinator_variants(discipline) and not request.user.is_superuser:
        messages.error(request, 'This competition is not in your discipline.')
        return redirect('coordinator_dashboard')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_standings':
            pool_team_id = request.POST.get('pool_team_id')
            exceptional_reason = request.POST.get('exceptional_reason', '').strip()
            confirm_exceptional = request.POST.get('confirm_exceptional') == '1'
            if not confirm_exceptional:
                messages.error(request, 'Standings overrides are allowed only for exceptional cases. Tick confirmation to proceed.')
                return redirect('coordinator_edit_standings', pk=pk)
            if len(exceptional_reason) < 12:
                messages.error(request, 'Provide a clear exceptional-case reason (at least 12 characters) before overriding standings.')
                return redirect('coordinator_edit_standings', pk=pk)
            try:
                pt = PoolTeam.objects.get(pk=pool_team_id, pool__competition=competition)
                before_state = {
                    'played': pt.played,
                    'won': pt.won,
                    'drawn': pt.drawn,
                    'lost': pt.lost,
                    'goals_for': pt.goals_for,
                    'goals_against': pt.goals_against,
                    'bonus_points': pt.bonus_points,
                }
                pt.played = int(request.POST.get('played', pt.played))
                pt.won = int(request.POST.get('won', pt.won))
                pt.drawn = int(request.POST.get('drawn', pt.drawn))
                pt.lost = int(request.POST.get('lost', pt.lost))
                pt.goals_for = int(request.POST.get('goals_for', pt.goals_for))
                pt.goals_against = int(request.POST.get('goals_against', pt.goals_against))
                pt.bonus_points = int(request.POST.get('bonus_points', pt.bonus_points))
                pt.save()
                after_state = {
                    'played': pt.played,
                    'won': pt.won,
                    'drawn': pt.drawn,
                    'lost': pt.lost,
                    'goals_for': pt.goals_for,
                    'goals_against': pt.goals_against,
                    'bonus_points': pt.bonus_points,
                }
                from admin_dashboard.models import ActivityLog
                ActivityLog.objects.create(
                    user=request.user,
                    action='STANDINGS_OVERRIDE',
                    description=(
                        f'{request.user.get_full_name()} made an exceptional standings override '
                        f'for {pt.team.name} in {pt.pool.name} ({competition.name}) and '
                        f'submitted this override to SG tracking. Reason: {exceptional_reason}'
                    ),
                    object_repr=str(pt),
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    extra_data={
                        'submitted_to_sg': True,
                        'exceptional_case': True,
                        'reason': exceptional_reason,
                        'before': before_state,
                        'after': after_state,
                    },
                )
                messages.success(request, f'Standings updated for {pt.team.name}.')
            except PoolTeam.DoesNotExist:
                messages.error(request, 'Pool team not found.')

        elif action == 'recalculate':
            pool_id = request.POST.get('pool_id')
            try:
                pool = Pool.objects.get(pk=pool_id, competition=competition)
                from matches.stats_engine import recalculate_pool_standings
                recalculate_pool_standings(pool)
                messages.success(request, f'Standings recalculated for {pool.name}.')
            except Pool.DoesNotExist:
                messages.error(request, 'Pool not found.')

        elif action == 'recalculate_all':
            pools = Pool.objects.filter(competition=competition)
            from matches.stats_engine import recalculate_pool_standings
            for pool in pools:
                recalculate_pool_standings(pool)
            messages.success(request, f'All pool standings recalculated for {competition.name}.')

        return redirect('coordinator_edit_standings', pk=pk)

    pools = Pool.objects.filter(competition=competition).prefetch_related('pool_teams__team').order_by('name')
    pool_data = []
    for pool in pools:
        teams = pool.pool_teams.select_related('team').all()
        sorted_teams = sorted(
            teams,
            key=lambda pt: (pt.points, pt.goal_difference, pt.goals_for),
            reverse=True,
        )
        pool_data.append({'pool': pool, 'teams': sorted_teams})

    return render(request, 'portal/coordinator/edit_standings.html', {
        'competition': competition,
        'pool_data': pool_data,
    })


@role_required('coordinator', 'admin')
def coordinator_match_reports_view(request):
    """Coordinator: View and approve match reports for their discipline."""
    from matches.models import MatchReport, MatchReportStatus

    discipline = _coordinator_discipline(request.user)
    if discipline:
        reports = MatchReport.objects.filter(
            fixture__competition__sport_type__in=_coordinator_variants(discipline)
        )
    else:
        reports = MatchReport.objects.none()

    status_filter = request.GET.get('status', 'submitted')
    if status_filter:
        reports = reports.filter(status=status_filter)

    reports = reports.select_related(
        'fixture__competition', 'fixture__home_team', 'fixture__away_team',
        'referee__user',
    ).order_by('-submitted_at')

    return render(request, 'portal/coordinator/match_reports.html', {
        'reports': reports,
        'status_filter': status_filter,
        'status_choices': MatchReportStatus.choices,
        'discipline_label': _coordinator_label(discipline),
    })


@role_required('coordinator', 'admin')
def coordinator_squads_view(request):
    """Coordinator: View match-day squads for their discipline."""
    discipline = _coordinator_discipline(request.user)
    if discipline:
        squads = SquadSubmission.objects.filter(
            fixture__competition__sport_type__in=_coordinator_variants(discipline)
        )
    else:
        squads = SquadSubmission.objects.none()

    status_filter = request.GET.get('status', '')
    if status_filter:
        squads = squads.filter(status=status_filter)

    squads = squads.select_related(
        'fixture__competition', 'fixture__home_team', 'fixture__away_team',
        'team',
    ).order_by('-created_at')

    return render(request, 'portal/coordinator/squads.html', {
        'squads': squads,
        'status_filter': status_filter,
        'status_choices': SquadStatus.choices,
        'discipline_label': _coordinator_label(discipline),
    })


@role_required('coordinator', 'admin')
def coordinator_statistics_view(request, pk):
    """Coordinator: View and manage statistics for a competition (top scorers, etc.)."""
    from competitions.models import Competition, Pool, PoolTeam
    from matches.stats_engine import get_top_scorers, get_top_assisters, get_disciplinary_table, get_fair_play_table

    competition = get_object_or_404(Competition, pk=pk)
    discipline = _coordinator_discipline(request.user)
    if discipline and competition.sport_type not in _coordinator_variants(discipline) and not request.user.is_superuser:
        messages.error(request, 'This competition is not in your discipline.')
        return redirect('coordinator_dashboard')

    top_scorers = get_top_scorers(competition)
    top_assisters = get_top_assisters(competition)
    disciplinary = get_disciplinary_table(competition)
    fair_play_table = get_fair_play_table(competition)

    # Standings per pool
    pools = Pool.objects.filter(competition=competition).prefetch_related('pool_teams__team').order_by('name')
    pool_data = []
    for pool in pools:
        teams = pool.pool_teams.select_related('team').all()
        sorted_teams = sorted(
            teams,
            key=lambda pt: (pt.points, pt.goal_difference, pt.goals_for),
            reverse=True,
        )
        pool_data.append({'pool': pool, 'teams': sorted_teams})

    return render(request, 'portal/coordinator/statistics.html', {
        'competition': competition,
        'top_scorers': top_scorers,
        'top_assisters': top_assisters,
        'disciplinary': disciplinary,
        'fair_play_table': fair_play_table,
        'pool_data': pool_data,
    })


@role_required('coordinator', 'admin')
def coordinator_referees_view(request):
    """Coordinator: View all referees and manage pending approvals."""
    pending = RefereeProfile.objects.filter(is_approved=False).select_related('user').order_by('-created_at')
    approved = RefereeProfile.objects.filter(is_approved=True).select_related('user').order_by('user__last_name')

    if request.method == 'POST':
        profile_id = request.POST.get('profile_id')
        action = request.POST.get('action')
        profile = get_object_or_404(RefereeProfile, pk=profile_id)

        if action == 'approve':
            profile.is_approved = True
            profile.approved_by = request.user
            profile.approved_at = timezone.now()
            profile.save()
            user = profile.user
            user.is_active = True
            temp_pw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            user.set_password(temp_pw)
            user.must_change_password = True
            user.save()
            try:
                send_credentials_email(user, temp_pw, 'Referee')
                messages.success(request, f'✅ {user.get_full_name()} approved! Login credentials sent to {user.email}.')
            except Exception:
                messages.warning(request, f'✅ {user.get_full_name()} approved but credential email failed. Contact them directly.')
        elif action == 'reject':
            user = profile.user
            user_name = user.get_full_name()
            profile.delete()
            user.delete()
            messages.warning(request, f'❌ {user_name} rejected and removed.')

        return redirect('coordinator_referees')

    return render(request, 'portal/coordinator/referees.html', {
        'pending': pending,
        'approved': approved,
        'stats': {
            'pending': pending.count(),
            'approved': approved.count(),
            'total': pending.count() + approved.count(),
        },
    })


@role_required('coordinator', 'admin')
def coordinator_appointments_view(request):
    """Coordinator: Manage referee appointments for discipline fixtures."""
    from referees.models import AppointmentRole, get_required_roles, get_optional_roles

    discipline = _coordinator_discipline(request.user)
    today = date.today()
    filter_status = request.GET.get('status', 'upcoming')

    if discipline:
        fixtures_qs = Fixture.objects.filter(
            competition__sport_type__in=_coordinator_variants(discipline)
        )
    else:
        fixtures_qs = Fixture.objects.none()

    fixtures_qs = fixtures_qs.select_related(
        'competition', 'home_team', 'away_team', 'venue',
    ).prefetch_related('referee_appointments__referee__user')

    if filter_status == 'upcoming':
        fixtures_qs = fixtures_qs.filter(match_date__gte=today).exclude(status__in=['cancelled'])
    elif filter_status == 'past':
        fixtures_qs = fixtures_qs.filter(match_date__lt=today)

    fixtures_qs = fixtures_qs.order_by('match_date', 'kickoff_time')

    role_labels = dict(AppointmentRole.choices)
    fixture_data = []
    total_needing = 0
    total_fully = 0

    for fixture in fixtures_qs:
        required_roles = get_required_roles(fixture.competition.sport_type)
        optional_roles = get_optional_roles(fixture.competition.sport_type)
        appointments = {a.role: a for a in fixture.referee_appointments.all() if a.status != 'replaced'}
        roles_info = []
        filled = 0
        for role_key in required_roles:
            appt = appointments.get(role_key)
            roles_info.append({
                'role_key': role_key,
                'role_label': role_labels.get(role_key, role_key),
                'appointment': appt,
                'referee_name': appt.referee.user.get_full_name() if appt else None,
                'status_display': appt.get_status_display() if appt else 'Not Appointed',
                'is_mandatory': True,
            })
            if appt:
                filled += 1

        for role_key in optional_roles:
            appt = appointments.get(role_key)
            roles_info.append({
                'role_key': role_key,
                'role_label': role_labels.get(role_key, role_key),
                'appointment': appt,
                'referee_name': appt.referee.user.get_full_name() if appt else None,
                'status_display': appt.get_status_display() if appt else 'Not Appointed',
                'is_mandatory': False,
            })

        needs_officials = filled < len(required_roles)
        if needs_officials:
            total_needing += 1
        if filled == len(required_roles):
            total_fully += 1

        fixture_data.append({
            'fixture': fixture,
            'roles': roles_info,
            'filled': filled,
            'total_roles': len(required_roles),
            'needs_officials': needs_officials,
        })

    return render(request, 'portal/coordinator/appointments.html', {
        'fixture_data': fixture_data,
        'filter_status': filter_status,
        'total_fixtures': len(fixture_data),
        'total_needing': total_needing,
        'total_fully': total_fully,
        'approved_referees_count': RefereeProfile.objects.filter(is_approved=True).count(),
        'discipline_label': _coordinator_label(discipline),
    })


@role_required('coordinator', 'admin')
def coordinator_competition_rules_view(request, pk):
    """Coordinator: Define competition criteria / rules for their discipline competition."""
    competition = get_object_or_404(Competition, pk=pk)
    discipline = _coordinator_discipline(request.user)
    if discipline and competition.sport_type not in _coordinator_variants(discipline) and not request.user.is_superuser:
        messages.error(request, 'This competition is not in your discipline.')
        return redirect('coordinator_dashboard')

    if request.method == 'POST':
        competition.rules = request.POST.get('rules', '')
        competition.save(update_fields=['rules'])
        messages.success(request, f'Rules updated for {competition.name}.')
        return redirect('coordinator_competition_manage', pk=pk)

    return render(request, 'portal/coordinator/edit_rules.html', {
        'competition': competition,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   TREASURER PORTAL
# ══════════════════════════════════════════════════════════════════════════════

@role_required('treasurer', 'admin')
def treasurer_dashboard_view(request):
    """Treasurer home — overview of county payments and county registration status."""
    current_season = str(date.today().year)

    # County payment stats
    county_payments = CountyPayment.objects.filter(season=current_season)
    counties_paid = county_payments.filter(payment_status__in=['paid', 'waived']).count()
    counties_pending = county_payments.filter(payment_status='pending').count()
    total_collected = sum(
        cp.participation_fee for cp in county_payments
        if cp.payment_status in ('paid', 'waived')
    )

    # County registration stats (new canonical channel)
    pending_count = CountyRegistration.objects.filter(
        status=CountyRegStatus.PAYMENT_SUBMITTED
    ).count()
    paid_count = pending_count
    approved_count = CountyRegistration.objects.filter(
        status=CountyRegStatus.APPROVED
    ).count()
    rejected_count = CountyRegistration.objects.filter(
        status=CountyRegStatus.REJECTED
    ).count()

    # Recent county registrations
    recent = CountyRegistration.objects.select_related('user').order_by('-created_at')[:5]
    # Recent county payments
    recent_payments = county_payments.order_by('-updated_at')[:5]

    return render(request, 'portal/treasurer/dashboard.html', {
        'pending_count':    pending_count,
        'paid_count':       paid_count,
        'approved_count':   approved_count,
        'rejected_count':   rejected_count,
        'recent_teams':     recent,
        'registration_fee': COUNTY_REGISTRATION_FEE_CAP,
        'counties_paid':    counties_paid,
        'counties_pending': counties_pending,
        'total_collected':  total_collected,
        'recent_payments':  recent_payments,
        'current_season':   current_season,
    })


@role_required('treasurer', 'admin')
def treasurer_teams_view(request):
    """Legacy endpoint kept for compatibility; county registration is now the only channel."""
    messages.info(request, 'Legacy team registration flow has been retired. Use county registrations.')
    return redirect('treasurer_county_registrations')


@role_required('treasurer', 'admin')
def treasurer_county_payments_view(request):
    """
    Treasurer manages county-level payments.
    Each county pays KSh 250,000 per season to cover ALL sports.
    """
    current_season = str(date.today().year)
    season = request.GET.get('season', current_season)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_county':
            county = request.POST.get('county', '').strip()
            if not county:
                messages.error(request, 'Please select a county.')
            elif CountyPayment.objects.filter(county=county, season=season).exists():
                messages.warning(request, f'{county} already has a payment record for {season}.')
            else:
                CountyPayment.objects.create(
                    county=county,
                    season=season,
                    participation_fee=COUNTY_REGISTRATION_FEE_CAP,
                )
                messages.success(request, f'County payment record created for {county} ({season}).')

        elif action == 'confirm_payment':
            payment_id = request.POST.get('payment_id')
            ref = request.POST.get('payment_reference', '').strip()
            payment_date_str = request.POST.get('payment_date', '').strip()
            notes = request.POST.get('notes', '').strip()

            if not ref:
                messages.error(request, 'Please enter the M-Pesa / payment reference.')
            else:
                try:
                    cp = CountyPayment.objects.get(pk=payment_id)
                    cp.payment_status = PaymentStatus.PAID
                    cp.payment_reference = ref
                    cp.confirmed_by = request.user
                    cp.confirmed_at = timezone.now()
                    cp.notes = notes
                    if payment_date_str:
                        from datetime import datetime as dt
                        cp.payment_date = dt.strptime(payment_date_str, '%Y-%m-%d').date()
                    else:
                        cp.payment_date = date.today()
                    cp.save()

                    # Also unlock all teams from this county
                    Team.objects.filter(
                        county__name=cp.county, payment_confirmed=False
                    ).update(
                        payment_confirmed=True,
                        payment_reference=ref,
                        payment_amount=COUNTY_REGISTRATION_FEE_CAP,
                        payment_confirmed_by=request.user,
                        payment_confirmed_at=timezone.now(),
                    )

                    # Audit log
                    from admin_dashboard.models import ActivityLog as AuditLog
                    AuditLog.objects.create(
                        user=request.user,
                        action='COUNTY_PAYMENT_CONFIRMED',
                        description=(
                            f'{request.user.get_full_name()} confirmed county payment for '
                            f'{cp.county} — Season {season} (Ref: {ref})'
                        ),
                        object_repr=str(cp),
                        ip_address=request.META.get('REMOTE_ADDR', ''),
                    )
                    messages.success(request, f'Payment confirmed for {cp.county} (Ref: {ref}).')
                except CountyPayment.DoesNotExist:
                    messages.error(request, 'Payment record not found.')

        elif action == 'waive_payment':
            payment_id = request.POST.get('payment_id')
            notes = request.POST.get('notes', '').strip()
            try:
                cp = CountyPayment.objects.get(pk=payment_id)
                cp.payment_status = PaymentStatus.WAIVED
                cp.confirmed_by = request.user
                cp.confirmed_at = timezone.now()
                cp.notes = notes or 'Payment waived'
                cp.save()

                # Unlock teams
                Team.objects.filter(
                    county=cp.county, payment_confirmed=False
                ).update(
                    payment_confirmed=True,
                    payment_confirmed_by=request.user,
                    payment_confirmed_at=timezone.now(),
                )

                messages.success(request, f'Payment waived for {cp.county}.')
            except CountyPayment.DoesNotExist:
                messages.error(request, 'Payment record not found.')

        return redirect('treasurer_county_payments')

    county_payments = CountyPayment.objects.filter(season=season).order_by('county')
    paid = county_payments.filter(payment_status__in=['paid', 'waived'])
    pending = county_payments.filter(payment_status='pending')

    # Counties from KenyaCounty enum that don't have a payment record yet
    existing_counties = set(county_payments.values_list('county', flat=True))
    available_counties = [
        (c.value, c.label) for c in KenyaCounty
        if c.value not in existing_counties
    ]

    return render(request, 'portal/treasurer/county_payments.html', {
        'paid_payments':       paid,
        'pending_payments':    pending,
        'paid_count':          paid.count(),
        'pending_count':       pending.count(),
        'total_collected':     sum(cp.participation_fee for cp in paid),
        'registration_fee':    COUNTY_REGISTRATION_FEE_CAP,
        'season':              season,
        'current_season':      current_season,
        'available_counties':  available_counties,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   COMPETITION MANAGER — STATISTICS & LEADERBOARDS
# ══════════════════════════════════════════════════════════════════════════════

@role_required('competition_manager', 'chief_sports_officer', 'admin')
def competition_standings_view(request, pk):
    """
    Competition Manager view: full standings, knockout bracket, and statistics.
    """
    competition = get_object_or_404(Competition, pk=pk)
    from competitions.models import Pool, PoolTeam

    # Group standings
    pools = Pool.objects.filter(competition=competition).prefetch_related(
        'pool_teams__team'
    ).order_by('name')

    pool_standings = []
    for pool in pools:
        teams = pool.pool_teams.all().order_by('-won', 'lost')
        # Sort by points, then goal difference, then goals scored
        sorted_teams = sorted(
            teams,
            key=lambda pt: (pt.points, pt.goal_difference, pt.goals_for),
            reverse=True
        )
        pool_standings.append({
            'pool': pool,
            'teams': sorted_teams,
        })

    # Knockout fixtures
    from competitions.models import KnockoutRound
    knockout_fixtures = Fixture.objects.filter(
        competition=competition, is_knockout=True
    ).select_related('home_team', 'away_team', 'venue', 'winner').order_by(
        'knockout_round', 'bracket_position', 'match_date'
    )

    # Group knockout fixtures by round
    knockout_rounds = {}
    for f in knockout_fixtures:
        round_name = f.get_knockout_round_display() if f.knockout_round else 'Unknown'
        if round_name not in knockout_rounds:
            knockout_rounds[round_name] = []
        knockout_rounds[round_name].append(f)

    # Statistics
    from matches.stats_engine import (
        get_top_scorers, get_top_assisters,
        get_disciplinary_table, get_clean_sheet_leaders,
    )
    top_scorers = get_top_scorers(competition, limit=10)
    top_assisters = get_top_assisters(competition, limit=10)
    disciplinary = get_disciplinary_table(competition, limit=10)
    clean_sheets = get_clean_sheet_leaders(competition, limit=5)

    return render(request, 'portal/competition_standings.html', {
        'competition':      competition,
        'pool_standings':   pool_standings,
        'knockout_rounds':  knockout_rounds,
        'top_scorers':      top_scorers,
        'top_assisters':    top_assisters,
        'disciplinary':     disciplinary,
        'clean_sheets':     clean_sheets,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def competition_reports_view(request, pk):
    """
    Competition Manager reviews and approves match reports for a competition.
    """
    competition = get_object_or_404(Competition, pk=pk)
    filter_status = request.GET.get('status', 'submitted')

    reports_qs = MatchReport.objects.filter(
        fixture__competition=competition
    ).select_related(
        'fixture__home_team', 'fixture__away_team',
        'fixture__venue', 'referee__user'
    ).order_by('-submitted_at')

    if filter_status and filter_status != 'all':
        reports_qs = reports_qs.filter(status=filter_status)

    return render(request, 'portal/competition_reports.html', {
        'competition': competition,
        'reports': reports_qs,
        'filter_status': filter_status,
        'submitted_count': MatchReport.objects.filter(
            fixture__competition=competition, status='submitted'
        ).count(),
        'approved_count': MatchReport.objects.filter(
            fixture__competition=competition, status='approved'
        ).count(),
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def competition_report_approve_view(request, pk, report_pk):
    """
    Competition Manager approves or returns a specific match report.
    On approval: updates fixture scores, pool standings, and player statistics.
    """
    competition = get_object_or_404(Competition, pk=pk)
    report = get_object_or_404(MatchReport, pk=report_pk, fixture__competition=competition)
    events = report.events.select_related('team', 'player').order_by('minute')

    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('reviewer_notes', '')

        if action == 'approve':
            report.status = MatchReportStatus.APPROVED
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.reviewer_notes = notes

            # Update fixture
            fixture = report.fixture
            fixture.home_score = report.home_score
            fixture.away_score = report.away_score
            fixture.status = 'completed'
            fixture.save(update_fields=['home_score', 'away_score', 'status'])

            # Auto-update standings + player stats
            from matches.stats_engine import process_approved_report
            process_approved_report(report)

            report.save()

            # Audit log
            from admin_dashboard.models import ActivityLog as AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='MATCH_REPORT_APPROVED',
                description=(
                    f'{request.user.get_full_name()} approved match report: '
                    f'{fixture.home_team} {report.home_score}-{report.away_score} '
                    f'{fixture.away_team}'
                ),
                object_repr=str(report),
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(
                request,
                f'Match report approved — {fixture.home_team} '
                f'{report.home_score}-{report.away_score} {fixture.away_team}. '
                f'Standings and player statistics updated automatically.'
            )

        elif action == 'return':
            report.status = MatchReportStatus.RETURNED
            report.reviewer_notes = notes
            report.save()
            messages.warning(request, 'Match report returned for revision.')

        return redirect('competition_reports', pk=competition.pk)

    return render(request, 'portal/competition_report_approve.html', {
        'competition': competition,
        'report': report,
        'events': events,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   REFEREE MANAGER — MATCH APPOINTMENTS
# ══════════════════════════════════════════════════════════════════════════════

from referees.models import AppointmentRole, AppointmentStatus as ApptStatus, get_required_roles


@role_required('coordinator', 'admin')
def referee_appointments_view(request):
    """
    Referee Manager — overview of all fixtures that need officials,
    summary statistics and appointment status per match.
    """
    today = date.today()
    filter_status = request.GET.get('status', 'upcoming')  # upcoming | all | past

    # Base queryset: upcoming confirmed/pending fixtures
    fixtures_qs = Fixture.objects.select_related(
        'competition', 'home_team', 'away_team', 'venue',
    ).prefetch_related('referee_appointments__referee__user')

    if filter_status == 'upcoming':
        fixtures_qs = fixtures_qs.filter(match_date__gte=today).exclude(status__in=['cancelled'])
    elif filter_status == 'past':
        fixtures_qs = fixtures_qs.filter(match_date__lt=today)
    else:
        fixtures_qs = fixtures_qs.all()

    fixtures_qs = fixtures_qs.order_by('match_date', 'kickoff_time')

    # Build enriched list
    role_labels = dict(AppointmentRole.choices)
    fixture_data = []
    total_needing = 0
    total_fully_appointed = 0
    total_partially = 0

    for fixture in fixtures_qs:
        required_roles = get_required_roles(fixture.competition.sport_type)
        appointments = {a.role: a for a in fixture.referee_appointments.all()}
        roles_info = []
        filled = 0
        for role_key in required_roles:
            appt = appointments.get(role_key)
            roles_info.append({
                'role_key': role_key,
                'role_label': role_labels.get(role_key, role_key),
                'appointment': appt,
                'referee_name': appt.referee.user.get_full_name() if appt else None,
                'status': appt.status if appt else None,
                'status_display': appt.get_status_display() if appt else 'Not Appointed',
            })
            if appt:
                filled += 1

        needs_officials = filled < len(required_roles)
        is_fully_appointed = filled == len(required_roles)

        if needs_officials:
            total_needing += 1
        if is_fully_appointed:
            total_fully_appointed += 1
        elif filled > 0:
            total_partially += 1

        fixture_data.append({
            'fixture': fixture,
            'roles': roles_info,
            'filled': filled,
            'total_roles': len(required_roles),
            'needs_officials': needs_officials,
            'is_fully_appointed': is_fully_appointed,
        })

    # Summary stats
    approved_referees_count = RefereeProfile.objects.filter(is_approved=True).count()

    return render(request, 'portal/referee_appointments.html', {
        'fixture_data': fixture_data,
        'filter_status': filter_status,
        'total_fixtures': len(fixture_data),
        'total_needing': total_needing,
        'total_fully_appointed': total_fully_appointed,
        'total_partially': total_partially,
        'approved_referees_count': approved_referees_count,
    })


@role_required('coordinator', 'admin')
def referee_appoint_view(request, fixture_pk):
    """
    Referee Manager appoints officials to a specific fixture.
    Shows fixture info, current appointments, and forms to assign each role.
    """
    fixture = get_object_or_404(
        Fixture.objects.select_related(
            'competition', 'home_team', 'away_team', 'venue',
        ),
        pk=fixture_pk,
    )
    today = date.today()

    required_roles = get_required_roles(fixture.competition.sport_type)
    from referees.models import get_optional_roles
    optional_roles = get_optional_roles(fixture.competition.sport_type)
    all_roles = required_roles + optional_roles
    role_labels = dict(AppointmentRole.choices)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'appoint':
            role = request.POST.get('role', '')
            referee_id = request.POST.get('referee_id', '')
            notes = request.POST.get('notes', '')

            if role not in all_roles:
                messages.error(request, 'Invalid role.')
            elif not referee_id:
                messages.error(request, 'Please select a referee.')
            else:
                try:
                    referee_profile = RefereeProfile.objects.get(pk=referee_id, is_approved=True)
                except RefereeProfile.DoesNotExist:
                    messages.error(request, 'Selected referee not found or not approved.')
                    return redirect('referee_appoint', fixture_pk=fixture.pk)

                # Check for duplicate (same referee already appointed in this fixture for another role)
                existing_same_role = RefereeAppointment.objects.filter(
                    fixture=fixture, role=role
                ).exclude(status='replaced').first()

                if existing_same_role:
                    # Replace existing appointment
                    existing_same_role.status = 'replaced'
                    existing_same_role.save()

                # Check referee doesn't have a conflicting appointment on same date
                conflict = RefereeAppointment.objects.filter(
                    referee=referee_profile,
                    fixture__match_date=fixture.match_date,
                    status__in=['pending', 'confirmed'],
                ).exclude(fixture=fixture).first()

                if conflict:
                    messages.warning(
                        request,
                        f'⚠️ {referee_profile.user.get_full_name()} already has an appointment '
                        f'on {fixture.match_date.strftime("%d %b %Y")} '
                        f'({conflict.fixture}). Appointment created anyway — please verify.'
                    )

                # Create appointment
                RefereeAppointment.objects.create(
                    fixture=fixture,
                    referee=referee_profile,
                    role=role,
                    appointed_by=request.user,
                    notes=notes,
                )
                messages.success(
                    request,
                    f'✅ {referee_profile.user.get_full_name()} appointed as '
                    f'{role_labels.get(role, role)} for {fixture}.'
                )

        elif action == 'remove':
            appt_id = request.POST.get('appointment_id', '')
            try:
                appt = RefereeAppointment.objects.get(pk=appt_id, fixture=fixture)
                ref_name = appt.referee.user.get_full_name()
                role_display = appt.get_role_display()
                appt.status = 'replaced'
                appt.save()
                messages.success(request, f'🔄 {ref_name} ({role_display}) removed from this fixture.')
            except RefereeAppointment.DoesNotExist:
                messages.error(request, 'Appointment not found.')

        return redirect('referee_appoint', fixture_pk=fixture.pk)

    # ── Build role data ──
    current_appointments = {
        a.role: a for a in RefereeAppointment.objects.filter(
            fixture=fixture
        ).exclude(status='replaced').select_related('referee__user')
    }

    roles_data = []
    for role_key in required_roles:
        appt = current_appointments.get(role_key)
        roles_data.append({
            'role_key': role_key,
            'role_label': role_labels.get(role_key, role_key),
            'appointment': appt,
            'referee_name': appt.referee.user.get_full_name() if appt else None,
            'status': appt.status if appt else None,
            'status_display': appt.get_status_display() if appt else None,
            'is_mandatory': True,
        })
    for role_key in optional_roles:
        appt = current_appointments.get(role_key)
        roles_data.append({
            'role_key': role_key,
            'role_label': role_labels.get(role_key, role_key),
            'appointment': appt,
            'referee_name': appt.referee.user.get_full_name() if appt else None,
            'status': appt.status if appt else None,
            'status_display': appt.get_status_display() if appt else None,
            'is_mandatory': False,
        })

    # ── Available referees (approved, with availability info for match date) ──
    approved_referees = RefereeProfile.objects.filter(
        is_approved=True
    ).select_related('user').order_by('user__last_name')

    # Get availability map for this date
    availability_map = dict(
        RefereeAvailability.objects.filter(
            referee__in=approved_referees,
            date=fixture.match_date,
        ).values_list('referee_id', 'status')
    )

    # Get appointments already on this match date (to flag busy referees)
    busy_on_date = set(
        RefereeAppointment.objects.filter(
            fixture__match_date=fixture.match_date,
            status__in=['pending', 'confirmed'],
        ).exclude(fixture=fixture).values_list('referee_id', flat=True)
    )

    # Already appointed to THIS fixture
    already_appointed_ids = set(
        a.referee_id for a in current_appointments.values()
    )

    referees_list = []
    for ref in approved_referees:
        avail = availability_map.get(ref.pk, None)
        is_busy = ref.pk in busy_on_date
        is_appointed_here = ref.pk in already_appointed_ids
        referees_list.append({
            'profile': ref,
            'full_name': ref.user.get_full_name(),
            'level': ref.get_level_display(),
            'county': ref.county,
            'total_matches': ref.total_matches,
            'avg_rating': ref.avg_rating,
            'availability': avail,
            'availability_label': (
                'Available' if avail == 'available'
                else 'Unavailable' if avail == 'unavailable'
                else 'Not Set'
            ),
            'is_busy': is_busy,
            'is_appointed_here': is_appointed_here,
        })

    return render(request, 'portal/referee_appoint.html', {
        'fixture': fixture,
        'roles_data': roles_data,
        'referees_list': referees_list,
        'required_roles': required_roles,
        'role_labels': role_labels,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   COMPETITION MANAGER — FULL PORTAL VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_dashboard_view(request):
    """Competition Manager dashboard — overview of all competitions and key stats."""
    from competitions.models import (
        Competition, Fixture, Venue, Pool, PoolTeam,
        SportType, CompetitionStatus, CountyPayment, PaymentStatus,
    )
    from matches.models import MatchReport

    competitions = Competition.objects.all()
    active = competitions.filter(status__in=['active', 'group_stage', 'knockout'])
    registration = competitions.filter(status='registration')

    # Key counts
    stats = {
        'total_competitions': competitions.count(),
        'active_competitions': active.count(),
        'total_fixtures': Fixture.objects.count(),
        'completed_fixtures': Fixture.objects.filter(status='completed').count(),
        'pending_reports': MatchReport.objects.filter(status='submitted').count(),
        'total_teams': Team.objects.filter(status='registered').count(),
        'total_venues': Venue.objects.filter(is_active=True).count(),
        'paid_counties': CountyPayment.objects.filter(
            payment_status__in=['paid', 'waived']
        ).count(),
        'pending_county_players': CountyPlayer.objects.filter(verification_status='pending').count(),
    }

    # Recent fixture results
    recent_results = Fixture.objects.filter(
        status='completed'
    ).select_related(
        'competition', 'home_team', 'away_team'
    ).order_by('-updated_at')[:8]

    # Pending reports needing approval
    pending_reports = MatchReport.objects.filter(
        status='submitted'
    ).select_related(
        'fixture__competition', 'fixture__home_team', 'fixture__away_team',
        'referee__user'
    ).order_by('-submitted_at')[:5]

    # Sport breakdown
    sport_breakdown = []
    for sport_val, sport_label in SportType.choices:
        count = competitions.filter(sport_type=sport_val).count()
        if count > 0:
            sport_breakdown.append({'label': sport_label, 'count': count})

    return render(request, 'portal/cm/dashboard.html', {
        'stats': stats,
        'active_competitions': active,
        'registration_competitions': registration,
        'recent_results': recent_results,
        'pending_reports': pending_reports,
        'sport_breakdown': sport_breakdown,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_create_competition_view(request):
    """Create a new competition."""
    from competitions.models import (
        Competition, SportType, GenderChoice, CompetitionFormat,
        AgeGroup, CompetitionStatus,
    )

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        sport_type = request.POST.get('sport_type', SportType.FOOTBALL_MEN)
        gender = request.POST.get('gender', GenderChoice.MEN)
        format_type = request.POST.get('format_type', CompetitionFormat.GROUP_AND_KNOCKOUT)
        season = request.POST.get('season', '2025')
        age_group = request.POST.get('age_group', AgeGroup.U17)
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        max_teams = request.POST.get('max_teams', 16)
        teams_per_group = request.POST.get('teams_per_group', 4)
        qualify_from_group = request.POST.get('qualify_from_group', 2)
        description = request.POST.get('description', '')
        rules = request.POST.get('rules', '')

        if not name or not start_date or not end_date:
            messages.error(request, 'Name, start date, and end date are required.')
        elif Competition.objects.filter(name=name).exists():
            messages.error(request, f'A competition named "{name}" already exists.')
        else:
            comp = Competition.objects.create(
                name=name,
                sport_type=sport_type,
                gender=gender,
                format_type=format_type,
                season=season,
                age_group=age_group,
                status=CompetitionStatus.REGISTRATION,
                start_date=start_date,
                end_date=end_date,
                max_teams=int(max_teams),
                teams_per_group=int(teams_per_group),
                qualify_from_group=int(qualify_from_group),
                description=description,
                rules=rules,
                created_by=request.user,
            )
            # Audit log
            from admin_dashboard.models import ActivityLog
            ActivityLog.objects.create(
                user=request.user,
                action='COMPETITION_CREATED',
                description=f'{request.user.get_full_name()} created competition: {comp.name}',
                object_repr=str(comp),
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(request, f'Competition "{comp.name}" created successfully.')
            return redirect('cm_competition_manage', pk=comp.pk)

    return render(request, 'portal/cm/create_competition.html', {
        'sport_types': SportType.choices,
        'gender_choices': GenderChoice.choices,
        'format_choices': CompetitionFormat.choices,
        'age_groups': AgeGroup.choices,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_edit_competition_view(request, pk):
    """Edit an existing competition."""
    from competitions.models import (
        Competition, SportType, GenderChoice, CompetitionFormat,
        AgeGroup, CompetitionStatus,
    )
    competition = get_object_or_404(Competition, pk=pk)

    if request.method == 'POST':
        competition.name = request.POST.get('name', competition.name).strip()
        competition.sport_type = request.POST.get('sport_type', competition.sport_type)
        competition.gender = request.POST.get('gender', competition.gender)
        competition.format_type = request.POST.get('format_type', competition.format_type)
        competition.season = request.POST.get('season', competition.season)
        competition.age_group = request.POST.get('age_group', competition.age_group)
        competition.status = request.POST.get('status', competition.status)
        competition.start_date = request.POST.get('start_date', competition.start_date)
        competition.end_date = request.POST.get('end_date', competition.end_date)
        competition.max_teams = int(request.POST.get('max_teams', competition.max_teams))
        competition.teams_per_group = int(request.POST.get('teams_per_group', competition.teams_per_group))
        competition.qualify_from_group = int(request.POST.get('qualify_from_group', competition.qualify_from_group))
        competition.description = request.POST.get('description', competition.description)
        competition.rules = request.POST.get('rules', competition.rules)
        competition.save()

        messages.success(request, f'Competition "{competition.name}" updated.')
        return redirect('cm_competition_manage', pk=competition.pk)

    return render(request, 'portal/cm/edit_competition.html', {
        'competition': competition,
        'sport_types': SportType.choices,
        'gender_choices': GenderChoice.choices,
        'format_choices': CompetitionFormat.choices,
        'age_groups': AgeGroup.choices,
        'status_choices': CompetitionStatus.choices,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_competition_manage_view(request, pk):
    """
    Central management hub for a competition.
    Shows pools, teams, fixtures, standings at a glance.
    """
    from competitions.models import (
        Competition, Pool, PoolTeam, Fixture, Venue, KnockoutRound,
        CountyPayment,
    )
    from matches.models import MatchReport

    competition = get_object_or_404(Competition, pk=pk)

    # Pools & teams
    pools = Pool.objects.filter(competition=competition).prefetch_related(
        'pool_teams__team'
    ).order_by('name')

    pool_data = []
    for pool in pools:
        teams = pool.pool_teams.select_related('team').all()
        sorted_teams = sorted(
            teams,
            key=lambda pt: (pt.points, pt.goal_difference, pt.goals_for),
            reverse=True
        )
        pool_data.append({'pool': pool, 'teams': sorted_teams})

    # Registered teams eligible for this competition (paid county, approved)
    eligible_teams = Team.objects.filter(
        status='registered',
        payment_confirmed=True,
        sport_type=competition.sport_type,
    ).exclude(
        pk__in=PoolTeam.objects.filter(
            pool__competition=competition
        ).values_list('team_id', flat=True)
    ).order_by('county', 'name')

    # All teams already in this competition
    teams_in_comp = Team.objects.filter(
        pool_memberships__pool__competition=competition
    ).distinct()

    # Fixtures
    group_fixtures = Fixture.objects.filter(
        competition=competition, is_knockout=False
    ).select_related('home_team', 'away_team', 'venue', 'pool').order_by('match_date', 'kickoff_time')

    knockout_fixtures = Fixture.objects.filter(
        competition=competition, is_knockout=True
    ).select_related('home_team', 'away_team', 'venue', 'winner').order_by(
        'knockout_round', 'bracket_position'
    )

    # Venues
    venues = Venue.objects.filter(is_active=True).order_by('county', 'name')

    # Match reports
    pending_reports = MatchReport.objects.filter(
        fixture__competition=competition, status='submitted'
    ).count()
    approved_reports = MatchReport.objects.filter(
        fixture__competition=competition, status='approved'
    ).count()

    return render(request, 'portal/cm/manage_competition.html', {
        'competition': competition,
        'pool_data': pool_data,
        'eligible_teams': eligible_teams,
        'teams_in_comp': teams_in_comp,
        'group_fixtures': group_fixtures,
        'knockout_fixtures': knockout_fixtures,
        'venues': venues,
        'pending_reports': pending_reports,
        'approved_reports': approved_reports,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_manage_pools_view(request, pk):
    """Create/delete pools and assign/remove teams."""
    from competitions.models import Competition, Pool, PoolTeam, CountyPayment

    competition = get_object_or_404(Competition, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create_pool':
            pool_name = request.POST.get('pool_name', '').strip()
            if not pool_name:
                messages.error(request, 'Pool name is required.')
            elif Pool.objects.filter(competition=competition, name=pool_name).exists():
                messages.error(request, f'Pool "{pool_name}" already exists.')
            else:
                Pool.objects.create(competition=competition, name=pool_name)
                messages.success(request, f'Pool "{pool_name}" created.')

        elif action == 'delete_pool':
            pool_id = request.POST.get('pool_id')
            try:
                pool = Pool.objects.get(pk=pool_id, competition=competition)
                name = pool.name
                pool.delete()
                messages.success(request, f'Pool "{name}" deleted.')
            except Pool.DoesNotExist:
                messages.error(request, 'Pool not found.')

        elif action == 'add_team':
            pool_id = request.POST.get('pool_id')
            team_id = request.POST.get('team_id')
            try:
                pool = Pool.objects.get(pk=pool_id, competition=competition)
                team = Team.objects.get(pk=team_id)

                # Validate payment
                if not team.payment_confirmed:
                    messages.error(request, f'{team.name} cannot be pooled — payment not confirmed.')
                elif team.status != 'registered':
                    messages.error(request, f'{team.name} is not approved.')
                elif PoolTeam.objects.filter(pool__competition=competition, team=team).exists():
                    messages.error(request, f'{team.name} is already in a pool for this competition.')
                else:
                    PoolTeam.objects.create(pool=pool, team=team)
                    messages.success(request, f'{team.name} added to {pool.name}.')
                    # Auto-generate fixtures if pool now has >=2 teams
                    auto_fixtures = _auto_generate_pool_fixtures(pool, competition, request.user)
                    if auto_fixtures:
                        messages.info(request, f'{len(auto_fixtures)} fixtures auto-generated for {pool.name}. You can modify dates/times from the fixtures page.')
            except (Pool.DoesNotExist, Team.DoesNotExist):
                messages.error(request, 'Pool or team not found.')

        elif action == 'remove_team':
            pt_id = request.POST.get('pool_team_id')
            try:
                pt = PoolTeam.objects.get(pk=pt_id, pool__competition=competition)
                name = pt.team.name
                pool_name = pt.pool.name
                pt.delete()
                messages.success(request, f'{name} removed from {pool_name}.')
            except PoolTeam.DoesNotExist:
                messages.error(request, 'Team assignment not found.')

        return redirect('cm_manage_pools', pk=competition.pk)

    # GET
    pools = Pool.objects.filter(competition=competition).prefetch_related(
        'pool_teams__team'
    ).order_by('name')

    # Eligible teams not yet in any pool for this competition
    assigned_ids = PoolTeam.objects.filter(
        pool__competition=competition
    ).values_list('team_id', flat=True)

    eligible_teams = Team.objects.filter(
        status='registered',
        payment_confirmed=True,
        sport_type=competition.sport_type,
    ).exclude(pk__in=assigned_ids).order_by('county', 'name')

    return render(request, 'portal/cm/manage_pools.html', {
        'competition': competition,
        'pools': pools,
        'eligible_teams': eligible_teams,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_generate_fixtures_view(request, pk):
    """Generate fixtures for a competition."""
    from competitions.models import Competition, Fixture, Venue, Pool
    from competitions.fixture_engine import generate_all_fixtures

    competition = get_object_or_404(Competition, pk=pk)

    # Check if fixtures already exist
    existing_count = Fixture.objects.filter(competition=competition).count()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'generate':
            start_date_str = request.POST.get('start_date', '')
            kickoff_time_str = request.POST.get('kickoff_time', '14:00')
            group_interval = int(request.POST.get('group_interval', 7))
            knockout_interval = int(request.POST.get('knockout_interval', 3))
            venue_id = request.POST.get('venue_id', '')
            knockout_teams = request.POST.get('knockout_teams', '')

            from datetime import datetime
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                messages.error(request, 'Invalid start date.')
                return redirect('cm_generate_fixtures', pk=pk)

            try:
                kickoff_time = datetime.strptime(kickoff_time_str, '%H:%M').time()
            except (ValueError, TypeError):
                kickoff_time = datetime.strptime('14:00', '%H:%M').time()

            venue = None
            if venue_id:
                try:
                    venue = Venue.objects.get(pk=venue_id)
                except Venue.DoesNotExist:
                    pass

            ko_teams = int(knockout_teams) if knockout_teams else None

            try:
                fixtures = generate_all_fixtures(
                    competition, start_date, kickoff_time,
                    group_interval=group_interval,
                    knockout_interval=knockout_interval,
                    knockout_teams=ko_teams,
                    venue=venue,
                    created_by=request.user,
                )

                from admin_dashboard.models import ActivityLog
                ActivityLog.objects.create(
                    user=request.user,
                    action='FIXTURES_GENERATED',
                    description=(
                        f'{request.user.get_full_name()} generated {len(fixtures)} '
                        f'fixtures for {competition.name}'
                    ),
                    object_repr=str(competition),
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                )

                messages.success(
                    request,
                    f'{len(fixtures)} fixtures generated for {competition.name}.'
                )
            except ValueError as e:
                messages.error(request, str(e))

            return redirect('cm_competition_manage', pk=pk)

        elif action == 'clear':
            count = Fixture.objects.filter(competition=competition).count()
            Fixture.objects.filter(competition=competition).delete()
            messages.warning(request, f'{count} fixtures deleted.')
            return redirect('cm_generate_fixtures', pk=pk)

    venues = Venue.objects.filter(is_active=True).order_by('county', 'name')
    pools = Pool.objects.filter(competition=competition).prefetch_related('pool_teams')
    total_pool_teams = sum(p.pool_teams.count() for p in pools)

    return render(request, 'portal/cm/generate_fixtures.html', {
        'competition': competition,
        'existing_count': existing_count,
        'venues': venues,
        'pools': pools,
        'total_pool_teams': total_pool_teams,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_manage_venues_view(request):
    """Manage venues — list, create, edit."""
    from competitions.models import Venue

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            county = request.POST.get('county', '').strip()
            city = request.POST.get('city', '').strip()
            capacity = request.POST.get('capacity', 0)
            surface = request.POST.get('surface', 'Natural Grass')
            address = request.POST.get('address', '')
            facilities = request.POST.get('facilities', '')

            if not name or not county:
                messages.error(request, 'Venue name and county are required.')
            else:
                Venue.objects.create(
                    name=name, county=county, city=city,
                    capacity=int(capacity) if capacity else 0,
                    surface=surface, address=address, facilities=facilities,
                )
                messages.success(request, f'Venue "{name}" created.')

        elif action == 'toggle':
            venue_id = request.POST.get('venue_id')
            try:
                venue = Venue.objects.get(pk=venue_id)
                venue.is_active = not venue.is_active
                venue.save(update_fields=['is_active'])
                status = 'activated' if venue.is_active else 'deactivated'
                messages.success(request, f'Venue "{venue.name}" {status}.')
            except Venue.DoesNotExist:
                messages.error(request, 'Venue not found.')

        elif action == 'update':
            venue_id = request.POST.get('venue_id')
            try:
                venue = Venue.objects.get(pk=venue_id)
                venue.name = request.POST.get('name', venue.name).strip()
                venue.county = request.POST.get('county', venue.county).strip()
                venue.city = request.POST.get('city', venue.city).strip()
                venue.capacity = int(request.POST.get('capacity', venue.capacity) or 0)
                venue.surface = request.POST.get('surface', venue.surface)
                venue.address = request.POST.get('address', venue.address)
                venue.facilities = request.POST.get('facilities', venue.facilities)
                venue.save()
                messages.success(request, f'Venue "{venue.name}" updated.')
            except Venue.DoesNotExist:
                messages.error(request, 'Venue not found.')

        return redirect('cm_venues')

    venues = Venue.objects.all().order_by('county', 'name')
    active_venues = venues.filter(is_active=True)
    inactive_venues = venues.filter(is_active=False)

    return render(request, 'portal/cm/venues.html', {
        'active_venues': active_venues,
        'inactive_venues': inactive_venues,
        'total_venues': venues.count(),
        'county_choices': KenyaCounty.choices,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_allocate_venue_view(request, pk):
    """Allocate venues to fixtures for a competition."""
    from competitions.models import Competition, Fixture, Venue

    competition = get_object_or_404(Competition, pk=pk)

    if request.method == 'POST':
        # Bulk update venue assignments
        fixtures = Fixture.objects.filter(competition=competition)
        updated = 0
        for fixture in fixtures:
            venue_id = request.POST.get(f'venue_{fixture.pk}', '')
            if venue_id:
                try:
                    venue = Venue.objects.get(pk=venue_id)
                    if fixture.venue != venue:
                        fixture.venue = venue
                        fixture.save(update_fields=['venue'])
                        updated += 1
                except Venue.DoesNotExist:
                    pass
            elif fixture.venue:
                fixture.venue = None
                fixture.save(update_fields=['venue'])
                updated += 1

        messages.success(request, f'{updated} fixture venue(s) updated.')
        return redirect('cm_competition_manage', pk=pk)

    fixtures = Fixture.objects.filter(
        competition=competition
    ).select_related(
        'home_team', 'away_team', 'venue', 'pool'
    ).order_by('match_date', 'kickoff_time')

    venues = Venue.objects.filter(is_active=True).order_by('county', 'name')

    return render(request, 'portal/cm/allocate_venues.html', {
        'competition': competition,
        'fixtures': fixtures,
        'venues': venues,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_edit_standings_view(request, pk):
    """Admin override — manually edit pool team standings."""
    from competitions.models import Competition, Pool, PoolTeam

    competition = get_object_or_404(Competition, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_standings':
            pool_team_id = request.POST.get('pool_team_id')
            try:
                pt = PoolTeam.objects.get(pk=pool_team_id, pool__competition=competition)
                pt.played = int(request.POST.get('played', pt.played))
                pt.won = int(request.POST.get('won', pt.won))
                pt.drawn = int(request.POST.get('drawn', pt.drawn))
                pt.lost = int(request.POST.get('lost', pt.lost))
                pt.goals_for = int(request.POST.get('goals_for', pt.goals_for))
                pt.goals_against = int(request.POST.get('goals_against', pt.goals_against))
                pt.bonus_points = int(request.POST.get('bonus_points', pt.bonus_points))
                pt.save()

                from admin_dashboard.models import ActivityLog
                ActivityLog.objects.create(
                    user=request.user,
                    action='STANDINGS_OVERRIDE',
                    description=(
                        f'{request.user.get_full_name()} manually edited standings for '
                        f'{pt.team.name} in {pt.pool.name} ({competition.name})'
                    ),
                    object_repr=str(pt),
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                )
                messages.success(request, f'Standings updated for {pt.team.name}.')
            except PoolTeam.DoesNotExist:
                messages.error(request, 'Pool team not found.')

        elif action == 'recalculate':
            pool_id = request.POST.get('pool_id')
            try:
                pool = Pool.objects.get(pk=pool_id, competition=competition)
                from matches.stats_engine import recalculate_pool_standings
                recalculate_pool_standings(pool)
                messages.success(request, f'Standings recalculated for {pool.name}.')
            except Pool.DoesNotExist:
                messages.error(request, 'Pool not found.')

        elif action == 'recalculate_all':
            pools = Pool.objects.filter(competition=competition)
            from matches.stats_engine import recalculate_pool_standings
            for pool in pools:
                recalculate_pool_standings(pool)
            messages.success(request, f'All pool standings recalculated for {competition.name}.')

        return redirect('cm_edit_standings', pk=pk)

    pools = Pool.objects.filter(competition=competition).prefetch_related(
        'pool_teams__team'
    ).order_by('name')

    pool_data = []
    for pool in pools:
        teams = pool.pool_teams.select_related('team').all()
        sorted_teams = sorted(
            teams,
            key=lambda pt: (pt.points, pt.goal_difference, pt.goals_for),
            reverse=True
        )
        pool_data.append({'pool': pool, 'teams': sorted_teams})

    return render(request, 'portal/cm/edit_standings.html', {
        'competition': competition,
        'pool_data': pool_data,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_edit_fixture_view(request, pk, fixture_pk):
    """Edit a specific fixture (date, time, venue, teams for knockout)."""
    from competitions.models import Competition, Fixture, Venue

    competition = get_object_or_404(Competition, pk=pk)
    fixture = get_object_or_404(Fixture, pk=fixture_pk, competition=competition)

    if request.method == 'POST':
        fixture.match_date = request.POST.get('match_date', fixture.match_date)
        kickoff = request.POST.get('kickoff_time', '')
        if kickoff:
            from datetime import datetime
            try:
                fixture.kickoff_time = datetime.strptime(kickoff, '%H:%M').time()
            except ValueError:
                pass
        venue_id = request.POST.get('venue_id', '')
        if venue_id:
            try:
                fixture.venue = Venue.objects.get(pk=venue_id)
            except Venue.DoesNotExist:
                pass
        else:
            fixture.venue = None

        status = request.POST.get('status', fixture.status)
        if status:
            fixture.status = status

        # For knockout matches, allow team reassignment
        if fixture.is_knockout:
            home_id = request.POST.get('home_team_id', '')
            away_id = request.POST.get('away_team_id', '')
            if home_id:
                try:
                    fixture.home_team = Team.objects.get(pk=home_id)
                except Team.DoesNotExist:
                    pass
            if away_id:
                try:
                    fixture.away_team = Team.objects.get(pk=away_id)
                except Team.DoesNotExist:
                    pass

        fixture.save()
        messages.success(request, f'Fixture updated: {fixture}')
        return redirect('cm_competition_manage', pk=pk)

    venues = Venue.objects.filter(is_active=True).order_by('county', 'name')
    from competitions.models import FixtureStatus
    teams = Team.objects.filter(
        status='registered', payment_confirmed=True
    ).order_by('name')

    return render(request, 'portal/cm/edit_fixture.html', {
        'competition': competition,
        'fixture': fixture,
        'venues': venues,
        'teams': teams,
        'status_choices': FixtureStatus.choices,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin')
def cm_competition_rules_view(request, pk):
    """Edit and publish competition rules."""
    competition = get_object_or_404(Competition, pk=pk)

    if request.method == 'POST':
        competition.rules = request.POST.get('rules', '')
        competition.save(update_fields=['rules'])
        messages.success(request, f'Rules updated for {competition.name}.')
        return redirect('cm_competition_manage', pk=pk)

    return render(request, 'portal/cm/edit_rules.html', {
        'competition': competition,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   VERIFICATION OFFICER — COUNTY-BASED VERIFICATION FLOW
# ══════════════════════════════════════════════════════════════════════════════

@role_required('competition_manager', 'chief_sports_officer', 'admin', 'verification_officer')
def vo_registered_counties_view(request):
    """List all registered (approved) counties with stats."""
    counties = CountyRegistration.objects.filter(
        status='approved'
    ).order_by('county')

    county_data = []
    for reg in counties:
        disciplines = reg.disciplines.all()
        total_players = CountyPlayer.objects.filter(discipline__registration=reg).count()
        pending_players = CountyPlayer.objects.filter(
            discipline__registration=reg, verification_status='pending'
        ).count()
        verified_players = CountyPlayer.objects.filter(
            discipline__registration=reg, verification_status='verified'
        ).count()
        county_data.append({
            'registration': reg,
            'discipline_count': disciplines.count(),
            'total_players': total_players,
            'pending_players': pending_players,
            'verified_players': verified_players,
        })

    return render(request, 'portal/verification/registered_counties.html', {
        'county_data': county_data,
        'total_counties': len(county_data),
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin', 'verification_officer')
def vo_county_disciplines_view(request, county_reg_pk):
    """Show disciplines registered under a specific county."""
    reg = get_object_or_404(CountyRegistration, pk=county_reg_pk, status='approved')
    disciplines = reg.disciplines.prefetch_related('players', 'technical_bench').all()

    disc_data = []
    for disc in disciplines:
        players = disc.players.all()
        bench = disc.technical_bench.all()
        disc_data.append({
            'discipline': disc,
            'total_players': players.count(),
            'pending': players.filter(verification_status='pending').count(),
            'verified': players.filter(verification_status='verified').count(),
            'rejected': players.filter(verification_status='rejected').count(),
            'resubmit': players.filter(verification_status='resubmit').count(),
            'bench_count': bench.count(),
        })

    return render(request, 'portal/verification/county_disciplines.html', {
        'reg': reg,
        'disc_data': disc_data,
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin', 'verification_officer')
def vo_discipline_players_view(request, discipline_pk):
    """Show players in a discipline with gender filter, linking to verification."""
    discipline = get_object_or_404(
        CountyDiscipline.objects.select_related('registration'),
        pk=discipline_pk,
    )

    tab = request.GET.get('tab', 'pending')
    player_query = request.GET.get('q', '').strip()

    players = discipline.players.all().order_by('last_name', 'first_name')

    if player_query:
        players = players.filter(
            Q(first_name__icontains=player_query) |
            Q(last_name__icontains=player_query) |
            Q(national_id_number__icontains=player_query)
        )

    pending = players.filter(verification_status='pending')
    verified = players.filter(verification_status='verified')
    rejected = players.filter(verification_status='rejected')
    resubmit = players.filter(verification_status='resubmit')

    return render(request, 'portal/verification/discipline_players.html', {
        'discipline': discipline,
        'reg': discipline.registration,
        'tab': tab,
        'pending_players': pending,
        'verified_players': verified,
        'rejected_players': rejected,
        'resubmit_players': resubmit,
        'player_query': player_query,
        'stats': {
            'pending': pending.count(),
            'verified': verified.count(),
            'rejected': rejected.count(),
            'resubmit': resubmit.count(),
        },
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin', 'verification_officer')
def vo_discipline_delegation_view(request, discipline_pk):
    """View technical bench / delegation for a discipline (separate from players)."""
    discipline = get_object_or_404(
        CountyDiscipline.objects.select_related('registration'),
        pk=discipline_pk,
    )
    bench_members = discipline.technical_bench.all().order_by('role')

    return render(request, 'portal/verification/discipline_delegation.html', {
        'discipline': discipline,
        'reg': discipline.registration,
        'bench_members': bench_members,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   COUNTY PLAYER VERIFICATION (Competition Manager / Organising Secretary)
# ══════════════════════════════════════════════════════════════════════════════

@role_required('competition_manager', 'chief_sports_officer', 'admin', 'verification_officer')
def county_player_verification_list_view(request):
    """CM view: All county players by verification status with filters."""
    tab = request.GET.get('tab', 'pending')
    discipline_filter = request.GET.get('discipline', '')
    county_filter = request.GET.get('county', '')
    huduma_filter = request.GET.get('huduma', '')
    clearance_filter = request.GET.get('clearance', '')
    player_query = request.GET.get('q', '').strip()

    players = CountyPlayer.objects.select_related(
        'discipline', 'discipline__registration',
    ).order_by('-registered_at', 'last_name')

    if discipline_filter:
        players = players.filter(discipline__sport_type=discipline_filter)
    if county_filter:
        players = players.filter(discipline__registration__county=county_filter)
    if huduma_filter:
        players = players.filter(huduma_status=huduma_filter)
    if clearance_filter:
        players = players.filter(higher_league_status=clearance_filter)
    if player_query:
        players = players.filter(
            Q(first_name__icontains=player_query) |
            Q(last_name__icontains=player_query) |
            Q(national_id_number__icontains=player_query)
        )

    pending = players.filter(verification_status='pending')
    verified = players.filter(verification_status='verified')
    rejected = players.filter(verification_status='rejected')
    resubmit = players.filter(verification_status='resubmit')

    # Build discipline filter choices
    disciplines = (
        CountyDiscipline.objects.values_list('sport_type', flat=True)
        .distinct().order_by('sport_type')
    )
    discipline_choices = [(st, dict(SportType.choices).get(st, st)) for st in disciplines]

    # Build county filter choices
    counties = (
        CountyRegistration.objects.values_list('county', flat=True)
        .distinct().order_by('county')
    )
    county_choices = [(c, dict(KenyaCounty.choices).get(c, c)) for c in counties]

    return render(request, 'portal/cm/county_player_verification.html', {
        'tab': tab,
        'pending_players': pending,
        'verified_players': verified,
        'rejected_players': rejected,
        'resubmit_players': resubmit,
        'disciplines': discipline_choices,
        'counties': county_choices,
        'discipline_filter': discipline_filter,
        'county_filter': county_filter,
        'huduma_filter': huduma_filter,
        'clearance_filter': clearance_filter,
        'player_query': player_query,
        'stats': {
            'pending': pending.count(),
            'verified': verified.count(),
            'rejected': rejected.count(),
            'resubmit': resubmit.count(),
        },
    })


@role_required('competition_manager', 'chief_sports_officer', 'admin', 'verification_officer')
def verify_county_player_view(request, player_pk):
    """CM view: Inspect a county player's documents and verify/reject/resubmit."""
    player = get_object_or_404(
        CountyPlayer.objects.select_related('discipline', 'discipline__registration'),
        pk=player_pk,
    )
    is_football = player.discipline.sport_type in ('football_men', 'football_women')
    clearance_check_label = 'FIFA Connect' if is_football else 'Higher League'

    blocking_reasons = []
    if player.age < 18 or player.age > 23:
        blocking_reasons.append('Age must be between 18 and 23.')
    if player.huduma_status != 'verified':
        blocking_reasons.append('Huduma age verification must be marked as Verified.')
    if player.higher_league_status != 'clear':
        blocking_reasons.append(f'{clearance_check_label} check must be marked as Clear.')

    can_verify = len(blocking_reasons) == 0

    if request.method == 'POST':
        action = request.POST.get('action')
        from admin_dashboard.models import ActivityLog

        if action == 'huduma_verify':
            player.huduma_status = 'verified'
            player.huduma_verified_at = timezone.now()
            player.save(update_fields=['huduma_status', 'huduma_verified_at'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'Huduma check marked VERIFIED for county player {player.first_name} {player.last_name} '
                            f'({player.discipline.get_sport_type_display()} - {player.discipline.registration.county})',
                user=request.user,
            )
            messages.success(request, f'Huduma check marked verified for {player.first_name} {player.last_name}.')
            return redirect('verify_county_player', player_pk=player.pk)

        elif action == 'huduma_fail':
            player.huduma_status = 'failed'
            player.huduma_verified_at = None
            player.save(update_fields=['huduma_status', 'huduma_verified_at'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'Huduma check marked FAILED for county player {player.first_name} {player.last_name} '
                            f'({player.discipline.get_sport_type_display()} - {player.discipline.registration.county})',
                user=request.user,
            )
            messages.warning(request, f'Huduma check marked failed for {player.first_name} {player.last_name}.')
            return redirect('verify_county_player', player_pk=player.pk)

        elif action == 'huduma_reset':
            player.huduma_status = 'not_checked'
            player.huduma_verified_at = None
            player.save(update_fields=['huduma_status', 'huduma_verified_at'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'Huduma check reset for county player {player.first_name} {player.last_name} '
                            f'({player.discipline.get_sport_type_display()} - {player.discipline.registration.county})',
                user=request.user,
            )
            messages.info(request, f'Huduma check reset for {player.first_name} {player.last_name}.')
            return redirect('verify_county_player', player_pk=player.pk)

        elif action == 'clearance_clear':
            player.higher_league_status = 'clear'
            player.higher_league_details = ''
            player.save(update_fields=['higher_league_status', 'higher_league_details'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'{clearance_check_label} check marked CLEAR for county player '
                            f'{player.first_name} {player.last_name} '
                            f'({player.discipline.get_sport_type_display()} - {player.discipline.registration.county})',
                user=request.user,
            )
            messages.success(request, f'{clearance_check_label} check marked clear for {player.first_name} {player.last_name}.')
            return redirect('verify_county_player', player_pk=player.pk)

        elif action == 'clearance_flag':
            details = request.POST.get('higher_league_details', '').strip()
            player.higher_league_status = 'flagged'
            player.higher_league_details = details
            player.save(update_fields=['higher_league_status', 'higher_league_details'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'{clearance_check_label} check FLAGGED for county player '
                            f'{player.first_name} {player.last_name} '
                            f'({player.discipline.get_sport_type_display()} - {player.discipline.registration.county}): {details}',
                user=request.user,
            )
            messages.warning(request, f'{clearance_check_label} check flagged for {player.first_name} {player.last_name}.')
            return redirect('verify_county_player', player_pk=player.pk)

        elif action == 'clearance_reset':
            player.higher_league_status = 'not_checked'
            player.higher_league_details = ''
            player.save(update_fields=['higher_league_status', 'higher_league_details'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'{clearance_check_label} check reset for county player '
                            f'{player.first_name} {player.last_name} '
                            f'({player.discipline.get_sport_type_display()} - {player.discipline.registration.county})',
                user=request.user,
            )
            messages.info(request, f'{clearance_check_label} check reset for {player.first_name} {player.last_name}.')
            return redirect('verify_county_player', player_pk=player.pk)

        if action == 'verify':
            # Enforce prerequisite checks before final verification.
            if not can_verify:
                messages.error(request, 'Cannot verify yet: ' + ' '.join(blocking_reasons))
                return redirect('verify_county_player', player_pk=player.pk)

            player.verification_status = 'verified'
            player.rejection_reason = ''
            player.save(update_fields=['verification_status', 'rejection_reason'])
            if hasattr(player.discipline, 'linked_team') and player.discipline.linked_team:
                player.discipline.linked_team.sync_players_from_county_discipline()
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'County player {player.first_name} {player.last_name} verified '
                            f'({player.discipline.get_sport_type_display()} — '
                            f'{player.discipline.registration.county})',
                user=request.user,
            )
            messages.success(request, f'✅ {player.first_name} {player.last_name} has been verified.')

        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '').strip()
            player.verification_status = 'rejected'
            player.rejection_reason = reason
            player.save(update_fields=['verification_status', 'rejection_reason'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'County player {player.first_name} {player.last_name} rejected '
                            f'({player.discipline.get_sport_type_display()} — '
                            f'{player.discipline.registration.county}): {reason}',
                user=request.user,
            )
            messages.warning(request, f'❌ {player.first_name} {player.last_name} has been rejected.')

        elif action == 'resubmit':
            reason = request.POST.get('rejection_reason', '').strip()
            player.verification_status = 'resubmit'
            player.rejection_reason = reason
            player.save(update_fields=['verification_status', 'rejection_reason'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'County player {player.first_name} {player.last_name} sent back for '
                            f'resubmission ({player.discipline.get_sport_type_display()} — '
                            f'{player.discipline.registration.county}): {reason}',
                user=request.user,
            )
            messages.info(request, f'🔄 {player.first_name} {player.last_name} sent back for resubmission.')

        elif action == 'reset':
            player.verification_status = 'pending'
            player.rejection_reason = ''
            player.save(update_fields=['verification_status', 'rejection_reason'])
            ActivityLog.objects.create(
                action='PLAYER_UPDATE',
                description=f'County player {player.first_name} {player.last_name} reset to pending '
                            f'({player.discipline.get_sport_type_display()} — '
                            f'{player.discipline.registration.county})',
                user=request.user,
            )
            messages.info(request, f'🔄 {player.first_name} {player.last_name} reset to pending.')

        return redirect('county_player_verification_list')

    return render(request, 'portal/cm/verify_county_player.html', {
        'player': player,
        'is_football': is_football,
        'clearance_check_label': clearance_check_label,
        'can_verify': can_verify,
        'blocking_reasons': blocking_reasons,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   M-PESA STK PUSH — AJAX ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@require_POST
def mpesa_stk_push_view(request):
    """AJAX endpoint to trigger an M-Pesa STK push payment prompt."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    phone = body.get('phone', '').strip()
    if not re.match(r'^\+254\d{9}$', phone):
        return JsonResponse({'success': False, 'error': 'Invalid phone number. Use +254XXXXXXXXX format.'}, status=400)

    try:
        from teams.mpesa_service import initiate_stk_push
        result = initiate_stk_push(
            phone_number=phone,
            amount=max(1, int(COUNTY_REGISTRATION_FEE_CAP)),
            account_reference=django_settings.MPESA_ACCOUNT_REF,
            description='MKJ SUPA CUP County Registration Fee',
        )
        if result['success']:
            checkout_id = result['data'].get('CheckoutRequestID', '')
            return JsonResponse({'success': True, 'checkout_id': checkout_id})
        else:
            return JsonResponse({'success': False, 'error': str(result.get('data', 'STK push failed.'))})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'Payment service unavailable. Please pay manually.'})


# ══════════════════════════════════════════════════════════════════════════════
#   COUNTY SPORTS DIRECTOR — PUBLIC REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

def county_admin_register_view(request):
    """Public county registration for MKJ SUPA CUP 4th Edition."""
    # Build list of already-taken counties for the template
    taken_counties = list(
        CountyRegistration.objects.values_list('county', flat=True)
    )

    if request.method == 'POST':
        form = CountyAdminRegistrationForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Auto-generate a secure temporary password
            temp_password = ''.join(
                secrets.choice(string.ascii_letters + string.digits)
                for _ in range(12)
            )
            user = User.objects.create_user(
                email=cd['email'],
                password=temp_password,
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                phone=cd['phone'],
                county=cd['county'],
                role=UserRole.COUNTY_SPORTS_DIRECTOR,
            )
            user.must_change_password = True
            user.save(update_fields=['must_change_password'])

            email_sent = True
            try:
                send_credentials_email(user, temp_password, 'County Sports Director')
            except Exception:
                email_sent = False

            # ── Collect payment data from registration form ──
            payment_method = request.POST.get('payment_method', '').strip()
            mpesa_phone = request.POST.get('mpesa_phone', '').strip()
            mpesa_reference = request.POST.get('mpesa_reference', '').strip()
            mpesa_checkout_id = request.POST.get('mpesa_checkout_id', '').strip()
            bank_reference = request.POST.get('bank_reference', '').strip()
            bank_slip = request.FILES.get('bank_slip')
            payment_amount_str = request.POST.get('payment_amount', '').strip()

            reg = CountyRegistration.objects.create(
                user=user,
                county=cd['county'],
                director_name=cd['director_name'],
                director_phone=cd['director_phone'],
                status=CountyRegStatus.APPROVED,
                approved_at=timezone.now(),
                payment_method=payment_method,
                mpesa_phone=mpesa_phone,
                mpesa_reference=mpesa_reference,
                mpesa_checkout_id=mpesa_checkout_id,
                bank_reference=bank_reference,
            )
            if bank_slip:
                reg.bank_slip = bank_slip
            if payment_amount_str:
                try:
                    reg.payment_amount = float(payment_amount_str)
                except (ValueError, TypeError):
                    pass

            reg.save()

            messages.success(request, mark_safe(
                f'<strong>County Registration Successful!</strong><br>'
                f'County: <strong>{cd["county"]}</strong><br>'
                f'Director of Sports: <strong>{cd["director_name"]}</strong><br><br>'
                f'Your temporary password has been sent to <code>{cd["email"]}</code>.<br>'
                f'Check your inbox and spam folder, then change the password on first login.<br><br>'
                f'<strong>Next steps:</strong><br>'
                f'1. Log in to the portal with your email and the temporary password from email<br>'
                     f'2. Change your password when prompted<br>'
                     f'3. Your registration is active immediately — add disciplines, players, and technical bench members'
            ))
            if not email_sent:
                messages.warning(
                    request,
                    'Registration is saved, but we could not deliver the credentials email right now. Please contact MKJ SUPA CUP support to resend credentials.'
                )
            return redirect('county_admin_register_success')
    else:
        form = CountyAdminRegistrationForm()

    return render(request, 'public/county_admin_register.html', {
        'form': form,
        'taken_counties': taken_counties,
        'active_page': 'register',
        'registration_fee': COUNTY_REGISTRATION_FEE_CAP,
        'bank_name': django_settings.MKJ_BANK_NAME,
        'bank_branch': django_settings.MKJ_BANK_BRANCH,
        'bank_account_name': django_settings.MKJ_BANK_ACCOUNT_NAME,
        'bank_account_no': django_settings.MKJ_BANK_ACCOUNT_NO,
        'mpesa_paybill': django_settings.MKJ_MPESA_PAYBILL,
        'mpesa_account_no': django_settings.MKJ_MPESA_ACCOUNT_NO,
    })


def county_admin_register_success_view(request):
    return render(request, 'public/county_admin_register_success.html', {
        'active_page': 'register',
    })


@role_required('admin', 'competition_manager', 'chief_sports_officer', 'secretary_general', 'coordinator', 'verification_officer', 'cec_sports')
def cec_sports_portal_view(request):
    """CEC sports caucus portal (view-only): high-level competition and verification visibility."""
    competitions = Competition.objects.order_by('-created_at')[:12]
    counties_registered = CountyRegistration.objects.filter(status='approved').count()
    pending_players = CountyPlayer.objects.filter(verification_status='pending').count()
    verified_players = CountyPlayer.objects.filter(verification_status='verified').count()

    return render(request, 'portal/cec_sports_dashboard.html', {
        'competitions': competitions,
        'counties_registered': counties_registered,
        'pending_players': pending_players,
        'verified_players': verified_players,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   COUNTY SPORTS ADMIN — PORTAL DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@role_required('county_sports_admin')
def county_admin_dashboard_view(request):
    """County admin home — registration status, payment, disciplines, players."""
    reg = get_object_or_404(CountyRegistration, user=request.user)
    disciplines = reg.disciplines.all()
    player_count = sum(d.player_count for d in disciplines)
    delegation_members = reg.delegation_members.all().order_by('role', 'full_name')
    delegation_count = delegation_members.count()
    cecm_member = delegation_members.filter(role=CountyDelegationRole.CECM_SPORTS).first()

    return render(request, 'portal/county_admin/dashboard.html', {
        'reg': reg,
        'disciplines': disciplines,
        'player_count': player_count,
        'delegation_count': delegation_count,
        'cecm_member': cecm_member,
        'registration_fee': COUNTY_REGISTRATION_FEE_CAP,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   COUNTY SPORTS ADMIN — PAYMENT SUBMISSION
# ══════════════════════════════════════════════════════════════════════════════

@role_required('county_sports_admin')
def county_admin_payment_view(request):
    """County admin submits payment proof (M-Pesa or bank slip)."""
    reg = get_object_or_404(CountyRegistration, user=request.user)
    reg.status = CountyRegStatus.APPROVED
    if not reg.approved_at:
        reg.approved_at = timezone.now()
    reg.save(update_fields=['status', 'approved_at'])
    messages.info(request, 'MKJ SUPA CUP does not charge a registration fee. Your registration remains active.')
    return redirect('county_admin_dashboard')


# ══════════════════════════════════════════════════════════════════════════════
#   COUNTY SPORTS ADMIN — DISCIPLINE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@role_required('county_sports_admin', 'subcounty_sports_officer')
def county_admin_add_discipline_view(request):
    """County admin chooses which disciplines to participate in."""
    reg = _get_primary_registration_for_user(request.user, auto_create=request.user.role == UserRole.SUBCOUNTY_SPORTS_OFFICER)
    if not reg:
        messages.error(request, 'Assign a county before adding disciplines.')
        return redirect('dashboard')

    sub_county = request.user.sub_county if request.user.role == UserRole.SUBCOUNTY_SPORTS_OFFICER else ''

    if not reg.is_approved:
        messages.warning(request, 'You must be approved before adding disciplines.')
        return redirect('county_admin_dashboard')

    existing = set(reg.disciplines.filter(sub_county=sub_county).values_list('sport_type', flat=True))
    available = [(k, v) for k, v in SQUAD_LIMITS.items() if k not in existing]

    if request.method == 'POST':
        sport = request.POST.get('sport_type', '')
        if sport in dict(SQUAD_LIMITS) and sport not in existing:
            CountyDiscipline.objects.create(registration=reg, sport_type=sport, sub_county=sub_county)
            messages.success(request, f'{dict(SportType.choices).get(sport, sport)} added.')
        else:
            messages.error(request, 'Invalid discipline or already added.')
        if request.user.role == UserRole.SUBCOUNTY_SPORTS_OFFICER:
            return redirect('subcounty_officer_disciplines')
        return redirect('county_admin_dashboard')

    return render(request, 'portal/county_admin/add_discipline.html', {
        'reg': reg,
        'available': [(k, dict(SportType.choices).get(k, k), v) for k, v in available],
    })


# ══════════════════════════════════════════════════════════════════════════════
#   COUNTY SPORTS ADMIN — PLAYER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@role_required('county_sports_admin')
def county_admin_discipline_players_view(request, discipline_pk):
    """View players in a discipline and add new ones."""
    reg = get_object_or_404(CountyRegistration, user=request.user)
    discipline = get_object_or_404(CountyDiscipline, pk=discipline_pk, registration=reg)
    players = discipline.players.all()

    return render(request, 'portal/county_admin/discipline_players.html', {
        'reg': reg,
        'discipline': discipline,
        'players': players,
    })


@role_required('county_sports_admin')
def county_admin_add_player_view(request, discipline_pk):
    """Add a player to a discipline."""
    reg = get_object_or_404(CountyRegistration, user=request.user)
    discipline = get_object_or_404(CountyDiscipline, pk=discipline_pk, registration=reg)

    if not reg.is_approved:
        messages.warning(request, 'Registration must be approved before adding players.')
        return redirect('county_admin_dashboard')

    if not discipline.can_add_player:
        messages.error(
            request,
            f'Squad limit reached ({discipline.squad_limit}) for '
            f'{discipline.get_sport_type_display()}.'
        )
        return redirect('county_admin_discipline_players', discipline_pk=discipline_pk)

    if request.method == 'POST':
        form = CountyPlayerForm(request.POST, request.FILES)
        if form.is_valid():
            player = form.save(commit=False)
            player.discipline = discipline
            player.save()
            messages.success(
                request,
                f'{player.first_name} {player.last_name} registered '
                f'({discipline.player_count}/{discipline.squad_limit}).'
            )
            return redirect('county_admin_discipline_players', discipline_pk=discipline_pk)
    else:
        form = CountyPlayerForm()

    return render(request, 'portal/county_admin/add_player.html', {
        'form': form,
        'discipline': discipline,
        'reg': reg,
    })


@role_required('county_sports_admin')
def county_admin_delete_player_view(request, player_pk):
    """Remove a player from a discipline."""
    reg = get_object_or_404(CountyRegistration, user=request.user)
    player = get_object_or_404(CountyPlayer, pk=player_pk, discipline__registration=reg)
    discipline_pk = player.discipline.pk

    if request.method == 'POST':
        name = f'{player.first_name} {player.last_name}'
        player.delete()
        messages.success(request, f'{name} removed.')
    return redirect('county_admin_discipline_players', discipline_pk=discipline_pk)


# ══════════════════════════════════════════════════════════════════════════════
#   TREASURER — COUNTY REGISTRATION APPROVALS
# ══════════════════════════════════════════════════════════════════════════════

@role_required('treasurer', 'admin', 'competition_manager', 'chief_sports_officer')
def treasurer_county_registrations_view(request):
    """Treasurer reviews county admin registrations and approves/rejects."""
    if request.method == 'POST':
        reg_id = request.POST.get('registration_id')
        action = request.POST.get('action')
        reg = get_object_or_404(CountyRegistration, pk=reg_id)

        if action == 'approve':
            reg.status = CountyRegStatus.APPROVED
            reg.approved_by = request.user
            reg.approved_at = timezone.now()
            reg.save()
            # Notify county admin by email
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject='[MKJ SUPA CUP] County Registration Approved',
                    message=(
                        f'Dear {reg.user.get_full_name()},\n\n'
                        f'Your county registration for {reg.county} has been approved.\n'
                        f'You can now log in to the MKJ SUPA CUP portal and begin adding disciplines and players.\n\n'
                        f'MKJ SUPA CUP Administration'
                    ),
                    from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@mkjsupacup.go.ke'),
                    recipient_list=[reg.user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, f'{reg.county} county registration approved.')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            reg.status = CountyRegStatus.REJECTED
            reg.rejection_reason = reason
            reg.save()
            messages.warning(request, f'{reg.county} county registration rejected.')

        return redirect('treasurer_county_registrations')

    pending = CountyRegistration.objects.filter(
        status=CountyRegStatus.PAYMENT_SUBMITTED
    ).order_by('-payment_submitted_at')
    approved = CountyRegistration.objects.filter(
        status=CountyRegStatus.APPROVED
    ).order_by('-approved_at')
    all_regs = CountyRegistration.objects.all().order_by('-created_at')

    return render(request, 'portal/treasurer/county_registrations.html', {
        'pending': pending,
        'approved': approved,
        'all_regs': all_regs,
        'registration_fee': COUNTY_REGISTRATION_FEE_CAP,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   COUNTY SPORTS DIRECTOR — TECHNICAL BENCH MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@role_required('county_sports_admin', 'subcounty_sports_officer')
def county_admin_add_bench_member_view(request, discipline_pk):
    """County sports director adds a technical bench member to a discipline."""
    reg = _get_primary_registration_for_user(request.user, auto_create=request.user.role == UserRole.SUBCOUNTY_SPORTS_OFFICER)
    if not reg:
        messages.error(request, 'Assign a county before managing technical bench members.')
        return redirect('dashboard')
    discipline = _get_managed_discipline(request.user, discipline_pk)

    if not reg.is_approved:
        messages.warning(request, 'Registration must be approved first.')
        return redirect('county_admin_dashboard')

    if request.method == 'POST':
        form = TechnicalBenchForm(request.POST, request.FILES)
        if form.is_valid():
            member = form.save(commit=False)
            member.discipline = discipline

            # Check if role is already filled
            if TechnicalBenchMember.objects.filter(discipline=discipline, role=member.role).exists():
                messages.error(request, f'{member.get_role_display()} is already assigned for this discipline.')
            else:
                member.save()

                # Team Manager must always be wired to a Team Manager account.
                if member.role == TechnicalBenchRole.TEAM_MANAGER:
                    existing_user = User.objects.filter(email__iexact=member.email).first()

                    if existing_user and existing_user.technical_bench_profile:
                        messages.error(request, 'This Team Manager email is already linked to another technical bench profile.')
                        member.delete()
                        return redirect('county_admin_discipline_players', discipline_pk=discipline_pk)

                    if existing_user and existing_user.role == UserRole.TEAM_MANAGER:
                        # Reuse existing Team Manager account and align profile details.
                        tm_user = existing_user
                        tm_user.first_name = member.first_name
                        tm_user.last_name = member.last_name
                        tm_user.phone = member.phone
                        tm_user.county = reg.county
                        tm_user.sub_county = discipline.sub_county
                        tm_user.is_active = True
                        tm_user.save(update_fields=['first_name', 'last_name', 'phone', 'county', 'sub_county', 'is_active'])
                        member.user = tm_user
                        member.save(update_fields=['user'])
                        if hasattr(discipline, 'linked_team'):
                            discipline.linked_team.manager = tm_user
                            discipline.linked_team.save(update_fields=['manager'])
                        messages.success(request, f'{member.get_full_name} added as {member.get_role_display()}. Existing Team Manager account linked.')
                    else:
                        try:
                            temp_pw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                            tm_user = User.objects.create_user(
                                email=member.email,
                                password=temp_pw,
                                first_name=member.first_name,
                                last_name=member.last_name,
                                phone=member.phone,
                                county=reg.county,
                                sub_county=discipline.sub_county,
                                role=UserRole.TEAM_MANAGER,
                                must_change_password=True,
                            )
                            member.user = tm_user
                            member.save(update_fields=['user'])
                            if hasattr(discipline, 'linked_team'):
                                discipline.linked_team.manager = tm_user
                                discipline.linked_team.save(update_fields=['manager'])
                            try:
                                send_credentials_email(tm_user, temp_pw, 'Team Manager')
                                messages.success(request, f'{member.get_full_name} added as {member.get_role_display()}. Login credentials sent to {member.email}.')
                            except Exception:
                                messages.success(request, f'{member.get_full_name} added as {member.get_role_display()} but credential email failed.')
                        except Exception as e:
                            member.delete()
                            messages.error(request, f'Team Manager account creation failed: {e}')
                            return redirect('county_admin_discipline_players', discipline_pk=discipline_pk)
                else:
                    messages.success(request, f'{member.get_full_name} added as {member.get_role_display()}.')

            if request.user.role == UserRole.SUBCOUNTY_SPORTS_OFFICER:
                return redirect('subcounty_officer_discipline_players', discipline_pk=discipline_pk)
            return redirect('county_admin_discipline_players', discipline_pk=discipline_pk)
    else:
        form = TechnicalBenchForm()

    existing_bench = discipline.technical_bench.all()
    filled_roles = set(existing_bench.values_list('role', flat=True))
    available_roles = [(k, v) for k, v in TechnicalBenchRole.choices if k not in filled_roles]

    return render(request, 'portal/county_admin/add_bench_member.html', {
        'form': form,
        'discipline': discipline,
        'reg': reg,
        'existing_bench': existing_bench,
        'available_roles': available_roles,
    })


@role_required('county_sports_admin', 'subcounty_sports_officer')
def county_admin_delete_bench_member_view(request, member_pk):
    """Remove a technical bench member."""
    reg = _get_primary_registration_for_user(request.user, auto_create=request.user.role == UserRole.SUBCOUNTY_SPORTS_OFFICER)
    if not reg:
        messages.error(request, 'Assign a county before managing technical bench members.')
        return redirect('dashboard')
    member = get_object_or_404(TechnicalBenchMember, pk=member_pk, discipline__in=_discipline_queryset_for_user(request.user))
    discipline_pk = member.discipline.pk

    if request.method == 'POST':
        name = member.get_full_name
        member.delete()
        messages.success(request, f'{name} removed from technical bench.')
    if request.user.role == UserRole.SUBCOUNTY_SPORTS_OFFICER:
        return redirect('subcounty_officer_discipline_players', discipline_pk=discipline_pk)
    return redirect('county_admin_discipline_players', discipline_pk=discipline_pk)


@role_required('county_sports_admin')
def county_admin_delegation_members_view(request):
    """County sports director manages county-level delegation officials."""
    reg = get_object_or_404(CountyRegistration, user=request.user)

    if not reg.is_approved:
        messages.warning(request, 'Registration must be approved before adding delegation members.')
        return redirect('county_admin_dashboard')

    members = reg.delegation_members.select_related('user').order_by('role', 'full_name')

    if request.method == 'POST':
        form = CountyDelegationMemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.registration = reg

            if (
                member.role == CountyDelegationRole.CECM_SPORTS and
                CountyDelegationMember.objects.filter(
                    registration=reg,
                    role=CountyDelegationRole.CECM_SPORTS,
                ).exists()
            ):
                messages.error(request, 'A CECM Sports member has already been added for this county.')
            elif member.role == CountyDelegationRole.CECM_SPORTS and User.objects.filter(email__iexact=member.email).exists():
                messages.error(request, 'A user account with this email already exists. Use a different email for CECM account creation.')
            else:
                member.save()

                if member.role == CountyDelegationRole.CECM_SPORTS:
                    temp_pw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                    name_parts = member.full_name.strip().split()
                    first_name = name_parts[0] if name_parts else 'CECM'
                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else 'Sports'

                    cec_user = User.objects.create_user(
                        email=member.email,
                        password=temp_pw,
                        first_name=first_name,
                        last_name=last_name,
                        phone=member.phone,
                        county=reg.county,
                        role=UserRole.CEC_SPORTS_MEMBER,
                        must_change_password=True,
                    )
                    member.user = cec_user
                    member.save(update_fields=['user'])

                    try:
                        send_credentials_email(cec_user, temp_pw, 'County Executive Committee Member for Sports (CECM)')
                        messages.success(request, f'{member.full_name} added as CECM Sports and login credentials sent.')
                    except Exception:
                        messages.success(request, f'{member.full_name} added as CECM Sports. Account created but credential email failed.')
                else:
                    messages.success(request, f'{member.full_name} added as {member.get_role_display()}.')

            return redirect('county_admin_delegation_members')
    else:
        form = CountyDelegationMemberForm()

    return render(request, 'portal/county_admin/delegation_members.html', {
        'reg': reg,
        'form': form,
        'members': members,
        'cecm_exists': members.filter(role=CountyDelegationRole.CECM_SPORTS).exists(),
    })


@role_required('county_sports_admin')
def county_admin_delete_delegation_member_view(request, member_pk):
    """Remove a county-level delegation member and linked account if present."""
    reg = get_object_or_404(CountyRegistration, user=request.user)
    member = get_object_or_404(CountyDelegationMember, pk=member_pk, registration=reg)

    if request.method == 'POST':
        name = member.full_name
        linked_user = member.user
        member.delete()
        if linked_user:
            linked_user.delete()
        messages.success(request, f'{name} removed from county delegation.')

    return redirect('county_admin_delegation_members')


# ══════════════════════════════════════════════════════════════════════════════
#   COUNTY SPORTS DIRECTOR — PLAYER VERIFICATION OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

@role_required('county_sports_admin')
def county_admin_verification_view(request):
    """County sports director views verification status of all their players."""
    reg = get_object_or_404(CountyRegistration, user=request.user)
    disciplines = reg.disciplines.prefetch_related('players').all()

    approved_players = []
    rejected_players = []
    resubmit_players = []
    pending_players = []

    for disc in disciplines:
        for player in disc.players.all():
            entry = {'player': player, 'discipline': disc}
            if player.verification_status == 'verified':
                approved_players.append(entry)
            elif player.verification_status == 'rejected':
                rejected_players.append(entry)
            elif player.verification_status == 'resubmit':
                resubmit_players.append(entry)
            else:
                pending_players.append(entry)

    return render(request, 'portal/county_admin/verification_status.html', {
        'reg': reg,
        'approved_players': approved_players,
        'rejected_players': rejected_players,
        'resubmit_players': resubmit_players,
        'pending_players': pending_players,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   PLAYER PROFILE VIEW (public within portal)
# ══════════════════════════════════════════════════════════════════════════════

@login_required(login_url='web_login')
def player_profile_view(request, player_pk):
    """
    Player profile view showing full details, verification status,
    discipline(s), and passport photo. Accessible to authorized roles.
    """
    # Try CountyPlayer first, then Player (team-based)
    player = None
    player_type = None
    try:
        player = CountyPlayer.objects.select_related('discipline__registration').get(pk=player_pk)
        player_type = 'county'
    except CountyPlayer.DoesNotExist:
        pass

    if not player:
        player = get_object_or_404(Player.objects.select_related('team'), pk=player_pk)
        player_type = 'team'

    # Access control
    user = request.user
    can_view = (
        user.is_superuser or
        user.role in ('admin', 'competition_manager', 'referee', 'coordinator', 'jury_chair', 'cec_sports')
    )
    if player_type == 'county':
        # County sports director can view their own county's players
        if user.role == 'county_sports_admin':
            try:
                reg = CountyRegistration.objects.get(user=user)
                if player.discipline.registration == reg:
                    can_view = True
            except CountyRegistration.DoesNotExist:
                pass
        # Team manager can view verified players in their county
        if user.role == 'team_manager':
            try:
                bench = TechnicalBenchMember.objects.get(user=user)
                if bench.discipline.registration == player.discipline.registration:
                    can_view = True
            except TechnicalBenchMember.DoesNotExist:
                pass
    elif player_type == 'team':
        if user.role == 'team_manager' and player.team.manager == user:
            can_view = True

    if not can_view:
        messages.error(request, 'You do not have permission to view this player profile.')
        return redirect('dashboard')

    return render(request, 'portal/player_profile.html', {
        'player': player,
        'player_type': player_type,
    })


@login_required(login_url='web_login')
def county_player_profile_view(request, player_pk):
    """County player profile view — redirect to the unified player profile."""
    return player_profile_view(request, player_pk)


# ══════════════════════════════════════════════════════════════════════════════
#   TEAM MANAGER PORTAL (dedicated portal for match management)
# ══════════════════════════════════════════════════════════════════════════════

@role_required('team_manager')
def team_manager_dashboard_view(request):
    """
    Team Manager dedicated dashboard showing:
    - Verified players (organized per discipline)
    - Upcoming matches
    - Disciplinary sanctions for own + opponent teams
    """
    user = request.user

    # Find the technical bench member linked to this user
    try:
        bench = TechnicalBenchMember.objects.select_related(
            'discipline__registration'
        ).get(user=user, role=TechnicalBenchRole.TEAM_MANAGER)
    except TechnicalBenchMember.DoesNotExist:
        bench = None

    # Fall back to old Team-based manager role
    my_teams = Team.objects.filter(manager=user)

    # Verified county players (if bench member)
    verified_players = []
    discipline = None
    county_reg = None
    if bench:
        discipline = bench.discipline
        county_reg = discipline.registration
        if hasattr(discipline, 'linked_team') and discipline.linked_team:
            discipline.linked_team.sync_players_from_county_discipline()
        verified_players = CountyPlayer.objects.filter(
            discipline=discipline,
            verification_status='verified',
        ).order_by('last_name', 'first_name')

    # Verified team players (old flow)
    team_players = {}
    for team in my_teams:
        team_players[team] = Player.objects.filter(
            team=team,
            verification_status=VerificationStatus.VERIFIED,
            huduma_status='verified',
            fifa_connect_status='clear',
        ).order_by('shirt_number')

    # Upcoming fixtures
    upcoming_fixtures = []
    fixture_action_rows = []
    if my_teams.exists():
        upcoming_fixtures = Fixture.objects.filter(
            Q(home_team__in=my_teams) | Q(away_team__in=my_teams),
            match_date__gte=timezone.now(),
        ).select_related(
            'competition', 'home_team', 'away_team', 'venue'
        ).order_by('match_date')[:10]

        now = timezone.now()
        for f in upcoming_fixtures:
            if f.home_team in my_teams:
                my_team = f.home_team
                opponent_team = f.away_team
            else:
                my_team = f.away_team
                opponent_team = f.home_team

            kickoff_dt = f.kickoff_datetime
            if timezone.is_naive(kickoff_dt):
                kickoff_dt = timezone.make_aware(kickoff_dt, timezone.get_current_timezone())
            selection_opens_at = kickoff_dt - timedelta(hours=2)

            match_locked = f.status in ('live', 'completed') or now >= kickoff_dt
            selection_window_open = (now >= selection_opens_at) and not match_locked

            my_squad = SquadSubmission.objects.filter(fixture=f, team=my_team).first()
            opp_squad = SquadSubmission.objects.filter(fixture=f, team=opponent_team).first()
            both_approved = (
                my_squad and my_squad.status == SquadStatus.APPROVED and
                opp_squad and opp_squad.status == SquadStatus.APPROVED
            )

            fixture_action_rows.append({
                'fixture': f,
                'selection_opens_at': selection_opens_at,
                'match_locked': match_locked,
                'selection_window_open': selection_window_open,
                'both_squads_approved': both_approved,
                'my_squad': my_squad,
                'opp_squad': opp_squad,
            })

    # Disciplinary sanctions
    from matches.models import PlayerStatistics
    own_sanctions = []
    opponent_sanctions = []
    if my_teams.exists():
        own_sanctions = PlayerStatistics.objects.filter(
            team__in=my_teams,
        ).filter(
            Q(yellow_cards__gt=0) | Q(red_cards__gt=0)
        ).select_related('player', 'team', 'competition').order_by('-red_cards', '-yellow_cards')[:20]

    return render(request, 'portal/team_manager/dashboard.html', {
        'bench': bench,
        'discipline': discipline,
        'county_reg': county_reg,
        'verified_players': verified_players,
        'my_teams': my_teams,
        'team_players': team_players,
        'upcoming_fixtures': upcoming_fixtures,
        'fixture_action_rows': fixture_action_rows,
        'own_sanctions': own_sanctions,
    })


@role_required('team_manager')
def team_manager_match_squad_view(request, fixture_pk):
    """
    Team Manager selects match day squad (starters + subs).
    - Sport-specific starter count (11 for football, 6 volleyball, etc.)
    - Formation selection for football
    - Only verified players can be selected
    - Suspended players are blocked
    - Cannot edit after match start
    - Post-referee-approval edits require re-approval
    """
    from django.conf import settings as conf
    from matches.models import get_starters_for_sport

    fixture = get_object_or_404(Fixture.objects.select_related(
        'home_team', 'away_team', 'competition', 'venue'
    ), pk=fixture_pk)
    user = request.user
    now = timezone.now()

    # Determine the manager's team
    my_teams = Team.objects.filter(manager=user)
    team = None
    if fixture.home_team in my_teams:
        team = fixture.home_team
    elif fixture.away_team in my_teams:
        team = fixture.away_team

    if not team:
        messages.error(request, 'Your team is not involved in this fixture.')
        return redirect('team_manager_dashboard')

    if team.source_discipline_id:
        team.sync_players_from_county_discipline()

    # Lock once match has started/completed OR kickoff time has passed.
    kickoff_dt = fixture.kickoff_datetime
    if timezone.is_naive(kickoff_dt):
        kickoff_dt = timezone.make_aware(kickoff_dt, timezone.get_current_timezone())

    if fixture.status in ('live', 'completed') or now >= kickoff_dt:
        messages.error(request, 'Cannot edit squad — match has already started or completed.')
        return redirect('team_manager_dashboard')

    # Squad selection window opens 2 hours before kickoff.
    selection_opens_at = kickoff_dt - timedelta(hours=2)
    if now < selection_opens_at:
        messages.warning(
            request,
            f'Squad selection opens 2 hours before kickoff at {selection_opens_at.strftime("%d %b %Y %H:%M")}.',
        )
        return redirect('team_manager_dashboard')

    # Sport-specific starter count
    sport_type = fixture.competition.sport_type if fixture.competition else ''
    required_starters = get_starters_for_sport(sport_type)
    is_football = sport_type in ('football_men', 'football_women')

    # Get existing submission
    existing = SquadSubmission.objects.filter(fixture=fixture, team=team).first()

    # If squad already approved by referee, warn that changes need re-approval
    needs_re_approval = existing and existing.status == SquadStatus.APPROVED

    # Get fully verified players only — suspended ones flagged
    eligible_players = Player.objects.filter(
        team=team,
        verification_status=VerificationStatus.VERIFIED,
        huduma_status='verified',
        fifa_connect_status='clear',
    ).exclude(
        status=PlayerStatus.SUSPENDED,
    ).order_by('shirt_number')

    suspended_ids = set(
        Player.objects.filter(
            team=team, status=PlayerStatus.SUSPENDED
        ).values_list('pk', flat=True)
    )
    eligible_ids = set(eligible_players.values_list('pk', flat=True))

    starter_ids = []
    sub_ids = []
    current_formation = ''
    if existing:
        starter_ids = list(existing.squad_players.filter(is_starter=True).values_list('player_id', flat=True))
        sub_ids = list(existing.squad_players.filter(is_starter=False).values_list('player_id', flat=True))
        current_formation = existing.formation or ''

    if request.method == 'POST':
        selected_starters = request.POST.getlist('starters')
        selected_subs = request.POST.getlist('subs')
        chosen_formation = request.POST.get('formation', '').strip()

        starters_int = [int(x) for x in selected_starters if x]
        subs_int = [int(x) for x in selected_subs if x]

        # Validate no suspended players
        selected_suspended = (set(starters_int) | set(subs_int)) & suspended_ids
        selected_ids = set(starters_int) | set(subs_int)
        invalid_ids = selected_ids - eligible_ids

        if invalid_ids:
            messages.error(request, 'You can only select from available eligible players.')
        elif selected_suspended:
            messages.error(request, 'Cannot select suspended players.')
        elif set(starters_int) & set(subs_int):
            messages.error(request, 'A player cannot be both a starter and a substitute.')
        elif len(starters_int) != required_starters:
            messages.error(request, f'Exactly {required_starters} starters required. You selected {len(starters_int)}.')
        elif is_football and not Player.objects.filter(pk__in=starters_int, team=team, position='GK').exists():
            messages.error(request, 'Football starting lineup must include at least one goalkeeper (GK).')
        elif is_football and (len(selected_ids) < 7 or len(selected_ids) > 25):
            messages.error(request, f'Football matchday squad must have between 7 and 25 players. You selected {len(selected_ids)}.')
        else:
            if existing:
                existing.squad_players.all().delete()
                submission = existing
            else:
                submission = SquadSubmission.objects.create(fixture=fixture, team=team)

            # If was previously approved and now re-submitted, needs re-approval
            submission.status = SquadStatus.SUBMITTED
            submission.submitted_at = timezone.now()
            submission.rejection_reason = ''
            submission.reviewed_by = None
            submission.reviewed_at = None
            if is_football and chosen_formation:
                submission.formation = chosen_formation
            submission.save()

            for pid in starters_int:
                p = Player.objects.get(pk=pid, team=team)
                SquadPlayer.objects.create(submission=submission, player=p, is_starter=True, shirt_number=p.shirt_number)
            for pid in subs_int:
                p = Player.objects.get(pk=pid, team=team)
                SquadPlayer.objects.create(submission=submission, player=p, is_starter=False, shirt_number=p.shirt_number)

            messages.success(request, f'Squad submitted for {fixture}.')
            return redirect('team_manager_dashboard')

    return render(request, 'portal/team_manager/match_squad.html', {
        'fixture': fixture,
        'team': team,
        'eligible_players': eligible_players,
        'suspended_ids': suspended_ids,
        'existing': existing,
        'starter_ids': starter_ids,
        'sub_ids': sub_ids,
        'needs_re_approval': needs_re_approval,
        'required_starters': required_starters,
        'is_football': is_football,
        'selection_opens_at': selection_opens_at,
        'formations': SquadSubmission.FOOTBALL_FORMATIONS,
        'current_formation': current_formation,
    })


@role_required('team_manager')
def team_manager_opponent_view(request, fixture_pk):
    """
    View opponent team list — ONLY after referee has approved both squads.
    """
    fixture = get_object_or_404(Fixture.objects.select_related(
        'home_team', 'away_team', 'competition'
    ), pk=fixture_pk)
    user = request.user

    my_teams = Team.objects.filter(manager=user)
    if fixture.home_team in my_teams:
        my_team = fixture.home_team
        opponent = fixture.away_team
    elif fixture.away_team in my_teams:
        my_team = fixture.away_team
        opponent = fixture.home_team
    else:
        messages.error(request, 'Your team is not involved in this fixture.')
        return redirect('team_manager_dashboard')

    # Check both squads are approved
    my_squad = SquadSubmission.objects.filter(fixture=fixture, team=my_team).first()
    opp_squad = SquadSubmission.objects.filter(fixture=fixture, team=opponent).first()

    both_approved = (
        my_squad and my_squad.status == SquadStatus.APPROVED and
        opp_squad and opp_squad.status == SquadStatus.APPROVED
    )

    if not both_approved:
        messages.warning(request, 'Opponent team list is only visible after referee approves both squads.')
        return redirect('team_manager_dashboard')

    # Only starters are visible for confirmation and potential appeals.
    opp_players = opp_squad.squad_players.select_related('player').filter(is_starter=True).order_by('shirt_number')

    return render(request, 'portal/team_manager/opponent_view.html', {
        'fixture': fixture,
        'my_team': my_team,
        'opponent': opponent,
        'opp_players': opp_players,
    })


@role_required('team_manager')
def team_manager_sanctions_view(request):
    """View disciplinary sanctions for own team and opponents."""
    user = request.user
    my_teams = Team.objects.filter(manager=user)
    from matches.models import PlayerStatistics

    own_sanctions = PlayerStatistics.objects.filter(
        team__in=my_teams,
    ).filter(
        Q(yellow_cards__gt=0) | Q(red_cards__gt=0)
    ).select_related('player', 'team', 'competition').order_by('-red_cards', '-yellow_cards')

    # Opponent sanctions: get from recent fixtures
    opponent_team_ids = set()
    recent_fixtures = Fixture.objects.filter(
        Q(home_team__in=my_teams) | Q(away_team__in=my_teams),
    ).select_related('home_team', 'away_team')[:20]

    for f in recent_fixtures:
        if f.home_team in my_teams:
            opponent_team_ids.add(f.away_team_id)
        else:
            opponent_team_ids.add(f.home_team_id)

    opponent_sanctions = PlayerStatistics.objects.filter(
        team_id__in=opponent_team_ids,
    ).filter(
        Q(yellow_cards__gt=0) | Q(red_cards__gt=0)
    ).select_related('player', 'team', 'competition').order_by('-red_cards', '-yellow_cards')[:30]

    return render(request, 'portal/team_manager/sanctions.html', {
        'own_sanctions': own_sanctions,
        'opponent_sanctions': opponent_sanctions,
        'my_teams': my_teams,
    })


@role_required('team_manager')
def team_manager_file_appeal_view(request):
    """
    Team Manager files a disciplinary appeal.
    Appeals must be reviewed and approved by the County Sports Director before proceeding.
    """
    from appeals.forms import AppealForm
    user = request.user
    my_teams = Team.objects.filter(manager=user)

    if not my_teams.exists():
        messages.error(request, 'No team found for your account.')
        return redirect('team_manager_dashboard')

    team = my_teams.first()

    if request.method == 'POST':
        form = AppealForm(request.POST)
        if form.is_valid():
            from appeals.models import Appeal, AppealStatus
            respondent_team_id = request.POST.get('respondent_team')
            if not respondent_team_id:
                messages.error(request, 'Please select a respondent team.')
            else:
                appeal = Appeal(
                    appellant_team=team,
                    appellant_user=user,
                    respondent_team_id=int(respondent_team_id),
                    subject=form.cleaned_data['subject'],
                    details=form.cleaned_data['details'],
                    status=AppealStatus.DRAFT,
                )
                match_id = request.POST.get('match')
                if match_id:
                    appeal.match_id = int(match_id)
                appeal.save()
                messages.success(request, 'Appeal drafted. It will be reviewed by your County Sports Director before submission.')
                return redirect('team_manager_dashboard')
    else:
        form = AppealForm()

    # Get possible opponent teams
    other_teams = Team.objects.exclude(pk__in=my_teams).filter(status='registered').order_by('name')

    return render(request, 'portal/team_manager/file_appeal.html', {
        'form': form,
        'team': team,
        'other_teams': other_teams,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   TEAM LIST — DOWNLOADABLE PDF
# ══════════════════════════════════════════════════════════════════════════════

@login_required(login_url='web_login')
def team_list_pdf_view(request, discipline_pk):
    """
    Generate and return a downloadable PDF of the team list.
    Includes MKJ SUPA CUP logo, player photos, name, DOB, position, jersey.
    Accessible to Team Manager, County Sports Director, admin, CM.
    """
    from django.http import HttpResponse
    from io import BytesIO

    discipline = get_object_or_404(
        CountyDiscipline.objects.select_related('registration'),
        pk=discipline_pk,
    )

    # Permission check
    user = request.user
    can_download = (
        user.is_superuser or
        user.role in ('admin', 'competition_manager')
    )
    if user.role == 'county_sports_admin':
        try:
            reg = CountyRegistration.objects.get(user=user)
            if discipline.registration == reg:
                can_download = True
        except CountyRegistration.DoesNotExist:
            pass
    if user.role == 'team_manager':
        try:
            bench = TechnicalBenchMember.objects.get(user=user)
            if bench.discipline == discipline:
                can_download = True
        except TechnicalBenchMember.DoesNotExist:
            pass

    if not can_download:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    players = discipline.players.filter(verification_status='verified').order_by('jersey_number', 'last_name')
    bench_members = discipline.technical_bench.all().order_by('role')

    # Generate PDF using reportlab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            Image as RLImage,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm, mm
        import os

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
            leftMargin=1.5*cm, rightMargin=1.5*cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        # ── MKJ SUPA CUP Logo ──
        logo_path = os.path.join(
            django_settings.STATICFILES_DIRS[0] if django_settings.STATICFILES_DIRS else django_settings.STATIC_ROOT,
            'img', 'mkj_supacup_logo_official.jpg',
        )
        if os.path.exists(logo_path):
            try:
                logo = RLImage(logo_path, width=30*mm, height=30*mm)
                logo.hAlign = 'CENTER'
                elements.append(logo)
                elements.append(Spacer(1, 2*mm))
            except Exception:
                pass

        # ── Header ──
        header_style = ParagraphStyle(
            'Header', parent=styles['Normal'],
            fontSize=8, textColor=colors.HexColor('#004D1A'),
            alignment=1, spaceAfter=2,
        )
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Title'],
            fontSize=14, spaceAfter=4, alignment=1,
            textColor=colors.HexColor('#1B5E20'),
        )
        subtitle_style = ParagraphStyle(
            'Subtitle', parent=styles['Heading2'],
            fontSize=11, spaceAfter=2, alignment=1,
        )

        elements.append(Paragraph(
            "KENYA YOUTH INTERCOUNTY SPORTS ASSOCIATION",
            header_style,
        ))
        elements.append(Paragraph(
            f"{discipline.registration.county} County — {discipline.get_sport_type_display()}",
            title_style,
        ))
        elements.append(Paragraph("Official Team List", subtitle_style))
        elements.append(Spacer(1, 0.5*cm))

        # ── Technical bench section ──
        if bench_members.exists():
            elements.append(Paragraph("Technical Bench / Delegation", styles['Heading3']))
            bench_data = [['Role', 'Name', 'Phone']]
            for m in bench_members:
                bench_data.append([m.get_role_display(), m.get_full_name, m.phone])
            bench_table = Table(bench_data, colWidths=[5*cm, 7*cm, 5*cm])
            bench_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(bench_table)
            elements.append(Spacer(1, 0.5*cm))

        # ── Players section with photos ──
        elements.append(Paragraph(f"Verified Players ({players.count()})", styles['Heading3']))

        if players.exists():
            cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10)
            name_style = ParagraphStyle('NameCell', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold')

            player_data = [['#', 'Photo', 'Name', 'Date of Birth', 'Position', 'Jersey']]
            row_num = 0
            for p in players:
                row_num += 1
                # Try to load player photo
                photo_cell = ''
                if p.photo and hasattr(p.photo, 'path'):
                    try:
                        photo_path = p.photo.path
                        if os.path.exists(photo_path):
                            photo_cell = RLImage(photo_path, width=18*mm, height=22*mm)
                    except Exception:
                        pass

                dob_str = p.date_of_birth.strftime('%d/%m/%Y') if p.date_of_birth else '—'

                player_data.append([
                    str(row_num),
                    photo_cell,
                    Paragraph(f"{p.last_name} {p.first_name}", name_style),
                    dob_str,
                    p.position or '—',
                    str(p.jersey_number) if p.jersey_number else '—',
                ])

            # Column widths adjusted for photo column
            col_widths = [1*cm, 2.2*cm, 5*cm, 3*cm, 3*cm, 2*cm]
            player_table = Table(player_data, colWidths=col_widths, repeatRows=1)

            # Row heights — header is normal, player rows need space for photo
            row_heights = [None] + [25*mm] * len(players)

            player_table = Table(player_data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
            player_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),   # # column
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),   # Photo column
                ('ALIGN', (5, 0), (5, -1), 'CENTER'),   # Jersey column
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 2*mm),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 2*mm),
            ]))
            elements.append(player_table)
        else:
            elements.append(Paragraph("No verified players.", styles['Normal']))

        elements.append(Spacer(1, 1*cm))
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=1)
        elements.append(Paragraph(
            f"Generated on {timezone.now().strftime('%d %B %Y at %H:%M')} — MKJ SUPA CUP CMS | Confidential — For authorised personnel only",
            footer_style,
        ))

        doc.build(elements)
        buffer.seek(0)

        county = discipline.registration.county
        sport = discipline.get_sport_type_display().replace(' ', '_')
        filename = f"MKJ SUPA CUP_{county}_{sport}_Team_List.pdf"

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except ImportError:
        messages.error(request, 'PDF generation requires the reportlab package. Install it with: pip install reportlab')
        return redirect('county_admin_dashboard')


# ══════════════════════════════════════════════════════════════════════════════
#   SECRETARY GENERAL — READ-ONLY OVERSIGHT PORTAL
# ══════════════════════════════════════════════════════════════════════════════

@role_required('secretary_general')
def sg_dashboard_view(request):
    """Secretary General overview: stats, recent actions, quick links."""
    from admin_dashboard.models import ActivityLog

    total_players = CountyPlayer.objects.count()
    verified_players = CountyPlayer.objects.filter(verification_status='verified').count()
    pending_players = CountyPlayer.objects.filter(verification_status='pending').count()
    rejected_players = CountyPlayer.objects.filter(verification_status='rejected').count()

    from appeals.models import Appeal, AppealStatus
    total_appeals = Appeal.objects.count()
    pending_appeals = Appeal.objects.filter(status=AppealStatus.SUBMITTED).count()
    decided_appeals = Appeal.objects.filter(status=AppealStatus.DECIDED).count()

    recent_activity = ActivityLog.objects.select_related('user').exclude(
        action__in=['LOGIN', 'LOGOUT']
    ).order_by('-timestamp')[:15]

    disciplines = CountyDiscipline.objects.select_related('registration').all()
    sport_breakdown = {}
    for d in disciplines:
        sport = d.get_sport_type_display()
        if sport not in sport_breakdown:
            sport_breakdown[sport] = {'total': 0, 'verified': 0}
        sport_breakdown[sport]['total'] += d.players.count()
        sport_breakdown[sport]['verified'] += d.players.filter(verification_status='verified').count()

    return render(request, 'portal/secretary_general/dashboard.html', {
        'total_players': total_players,
        'verified_players': verified_players,
        'pending_players': pending_players,
        'rejected_players': rejected_players,
        'total_appeals': total_appeals,
        'pending_appeals': pending_appeals,
        'decided_appeals': decided_appeals,
        'recent_activity': recent_activity,
        'sport_breakdown': sport_breakdown,
        'total_counties': CountyRegistration.objects.count(),
    })


@role_required('secretary_general')
def sg_verifications_view(request):
    """SG: View all player verifications across all disciplines (read-only)."""
    tab = request.GET.get('tab', 'verified')
    discipline_filter = request.GET.get('discipline', '')

    players = CountyPlayer.objects.select_related(
        'discipline', 'discipline__registration',
    ).order_by('-registered_at', 'last_name')

    if discipline_filter:
        players = players.filter(discipline__sport_type=discipline_filter)

    verified = players.filter(verification_status='verified')
    pending = players.filter(verification_status='pending')
    rejected = players.filter(verification_status='rejected')

    disciplines = (
        CountyDiscipline.objects.values_list('sport_type', flat=True)
        .distinct().order_by('sport_type')
    )
    discipline_choices = [(st, dict(SportType.choices).get(st, st)) for st in disciplines]

    return render(request, 'portal/secretary_general/verifications.html', {
        'tab': tab,
        'verified_players': verified,
        'pending_players': pending,
        'rejected_players': rejected,
        'disciplines': discipline_choices,
        'discipline_filter': discipline_filter,
        'stats': {
            'verified': verified.count(),
            'pending': pending.count(),
            'rejected': rejected.count(),
        },
    })


@role_required('secretary_general')
def sg_appeals_view(request):
    """SG: View all appeals and their decisions (read-only)."""
    from appeals.models import Appeal, AppealStatus, JuryDecision

    status_filter = request.GET.get('status', '')
    appeals = Appeal.objects.select_related(
        'appellant_team', 'respondent_team', 'appellant_user', 'competition',
    ).order_by('-created_at')

    if status_filter:
        appeals = appeals.filter(status=status_filter)

    return render(request, 'portal/secretary_general/appeals.html', {
        'appeals': appeals,
        'status_choices': AppealStatus.choices,
        'current_status': status_filter,
    })


@role_required('secretary_general')
def sg_treasurer_actions_view(request):
    """SG: View all actions performed by the Treasurer."""
    from admin_dashboard.models import ActivityLog

    treasurer_logs = ActivityLog.objects.filter(
        user__role='treasurer',
    ).exclude(
        action__in=['LOGIN', 'LOGOUT']
    ).select_related('user').order_by('-timestamp')

    return render(request, 'portal/secretary_general/treasurer_actions.html', {
        'logs': treasurer_logs,
    })


@role_required('secretary_general')
def sg_user_actions_view(request):
    """SG: View all user activity — filterable by user and action type."""
    from admin_dashboard.models import ActivityLog

    user_filter = request.GET.get('user', '')
    action_filter = request.GET.get('action', '')

    logs = ActivityLog.objects.select_related('user').exclude(
        action__in=['LOGIN', 'LOGOUT']
    ).order_by('-timestamp')

    if user_filter:
        logs = logs.filter(user_id=user_filter)
    if action_filter:
        logs = logs.filter(action=action_filter)

    users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    action_choices = [
        (code, label) for code, label in ActivityLog.ACTION_CHOICES
        if code not in ('LOGIN', 'LOGOUT')
    ]

    return render(request, 'portal/secretary_general/user_actions.html', {
        'logs': logs[:200],
        'users': users,
        'action_choices': action_choices,
        'user_filter': user_filter,
        'action_filter': action_filter,
    })


@role_required('secretary_general')
def sg_exceptional_overrides_view(request):
    """SG: Track exceptional results/standings overrides submitted by coordinators."""
    from admin_dashboard.models import ActivityLog
    from io import BytesIO

    competition_filter = request.GET.get('competition', '').strip()
    discipline_filter = request.GET.get('discipline', '').strip()
    user_filter = request.GET.get('user', '').strip()
    action_filter = request.GET.get('action', '').strip()
    status_filter = request.GET.get('status', 'pending').strip().lower()
    export_format = request.GET.get('export', '').strip().lower()

    review_base_qs = ActivityLog.objects.filter(
        user__role='coordinator',
        action__in=['STANDINGS_OVERRIDE', 'RESULT_OVERRIDE'],
        extra_data__submitted_to_sg=True,
    )

    if request.method == 'POST':
        log_id = request.POST.get('log_id', '').strip()
        decision = request.POST.get('decision', '').strip().lower()
        review_note = request.POST.get('review_note', '').strip()
        next_query = request.POST.get('next', '').strip()

        redirect_url = 'sg_exceptional_overrides'
        if next_query:
            redirect_url = f"{redirect_url}?{next_query}"

        if decision not in ('acknowledged', 'rejected'):
            messages.error(request, 'Choose a valid SG review decision.')
            return redirect(redirect_url)

        if decision == 'rejected' and len(review_note) < 8:
            messages.error(request, 'Provide a rejection remark of at least 8 characters.')
            return redirect(redirect_url)

        try:
            override_log = review_base_qs.select_related('user').get(pk=int(log_id))
        except (ValueError, ActivityLog.DoesNotExist):
            messages.error(request, 'Override record not found.')
            return redirect(redirect_url)

        extra_data = override_log.extra_data if isinstance(override_log.extra_data, dict) else {}
        extra_data.update({
            'sg_review_status': decision,
            'sg_review_note': review_note,
            'sg_reviewed_at': timezone.now().isoformat(),
            'sg_reviewed_by_id': request.user.pk,
            'sg_reviewed_by_name': request.user.get_full_name() or request.user.email,
        })
        override_log.extra_data = extra_data
        override_log.save(update_fields=['extra_data'])

        ActivityLog.objects.create(
            user=request.user,
            action='SG_OVERRIDE_ACK' if decision == 'acknowledged' else 'SG_OVERRIDE_REJECT',
            description=(
                f"SG {decision} coordinator override #{override_log.pk} "
                f"by {override_log.user.get_full_name() or override_log.user.email}."
            ),
            object_repr=str(override_log.pk),
            ip_address=request.META.get('REMOTE_ADDR', ''),
            extra_data={
                'related_override_log_id': override_log.pk,
                'decision': decision,
                'review_note': review_note,
            },
        )

        messages.success(
            request,
            'Override reviewed successfully.'
            if decision == 'acknowledged'
            else 'Override rejected and logged successfully.'
        )
        return redirect(redirect_url)

    logs = ActivityLog.objects.filter(
        user__role='coordinator',
        action__in=['STANDINGS_OVERRIDE', 'RESULT_OVERRIDE'],
    ).exclude(
        action__in=['LOGIN', 'LOGOUT']
    ).select_related('user').order_by('-timestamp')

    # Keep SG queue focused on explicitly submitted exceptional overrides.
    logs = logs.filter(extra_data__submitted_to_sg=True)

    if competition_filter:
        logs = logs.filter(description__icontains=competition_filter)
    if discipline_filter:
        logs = logs.filter(user__assigned_discipline=discipline_filter)
    if user_filter:
        logs = logs.filter(user_id=user_filter)
    if action_filter:
        logs = logs.filter(action=action_filter)
    if status_filter and status_filter != 'all':
        if status_filter == 'pending':
            logs = logs.exclude(extra_data__sg_review_status__in=['acknowledged', 'rejected'])
        else:
            logs = logs.filter(extra_data__sg_review_status=status_filter)

    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="sg_exceptional_overrides_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            'Timestamp',
            'Coordinator Name',
            'Coordinator Email',
            'Discipline',
            'Override Type',
            'Reason',
            'Description',
            'IP Address',
            'SG Review Status',
            'SG Review Note',
            'SG Reviewed By',
            'SG Reviewed At',
            'Before State',
            'After State',
        ])

        for log in logs.iterator():
            extra_data = log.extra_data if isinstance(log.extra_data, dict) else {}
            writer.writerow([
                timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
                log.user.get_full_name() or '',
                log.user.email or '',
                log.user.assigned_discipline or '',
                'Result Override' if log.action == 'RESULT_OVERRIDE' else 'Standings Override',
                extra_data.get('reason', ''),
                log.description or '',
                log.ip_address or '',
                extra_data.get('sg_review_status', 'pending'),
                extra_data.get('sg_review_note', ''),
                extra_data.get('sg_reviewed_by_name', ''),
                extra_data.get('sg_reviewed_at', ''),
                json.dumps(extra_data.get('before', {}), ensure_ascii=True),
                json.dumps(extra_data.get('after', {}), ensure_ascii=True),
            ])

        return response

    if export_format == 'pdf':
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError:
            messages.error(request, 'PDF export requires reportlab. Install with: pip install reportlab')
            return redirect('sg_exceptional_overrides')

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
        )
        styles = getSampleStyleSheet()
        elements = [
            Paragraph('MKJ SUPA CUP - Exceptional Coordinator Overrides (SG Report)', styles['Title']),
            Paragraph(f"Generated: {timezone.now().strftime('%d %b %Y %H:%M')}", styles['Normal']),
            Spacer(1, 6),
        ]

        rows = [[
            'Date/Time', 'Coordinator', 'Discipline', 'Type', 'Reason', 'SG Status', 'SG Note', 'Description'
        ]]
        for log in logs[:1000]:
            extra_data = log.extra_data if isinstance(log.extra_data, dict) else {}
            rows.append([
                timezone.localtime(log.timestamp).strftime('%d %b %Y %H:%M') if log.timestamp else '',
                (log.user.get_full_name() or log.user.email or '')[:24],
                (log.user.assigned_discipline or '-')[:18],
                'Result' if log.action == 'RESULT_OVERRIDE' else 'Standings',
                (extra_data.get('reason', '') or '-')[:45],
                (extra_data.get('sg_review_status', 'pending') or 'pending')[:14],
                (extra_data.get('sg_review_note', '') or '-')[:35],
                (log.description or '-')[:55],
            ])

        table = Table(rows, colWidths=[25*mm, 35*mm, 26*mm, 18*mm, 43*mm, 24*mm, 36*mm, 50*mm], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#BDBDBD')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7F7F7')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)
        if logs.count() > 1000:
            elements.append(Spacer(1, 5))
            elements.append(Paragraph('Showing first 1000 rows only.', styles['Italic']))
        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="sg_exceptional_overrides_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        )
        return response

    users = User.objects.filter(role='coordinator', is_active=True).order_by('first_name', 'last_name')
    discipline_choices = [
        (value, label) for value, label in SportType.choices
    ]
    action_choices = [
        ('STANDINGS_OVERRIDE', 'Standings Override'),
        ('RESULT_OVERRIDE', 'Result Override'),
    ]
    status_choices = [
        ('pending', 'Pending Review'),
        ('acknowledged', 'Acknowledged'),
        ('rejected', 'Rejected'),
        ('all', 'All'),
    ]

    base_qs = review_base_qs
    pending_qs = base_qs.exclude(extra_data__sg_review_status__in=['acknowledged', 'rejected'])

    return render(request, 'portal/secretary_general/exceptional_overrides.html', {
        'logs': logs[:200],
        'users': users,
        'discipline_choices': discipline_choices,
        'action_choices': action_choices,
        'status_choices': status_choices,
        'competition_filter': competition_filter,
        'discipline_filter': discipline_filter,
        'user_filter': user_filter,
        'action_filter': action_filter,
        'status_filter': status_filter,
        'current_query': request.GET.urlencode,
        'stats': {
            'total': base_qs.count(),
            'pending': pending_qs.count(),
            'acknowledged': base_qs.filter(extra_data__sg_review_status='acknowledged').count(),
            'rejected': base_qs.filter(extra_data__sg_review_status='rejected').count(),
            'result_overrides': base_qs.filter(action='RESULT_OVERRIDE').count(),
            'standings_overrides': base_qs.filter(action='STANDINGS_OVERRIDE').count(),
        },
    })


@role_required('secretary_general')
def sg_verified_players_view(request):
    """SG: View verified players for all disciplines — who verified, when, where."""
    discipline_filter = request.GET.get('discipline', '')
    county_filter = request.GET.get('county', '')

    players = CountyPlayer.objects.filter(
        verification_status='verified',
    ).select_related(
        'discipline', 'discipline__registration',
    ).order_by('discipline__sport_type', 'discipline__registration__county', 'last_name')

    if discipline_filter:
        players = players.filter(discipline__sport_type=discipline_filter)
    if county_filter:
        players = players.filter(discipline__registration__county=county_filter)

    disc_values = CountyDiscipline.objects.values_list('sport_type', flat=True).distinct().order_by('sport_type')
    disciplines = [(st, dict(SportType.choices).get(st, st)) for st in disc_values]
    counties = CountyRegistration.objects.values_list('county', flat=True).distinct().order_by('county')

    return render(request, 'portal/secretary_general/verified_players.html', {
        'players': players,
        'disciplines': disciplines,
        'counties': counties,
        'discipline_filter': discipline_filter,
        'county_filter': county_filter,
        'total': players.count(),
    })


# ══════════════════════════════════════════════════════════════════════════════
#   SCOUT PORTAL
# ══════════════════════════════════════════════════════════════════════════════

@role_required('scout', 'admin')
def scout_dashboard_view(request):
    """Scout dashboard — overview of shortlisted players and browse, scoped to discipline."""
    from teams.models import ScoutShortlist, CountyPlayer, CountyDiscipline, CountyRegistration

    user = request.user
    discipline = user.assigned_discipline
    discipline_label = dict(SportType.choices).get(discipline, discipline or 'Not Assigned')

    shortlist = ScoutShortlist.objects.filter(scout=user).select_related(
        'player', 'player__discipline', 'player__discipline__registration',
    )

    # Scope total players to scout's assigned discipline if set
    player_qs = CountyPlayer.objects.filter(verification_status='verified')
    if discipline:
        player_qs = player_qs.filter(discipline__sport_type=discipline)
    total_players = player_qs.count()

    return render(request, 'portal/scout/dashboard.html', {
        'discipline': discipline,
        'discipline_label': discipline_label,
        'shortlist': shortlist[:10],
        'shortlist_count': shortlist.count(),
        'total_players': total_players,
        'top_rated': shortlist.filter(rating__gte=4).count(),
    })


@role_required('scout', 'admin')
def scout_players_view(request):
    """Browse verified players for scouting — defaults to scout's assigned discipline."""
    from teams.models import ScoutShortlist, CountyPlayer, CountyDiscipline, CountyRegistration

    discipline_filter = request.GET.get('discipline', '')
    county_filter = request.GET.get('county', '')
    search_query = request.GET.get('q', '').strip()

    # Default to the scout's assigned discipline if no filter explicitly set
    if not discipline_filter and 'discipline' not in request.GET and request.user.assigned_discipline:
        discipline_filter = request.user.assigned_discipline

    players = CountyPlayer.objects.filter(
        verification_status='verified',
    ).select_related(
        'discipline', 'discipline__registration',
    ).order_by('last_name', 'first_name')

    if discipline_filter:
        players = players.filter(discipline__sport_type=discipline_filter)
    if county_filter:
        players = players.filter(discipline__registration__county=county_filter)
    if search_query:
        players = players.filter(
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query)
        )

    # Get IDs already shortlisted by this scout
    shortlisted_ids = set(
        ScoutShortlist.objects.filter(scout=request.user).values_list('player_id', flat=True)
    )

    disc_values = CountyDiscipline.objects.values_list('sport_type', flat=True).distinct().order_by('sport_type')
    disciplines = [(st, dict(SportType.choices).get(st, st)) for st in disc_values]
    counties = CountyRegistration.objects.values_list('county', flat=True).distinct().order_by('county')

    return render(request, 'portal/scout/players.html', {
        'players': players,
        'shortlisted_ids': shortlisted_ids,
        'disciplines': disciplines,
        'counties': counties,
        'discipline_filter': discipline_filter,
        'county_filter': county_filter,
        'search_query': search_query,
        'total': players.count(),
    })


@role_required('scout', 'admin')
def scout_shortlist_view(request):
    """View and manage the scout's shortlist."""
    from teams.models import ScoutShortlist

    shortlist = ScoutShortlist.objects.filter(scout=request.user).select_related(
        'player', 'player__discipline', 'player__discipline__registration',
    )

    rating_filter = request.GET.get('rating', '')
    if rating_filter:
        shortlist = shortlist.filter(rating=int(rating_filter))

    return render(request, 'portal/scout/shortlist.html', {
        'shortlist': shortlist,
        'rating_filter': rating_filter,
        'total': shortlist.count(),
    })


@role_required('scout', 'admin')
def scout_add_to_shortlist_view(request, player_pk):
    """Add a player to the scout's shortlist."""
    from teams.models import ScoutShortlist, CountyPlayer

    if request.method != 'POST':
        return redirect('scout_players')

    player = get_object_or_404(CountyPlayer, pk=player_pk, verification_status='verified')
    rating = int(request.POST.get('rating', 3))
    notes = request.POST.get('notes', '').strip()

    obj, created = ScoutShortlist.objects.get_or_create(
        scout=request.user, player=player,
        defaults={'rating': max(1, min(5, rating)), 'notes': notes},
    )
    if created:
        messages.success(request, f'{player.first_name} {player.last_name} added to your shortlist.')
    else:
        messages.info(request, f'{player.first_name} {player.last_name} is already on your shortlist.')

    return redirect('scout_players')


@role_required('scout', 'admin')
def scout_edit_shortlist_view(request, pk):
    """Edit rating/notes on a shortlisted player."""
    from teams.models import ScoutShortlist

    entry = get_object_or_404(ScoutShortlist, pk=pk, scout=request.user)

    if request.method == 'POST':
        entry.rating = max(1, min(5, int(request.POST.get('rating', entry.rating))))
        entry.notes = request.POST.get('notes', entry.notes).strip()
        entry.save(update_fields=['rating', 'notes', 'updated_at'])
        messages.success(request, 'Shortlist entry updated.')
        return redirect('scout_shortlist')

    return render(request, 'portal/scout/edit_shortlist.html', {'entry': entry})


@role_required('scout', 'admin')
def scout_remove_from_shortlist_view(request, pk):
    """Remove a player from the scout's shortlist."""
    from teams.models import ScoutShortlist

    entry = get_object_or_404(ScoutShortlist, pk=pk, scout=request.user)
    if request.method == 'POST':
        name = f'{entry.player.first_name} {entry.player.last_name}'
        entry.delete()
        messages.success(request, f'{name} removed from your shortlist.')
    return redirect('scout_shortlist')


# ── Scout: Live Matches for Scouting ─────────────────────────────────────────

@role_required('scout', 'admin')
def scout_live_matches_view(request):
    """Scout: List fixtures (today/upcoming/past) with squad lists for live scouting."""
    user = request.user
    discipline = user.assigned_discipline
    today = date.today()
    filter_status = request.GET.get('status', 'today')

    fixtures_qs = Fixture.objects.select_related(
        'competition', 'home_team', 'away_team', 'venue',
    )
    if discipline:
        variants = _coordinator_variants(discipline)
        if variants:
            fixtures_qs = fixtures_qs.filter(competition__sport_type__in=variants)

    if filter_status == 'today':
        fixtures_qs = fixtures_qs.filter(match_date=today)
    elif filter_status == 'upcoming':
        fixtures_qs = fixtures_qs.filter(match_date__gte=today).exclude(status='cancelled')
    elif filter_status == 'past':
        fixtures_qs = fixtures_qs.filter(match_date__lt=today, status='completed')

    fixtures_qs = fixtures_qs.order_by('match_date', 'kickoff_time')

    # Check which fixtures have approved squads
    fixture_data = []
    for f in fixtures_qs:
        home_squad = SquadSubmission.objects.filter(fixture=f, team=f.home_team, status='approved').first()
        away_squad = SquadSubmission.objects.filter(fixture=f, team=f.away_team, status='approved').first()
        fixture_data.append({
            'fixture': f,
            'has_squads': bool(home_squad or away_squad),
            'home_squad_approved': bool(home_squad),
            'away_squad_approved': bool(away_squad),
        })

    discipline_label = _coordinator_label(discipline) if discipline else 'All Disciplines'

    return render(request, 'portal/scout/live_matches.html', {
        'fixture_data': fixture_data,
        'filter_status': filter_status,
        'discipline_label': discipline_label,
        'total': len(fixture_data),
    })


@role_required('scout', 'admin')
def scout_match_squad_view(request, fixture_pk):
    """Scout: View full squad lists for a fixture including substitutions."""
    fixture = get_object_or_404(
        Fixture.objects.select_related('competition', 'home_team', 'away_team', 'venue'),
        pk=fixture_pk,
    )
    sport_type = fixture.competition.sport_type

    # Home squad
    home_squad = SquadSubmission.objects.filter(
        fixture=fixture, team=fixture.home_team, status='approved'
    ).first()
    home_players = SquadPlayer.objects.filter(
        submission=home_squad
    ).select_related('player').order_by('-is_starter', 'shirt_number') if home_squad else []

    # Away squad
    away_squad = SquadSubmission.objects.filter(
        fixture=fixture, team=fixture.away_team, status='approved'
    ).first()
    away_players = SquadPlayer.objects.filter(
        submission=away_squad
    ).select_related('player').order_by('-is_starter', 'shirt_number') if away_squad else []

    # Substitution events from match report
    subs = []
    try:
        report = MatchReport.objects.get(fixture=fixture)
        subs = report.events.filter(
            event_type__in=['sub_on', 'sub_off']
        ).select_related('player', 'team').order_by('minute')
    except MatchReport.DoesNotExist:
        pass

    # Existing scout reports for this fixture by this scout
    from teams.models import ScoutReport
    my_reports = set(
        ScoutReport.objects.filter(
            scout=request.user, fixture=fixture
        ).values_list('player_id', flat=True)
    )

    return render(request, 'portal/scout/match_squad.html', {
        'fixture': fixture,
        'home_players': home_players,
        'away_players': away_players,
        'home_squad': home_squad,
        'away_squad': away_squad,
        'subs': subs,
        'my_reports': my_reports,
        'sport_type': sport_type,
    })


@role_required('scout', 'admin')
def scout_evaluate_player_view(request, fixture_pk, player_pk):
    """Scout: Create or edit a detailed scouting evaluation for a player in a match."""
    from teams.models import ScoutReport, get_scouting_criteria

    fixture = get_object_or_404(
        Fixture.objects.select_related('competition', 'home_team', 'away_team'),
        pk=fixture_pk,
    )
    player = get_object_or_404(Player, pk=player_pk)
    sport_type = fixture.competition.sport_type
    criteria_def = get_scouting_criteria(sport_type)

    # Determine if player is a GK
    is_gk = (player.position or '').upper() in ('GK', 'GOALKEEPER')
    criteria_list = list(criteria_def.get('criteria', []))
    if is_gk and 'gk_criteria' in criteria_def:
        criteria_list.extend(criteria_def['gk_criteria'])

    # Get or create report
    try:
        report = ScoutReport.objects.get(scout=request.user, player=player, fixture=fixture)
    except ScoutReport.DoesNotExist:
        report = None

    if request.method == 'POST':
        # Parse criteria scores
        scores = {}
        for c in criteria_list:
            val = request.POST.get(f'criteria_{c["key"]}', '')
            if val:
                scores[c['key']] = max(1, min(10, int(val)))

        overall = max(1, min(10, int(request.POST.get('overall_rating', 5))))
        strengths = request.POST.get('strengths', '').strip()
        weaknesses = request.POST.get('weaknesses', '').strip()
        recommendation = request.POST.get('recommendation', 'monitor')
        notes = request.POST.get('notes', '').strip()
        minutes_observed = int(request.POST.get('minutes_observed', 0))

        if report:
            report.criteria_scores = scores
            report.overall_rating = overall
            report.strengths = strengths
            report.weaknesses = weaknesses
            report.recommendation = recommendation
            report.notes = notes
            report.minutes_observed = minutes_observed
            report.sport_type = sport_type
            report.save()
            messages.success(request, f'Evaluation updated for {player.first_name} {player.last_name}.')
        else:
            ScoutReport.objects.create(
                scout=request.user,
                player=player,
                fixture=fixture,
                sport_type=sport_type,
                criteria_scores=scores,
                overall_rating=overall,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendation=recommendation,
                notes=notes,
                minutes_observed=minutes_observed,
            )
            messages.success(request, f'Evaluation saved for {player.first_name} {player.last_name}.')

        return redirect('scout_match_squad', fixture_pk=fixture.pk)

    return render(request, 'portal/scout/evaluate_player.html', {
        'fixture': fixture,
        'player': player,
        'criteria_list': criteria_list,
        'criteria_def': criteria_def,
        'is_gk': is_gk,
        'report': report,
        'sport_type': sport_type,
    })


@role_required('scout', 'admin')
def scout_reports_view(request):
    """Scout: View all my scouting reports."""
    from teams.models import ScoutReport

    reports = ScoutReport.objects.filter(
        scout=request.user
    ).select_related(
        'player__team', 'fixture__competition', 'fixture__home_team', 'fixture__away_team',
    )

    discipline_filter = request.GET.get('discipline', '')
    recommendation_filter = request.GET.get('recommendation', '')

    if discipline_filter:
        variants = _coordinator_variants(discipline_filter)
        if variants:
            reports = reports.filter(fixture__competition__sport_type__in=variants)

    if recommendation_filter:
        reports = reports.filter(recommendation=recommendation_filter)

    return render(request, 'portal/scout/reports.html', {
        'reports': reports,
        'total': reports.count(),
        'discipline_filter': discipline_filter,
        'recommendation_filter': recommendation_filter,
    })


@role_required('scout', 'admin')
def scout_report_detail_view(request, pk):
    """Scout: View details of one of my scouting reports."""
    from teams.models import ScoutReport, get_scouting_criteria

    report = get_object_or_404(
        ScoutReport.objects.select_related(
            'player__team', 'fixture__competition', 'fixture__home_team', 'fixture__away_team', 'scout',
        ),
        pk=pk, scout=request.user,
    )

    criteria_def = get_scouting_criteria(report.sport_type)
    return render(request, 'portal/scout/report_detail.html', {
        'report': report,
        'criteria_display': report.criteria_display,
        'criteria_def': criteria_def,
    })


# ── Leadership: View Scout Reports ──────────────────────────────────────────

@role_required('chief_sports_officer', 'director_sports', 'chief_officer_sports', 'cec_sports', 'admin')
def leadership_scout_reports_view(request):
    """Leadership roles: View all scouting reports across all scouts."""
    from teams.models import ScoutReport

    reports = ScoutReport.objects.select_related(
        'scout', 'player__team', 'fixture__competition', 'fixture__home_team', 'fixture__away_team',
    )

    scout_filter = request.GET.get('scout', '')
    discipline_filter = request.GET.get('discipline', '')
    recommendation_filter = request.GET.get('recommendation', '')

    if scout_filter:
        reports = reports.filter(scout_id=scout_filter)
    if discipline_filter:
        variants = _coordinator_variants(discipline_filter)
        if variants:
            reports = reports.filter(fixture__competition__sport_type__in=variants)
    if recommendation_filter:
        reports = reports.filter(recommendation=recommendation_filter)

    from accounts.models import User
    scouts = User.objects.filter(role='scout').order_by('first_name', 'last_name')

    stats = {
        'total_reports': reports.count(),
        'highly_recommended': reports.filter(recommendation='highly_recommended').count(),
        'recommended': reports.filter(recommendation='recommended').count(),
        'scouts_active': reports.values('scout').distinct().count(),
    }

    return render(request, 'portal/leadership/scout_reports.html', {
        'reports': reports,
        'scouts': scouts,
        'stats': stats,
        'scout_filter': scout_filter,
        'discipline_filter': discipline_filter,
        'recommendation_filter': recommendation_filter,
    })


@role_required('chief_sports_officer', 'director_sports', 'chief_officer_sports', 'cec_sports', 'admin')
def leadership_scout_report_detail_view(request, pk):
    """Leadership roles: View a specific scouting report in detail."""
    from teams.models import ScoutReport, get_scouting_criteria

    report = get_object_or_404(
        ScoutReport.objects.select_related(
            'player__team', 'fixture__competition', 'fixture__home_team', 'fixture__away_team', 'scout',
        ),
        pk=pk,
    )

    criteria_def = get_scouting_criteria(report.sport_type)
    return render(request, 'portal/scout/report_detail.html', {
        'report': report,
        'criteria_display': report.criteria_display,
        'criteria_def': criteria_def,
        'is_leadership_view': True,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   SUB-COUNTY SPORTS OFFICER PORTAL
# ══════════════════════════════════════════════════════════════════════════════

@role_required('subcounty_sports_officer', 'admin')
def subcounty_officer_dashboard_view(request):
    """Dashboard for sub-county sports officers."""
    user = request.user
    sub_county = user.sub_county or 'Unassigned'
    county_reg = _get_primary_registration_for_user(user, auto_create=True)
    disciplines = _discipline_queryset_for_user(user)
    players_count = CountyPlayer.objects.filter(discipline__in=disciplines).count()
    teams_count = Team.objects.filter(source_discipline__in=disciplines).count()
    bench_count = TechnicalBenchMember.objects.filter(discipline__in=disciplines).count()

    stats = {
        'county': user.county or 'Unassigned',
        'sub_county': sub_county,
        'disciplines': disciplines.count() if disciplines else 0,
        'players': players_count,
        'teams': teams_count,
        'bench_members': bench_count,
        'fixtures': Fixture.objects.count(),
        'competitions': Competition.objects.count(),
    }

    upcoming_fixtures = Fixture.objects.filter(
        match_date__gte=timezone.now()
    ).select_related('competition', 'home_team', 'away_team', 'venue').order_by('match_date')[:6]

    return render(request, 'portal/subcounty_officer/dashboard.html', {
        'stats': stats,
        'upcoming_fixtures': upcoming_fixtures,
        'sub_county': sub_county,
        'disciplines': disciplines,
        'county_reg': county_reg,
    })


@role_required('subcounty_sports_officer', 'admin')
def subcounty_officer_disciplines_view(request):
    """List and add disciplines for the officer's assigned sub-county."""
    county_reg = _get_primary_registration_for_user(request.user, auto_create=True)
    if not county_reg:
        messages.warning(request, 'Assign a county before managing disciplines.')
        return redirect('subcounty_officer_dashboard')

    existing = set(_discipline_queryset_for_user(request.user).values_list('sport_type', flat=True))
    if request.method == 'POST':
        sport = request.POST.get('sport_type', '').strip()
        if not request.user.sub_county:
            messages.error(request, 'Assign a sub-county to this user before adding disciplines.')
        elif sport in dict(SQUAD_LIMITS) and sport not in existing:
            CountyDiscipline.objects.create(
                registration=county_reg,
                sport_type=sport,
                sub_county=request.user.sub_county,
            )
            messages.success(request, f'{dict(SportType.choices).get(sport, sport)} added for {request.user.sub_county}.')
        else:
            messages.error(request, 'Invalid discipline or already added for this sub-county.')
        return redirect('subcounty_officer_disciplines')

    disciplines = _discipline_queryset_for_user(request.user)
    return render(request, 'portal/subcounty_officer/disciplines.html', {
        'disciplines': disciplines,
        'reg': county_reg,
        'available': [(code, dict(SportType.choices).get(code, code), limit) for code, limit in SQUAD_LIMITS.items() if code not in existing],
    })


@role_required('subcounty_sports_officer', 'admin')
def subcounty_officer_discipline_players_view(request, discipline_pk):
    """View players in a discipline, sorted by verification status tabs."""
    county_reg = _get_primary_registration_for_user(request.user, auto_create=True)
    if not county_reg:
        messages.warning(request, 'Assign a county before managing disciplines.')
        return redirect('subcounty_officer_dashboard')

    discipline = _get_managed_discipline(request.user, discipline_pk)
    tab = request.GET.get('tab', 'all')
    players = discipline.players.all().order_by('last_name', 'first_name')

    pending = players.filter(verification_status='pending')
    verified = players.filter(verification_status='verified')
    rejected = players.filter(verification_status='rejected')
    resubmit = players.filter(verification_status='resubmit')

    # Auto-created team reference
    team = Team.objects.filter(source_discipline=discipline).first()

    return render(request, 'portal/subcounty_officer/discipline_players.html', {
        'reg': county_reg,
        'discipline': discipline,
        'players': players,
        'pending_players': pending,
        'verified_players': verified,
        'rejected_players': rejected,
        'resubmit_players': resubmit,
        'tab': tab,
        'stats': {
            'total': players.count(),
            'pending': pending.count(),
            'verified': verified.count(),
            'rejected': rejected.count(),
            'resubmit': resubmit.count(),
        },
        'team': team,
        'bench_members': discipline.technical_bench.all().order_by('role'),
    })


@role_required('subcounty_sports_officer', 'admin')
def subcounty_officer_add_player_view(request, discipline_pk):
    """Sub-county sports officer adds a player to a discipline."""
    county_reg = _get_primary_registration_for_user(request.user, auto_create=True)
    if not county_reg:
        messages.warning(request, 'Assign a county before managing disciplines.')
        return redirect('subcounty_officer_dashboard')

    discipline = _get_managed_discipline(request.user, discipline_pk)

    if not discipline.can_add_player:
        messages.error(
            request,
            f'Squad limit reached ({discipline.squad_limit}) for '
            f'{discipline.get_sport_type_display()}.'
        )
        return redirect('subcounty_officer_discipline_players', discipline_pk=discipline_pk)

    if request.method == 'POST':
        form = CountyPlayerForm(request.POST, request.FILES)
        if form.is_valid():
            player = form.save(commit=False)
            player.discipline = discipline
            player.save()
            messages.success(
                request,
                f'{player.first_name} {player.last_name} registered '
                f'({discipline.player_count}/{discipline.squad_limit}).'
            )
            return redirect('subcounty_officer_discipline_players', discipline_pk=discipline_pk)
    else:
        form = CountyPlayerForm()

    return render(request, 'portal/subcounty_officer/add_player.html', {
        'form': form,
        'discipline': discipline,
        'reg': county_reg,
    })


@role_required('subcounty_sports_officer', 'admin')
def subcounty_officer_delete_player_view(request, player_pk):
    """Sub-county sports officer removes a player from a discipline."""
    county_reg = _get_primary_registration_for_user(request.user, auto_create=True)
    if not county_reg:
        messages.warning(request, 'Assign a county before managing disciplines.')
        return redirect('subcounty_officer_dashboard')

    player = get_object_or_404(CountyPlayer, pk=player_pk, discipline__in=_discipline_queryset_for_user(request.user))
    discipline_pk = player.discipline.pk

    if request.method == 'POST':
        name = f'{player.first_name} {player.last_name}'
        player.delete()
        messages.success(request, f'{name} removed.')
    return redirect('subcounty_officer_discipline_players', discipline_pk=discipline_pk)


# ══════════════════════════════════════════════════════════════════════════════
#   DIRECTOR OF SPORTS PORTAL
# ══════════════════════════════════════════════════════════════════════════════

@role_required('director_sports', 'admin')
def director_sports_dashboard_view(request):
    """Dashboard for Director of Sports — high-level oversight of all competitions."""
    stats = {
        'competitions': Competition.objects.count(),
        'teams': Team.objects.count(),
        'players': Player.objects.count(),
        'referees': RefereeProfile.objects.filter(is_approved=True).count(),
        'fixtures': Fixture.objects.count(),
        'counties_registered': CountyRegistration.objects.filter(status='approved').count(),
    }

    active_comps = Competition.objects.filter(
        status__in=['active', 'group_stage', 'knockout']
    ).order_by('-start_date')[:5]

    recent_results = Fixture.objects.filter(
        status='completed'
    ).select_related('competition', 'home_team', 'away_team').order_by('-match_date')[:8]

    return render(request, 'portal/director_sports/dashboard.html', {
        'stats': stats,
        'active_competitions': active_comps,
        'recent_results': recent_results,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   CHIEF OFFICER SPORTS PORTAL
# ══════════════════════════════════════════════════════════════════════════════

@role_required('chief_officer_sports', 'chief_sports_officer', 'admin')
def chief_officer_sports_dashboard_view(request):
    """Dashboard for Chief Officer - Sports — executive oversight."""
    all_disciplines = CountyDiscipline.objects.select_related('registration').all()
    stats = {
        'competitions': Competition.objects.count(),
        'teams': Team.objects.count(),
        'players': CountyPlayer.objects.count(),
        'referees': RefereeProfile.objects.filter(is_approved=True).count(),
        'fixtures': Fixture.objects.count(),
        'counties_registered': CountyRegistration.objects.filter(status='approved').count(),
        'subcounties_active': all_disciplines.exclude(sub_county='').values('sub_county').distinct().count(),
        'disciplines': all_disciplines.count(),
    }

    active_comps = Competition.objects.filter(
        status__in=['active', 'group_stage', 'knockout']
    ).order_by('-start_date')[:5]

    recent_results = Fixture.objects.filter(
        status='completed'
    ).select_related('competition', 'home_team', 'away_team').order_by('-match_date')[:8]

    recent_teams = Team.objects.select_related('county').order_by('-registered_at')[:10]
    recent_players = CountyPlayer.objects.select_related('discipline__registration').order_by('-registered_at')[:10]

    return render(request, 'portal/chief_officer_sports/dashboard.html', {
        'stats': stats,
        'active_competitions': active_comps,
        'recent_results': recent_results,
        'recent_teams': recent_teams,
        'recent_players': recent_players,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   VERIFIED PLAYER LISTS — Sub-County Officer / Team Manager / Director
# ══════════════════════════════════════════════════════════════════════════════

@role_required('subcounty_sports_officer', 'admin')
def subcounty_verified_players_view(request):
    """Sub-county officer: view verified players scoped to their sub-county."""
    user = request.user
    discipline_filter = request.GET.get('discipline', '')
    disciplines = _discipline_queryset_for_user(user)

    players = CountyPlayer.objects.filter(
        verification_status='verified',
        discipline__in=disciplines,
    ).select_related('discipline', 'discipline__registration').order_by(
        'discipline__sport_type', 'last_name',
    )

    if discipline_filter:
        players = players.filter(discipline__sport_type=discipline_filter)

    disc_values = disciplines.values_list('sport_type', flat=True).distinct().order_by('sport_type')
    disc_choices = [(st, dict(SportType.choices).get(st, st)) for st in disc_values]

    return render(request, 'portal/subcounty_officer/verified_players.html', {
        'players': players,
        'disciplines': disc_choices,
        'discipline_filter': discipline_filter,
        'total': players.count(),
        'sub_county': user.sub_county or 'Unassigned',
    })


@role_required('team_manager', 'admin')
def team_manager_verified_players_view(request):
    """Team manager: view verified players for their discipline."""
    user = request.user
    discipline_filter = request.GET.get('discipline', '')

    try:
        bench = TechnicalBenchMember.objects.select_related(
            'discipline__registration',
        ).get(user=user, role=TechnicalBenchRole.TEAM_MANAGER)
        discipline = bench.discipline
    except TechnicalBenchMember.DoesNotExist:
        discipline = None

    if discipline:
        players = CountyPlayer.objects.filter(
            verification_status='verified',
            discipline=discipline,
        ).select_related('discipline', 'discipline__registration').order_by('last_name')
        disc_choices = [(discipline.sport_type, dict(SportType.choices).get(discipline.sport_type, discipline.sport_type))]
    else:
        players = CountyPlayer.objects.none()
        disc_choices = []

    return render(request, 'portal/team_manager/verified_players.html', {
        'players': players,
        'disciplines': disc_choices,
        'discipline_filter': discipline_filter,
        'total': players.count(),
        'discipline': discipline,
    })


@role_required('director_sports', 'admin')
def director_sports_verified_players_view(request):
    """Director of Sports: view all verified players across all disciplines."""
    discipline_filter = request.GET.get('discipline', '')
    county_filter = request.GET.get('county', '')

    players = CountyPlayer.objects.filter(
        verification_status='verified',
    ).select_related('discipline', 'discipline__registration').order_by(
        'discipline__sport_type', 'discipline__registration__county', 'last_name',
    )

    if discipline_filter:
        players = players.filter(discipline__sport_type=discipline_filter)
    if county_filter:
        players = players.filter(discipline__registration__county=county_filter)

    disc_values = CountyDiscipline.objects.values_list('sport_type', flat=True).distinct().order_by('sport_type')
    disc_choices = [(st, dict(SportType.choices).get(st, st)) for st in disc_values]
    counties = CountyRegistration.objects.values_list('county', flat=True).distinct().order_by('county')

    return render(request, 'portal/director_sports/verified_players.html', {
        'players': players,
        'disciplines': disc_choices,
        'counties': counties,
        'discipline_filter': discipline_filter,
        'county_filter': county_filter,
        'total': players.count(),
    })


@login_required(login_url='web_login')
def verified_players_pdf_view(request):
    """Generate a PDF of verified players, scoped to the user's role."""
    from django.http import HttpResponse
    from io import BytesIO

    user = request.user
    discipline_filter = request.GET.get('discipline', '')

    # Build queryset based on role
    if user.role == 'subcounty_sports_officer':
        disciplines = _discipline_queryset_for_user(user)
        players = CountyPlayer.objects.filter(
            verification_status='verified', discipline__in=disciplines,
        )
        scope_label = f"{user.sub_county or 'Sub-County'} — {user.county or ''}"
    elif user.role == 'team_manager':
        try:
            bench = TechnicalBenchMember.objects.select_related(
                'discipline__registration',
            ).get(user=user, role=TechnicalBenchRole.TEAM_MANAGER)
            players = CountyPlayer.objects.filter(
                verification_status='verified', discipline=bench.discipline,
            )
            scope_label = f"{bench.discipline.registration.county} — {bench.discipline.get_sport_type_display()}"
        except TechnicalBenchMember.DoesNotExist:
            players = CountyPlayer.objects.none()
            scope_label = "No discipline assigned"
    elif user.role == 'director_sports' or user.is_superuser:
        players = CountyPlayer.objects.filter(verification_status='verified')
        county_filter = request.GET.get('county', '')
        if county_filter:
            players = players.filter(discipline__registration__county=county_filter)
        scope_label = "All Counties — All Disciplines"
    else:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    players = players.select_related('discipline', 'discipline__registration').order_by(
        'discipline__sport_type', 'last_name',
    )
    if discipline_filter:
        sport_label = dict(SportType.choices).get(discipline_filter, discipline_filter)
        players = players.filter(discipline__sport_type=discipline_filter)
        scope_label += f" — {sport_label}"

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            Image as RLImage,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm, mm
        import os

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        # Logo
        logo_path = os.path.join(
            django_settings.STATICFILES_DIRS[0] if django_settings.STATICFILES_DIRS else django_settings.STATIC_ROOT,
            'img', 'mkj_supacup_logo_official.jpg',
        )
        if os.path.exists(logo_path):
            try:
                logo = RLImage(logo_path, width=30 * mm, height=30 * mm)
                logo.hAlign = 'CENTER'
                elements.append(logo)
                elements.append(Spacer(1, 2 * mm))
            except Exception:
                pass

        header_style = ParagraphStyle(
            'Header', parent=styles['Normal'],
            fontSize=8, textColor=colors.HexColor('#004D1A'), alignment=1, spaceAfter=2,
        )
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Title'],
            fontSize=14, spaceAfter=4, alignment=1, textColor=colors.HexColor('#1B5E20'),
        )
        subtitle_style = ParagraphStyle(
            'Subtitle', parent=styles['Heading2'],
            fontSize=11, spaceAfter=2, alignment=1,
        )

        elements.append(Paragraph("MKJ SUPA CUP — 4th Edition", header_style))
        elements.append(Paragraph("Verified Players List", title_style))
        elements.append(Paragraph(scope_label, subtitle_style))
        elements.append(Spacer(1, 0.5 * cm))

        # Players table
        cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10)
        name_style = ParagraphStyle('NameCell', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold')

        player_data = [['#', 'Photo', 'Name', 'Discipline', 'National ID', 'Position', 'Jersey']]
        row_num = 0
        for p in players:
            row_num += 1
            photo_cell = ''
            if p.photo and hasattr(p.photo, 'path'):
                try:
                    photo_path = p.photo.path
                    if os.path.exists(photo_path):
                        photo_cell = RLImage(photo_path, width=18 * mm, height=22 * mm)
                except Exception:
                    pass

            player_data.append([
                str(row_num),
                photo_cell,
                Paragraph(f"{p.last_name} {p.first_name}", name_style),
                p.discipline.get_sport_type_display() if p.discipline else '—',
                p.national_id_number or '—',
                p.position or '—',
                str(p.jersey_number) if p.jersey_number else '—',
            ])

        if row_num > 0:
            col_widths = [1 * cm, 2.2 * cm, 4 * cm, 3 * cm, 2.8 * cm, 2 * cm, 1.5 * cm]
            row_heights = [None] + [25 * mm] * row_num
            player_table = Table(player_data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
            player_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('ALIGN', (6, 0), (6, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 2 * mm),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 2 * mm),
            ]))
            elements.append(Paragraph(f"Verified Players ({row_num})", styles['Heading3']))
            elements.append(player_table)
        else:
            elements.append(Paragraph("No verified players found.", styles['Normal']))

        elements.append(Spacer(1, 1 * cm))
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=1)
        elements.append(Paragraph(
            f"Generated on {timezone.now().strftime('%d %B %Y at %H:%M')} — MKJ SUPA CUP CMS | Confidential",
            footer_style,
        ))

        doc.build(elements)
        buffer.seek(0)

        filename = f"MKJ_SUPA_CUP_Verified_Players_{timezone.now().strftime('%Y%m%d')}.pdf"
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except ImportError:
        messages.error(request, 'PDF generation requires the reportlab package.')
        return redirect('dashboard')


@login_required(login_url='web_login')
def match_squad_pdf_view(request, squad_pk):
    """Download an approved match-day squad sheet as PDF."""
    from django.http import HttpResponse
    from io import BytesIO

    squad = get_object_or_404(
        SquadSubmission.objects.select_related(
            'fixture__home_team', 'fixture__away_team', 'fixture__competition',
            'fixture__venue', 'team',
        ),
        pk=squad_pk,
    )

    # Only approved squads can be downloaded
    if squad.status != SquadStatus.APPROVED:
        messages.warning(request, 'Squad sheet can only be downloaded after referee approval.')
        return redirect('dashboard')

    # Permission check — team manager, referee, admin, CM, director, chief officer
    user = request.user
    allowed = user.is_superuser or user.role in (
        'admin', 'competition_manager', 'chief_sports_officer',
        'director_sports', 'referee', 'secretary_general',
    )
    if user.role == 'team_manager':
        my_teams = Team.objects.filter(manager=user)
        if squad.team in my_teams:
            allowed = True
    if user.role == 'subcounty_sports_officer':
        allowed = True

    if not allowed:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    fixture = squad.fixture
    squad_players = squad.squad_players.select_related('player').order_by('-is_starter', 'shirt_number')
    starters = [sp for sp in squad_players if sp.is_starter]
    subs = [sp for sp in squad_players if not sp.is_starter]

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            Image as RLImage,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm, mm
        import os

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        # Logo
        logo_path = os.path.join(
            django_settings.STATICFILES_DIRS[0] if django_settings.STATICFILES_DIRS else django_settings.STATIC_ROOT,
            'img', 'mkj_supacup_logo_official.jpg',
        )
        if os.path.exists(logo_path):
            try:
                logo = RLImage(logo_path, width=30 * mm, height=30 * mm)
                logo.hAlign = 'CENTER'
                elements.append(logo)
                elements.append(Spacer(1, 2 * mm))
            except Exception:
                pass

        header_style = ParagraphStyle(
            'Header', parent=styles['Normal'],
            fontSize=8, textColor=colors.HexColor('#004D1A'), alignment=1, spaceAfter=2,
        )
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Title'],
            fontSize=14, spaceAfter=4, alignment=1, textColor=colors.HexColor('#1B5E20'),
        )
        subtitle_style = ParagraphStyle(
            'Subtitle', parent=styles['Heading2'],
            fontSize=11, spaceAfter=2, alignment=1,
        )
        info_style = ParagraphStyle(
            'Info', parent=styles['Normal'],
            fontSize=9, alignment=1, spaceAfter=2,
        )

        elements.append(Paragraph("MKJ SUPA CUP — 4th Edition", header_style))
        elements.append(Paragraph("Match Day Squad Sheet", title_style))
        elements.append(Paragraph(
            f"{fixture.home_team.name} vs {fixture.away_team.name}",
            subtitle_style,
        ))

        # Match info
        match_date = fixture.match_date.strftime('%d %B %Y') if fixture.match_date else '—'
        kickoff = fixture.kickoff_time.strftime('%H:%M') if hasattr(fixture, 'kickoff_time') and fixture.kickoff_time else '—'
        venue_name = fixture.venue.name if fixture.venue else '—'
        comp_name = fixture.competition.name if fixture.competition else '—'

        elements.append(Paragraph(
            f"Competition: {comp_name} &nbsp;|&nbsp; Date: {match_date} &nbsp;|&nbsp; Kick-off: {kickoff} &nbsp;|&nbsp; Venue: {venue_name}",
            info_style,
        ))
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph(
            f"<b>Team:</b> {squad.team.name} &nbsp;&nbsp; <b>Formation:</b> {squad.formation or '—'} &nbsp;&nbsp; "
            f"<b>Kit:</b> {squad.get_kit_choice_display() if hasattr(squad, 'get_kit_choice_display') else squad.kit_choice or '—'}",
            info_style,
        ))
        elements.append(Paragraph(
            f"<b>Status:</b> ✅ Approved by Referee &nbsp;&nbsp; "
            f"<b>Approved:</b> {squad.reviewed_at.strftime('%d %B %Y %H:%M') if squad.reviewed_at else '—'}",
            info_style,
        ))
        elements.append(Spacer(1, 0.5 * cm))

        name_style_cell = ParagraphStyle('NameCell', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold')

        def _build_player_table(player_list, section_title):
            """Build a reportlab table for a list of SquadPlayers."""
            elements.append(Paragraph(f"{section_title} ({len(player_list)})", styles['Heading3']))
            if not player_list:
                elements.append(Paragraph("None", styles['Normal']))
                elements.append(Spacer(1, 0.3 * cm))
                return

            data = [['#', 'Photo', 'Name', 'Position', 'DOB', 'National ID']]
            for sp in player_list:
                p = sp.player
                photo_cell = ''
                if p.photo and hasattr(p.photo, 'path'):
                    try:
                        photo_path = p.photo.path
                        if os.path.exists(photo_path):
                            photo_cell = RLImage(photo_path, width=18 * mm, height=22 * mm)
                    except Exception:
                        pass

                dob_str = p.date_of_birth.strftime('%d/%m/%Y') if p.date_of_birth else '—'
                data.append([
                    str(sp.shirt_number),
                    photo_cell,
                    Paragraph(f"{p.last_name} {p.first_name}", name_style_cell),
                    p.get_position_display() if hasattr(p, 'get_position_display') else (p.position or '—'),
                    dob_str,
                    p.national_id_number or '—',
                ])

            col_widths = [1 * cm, 2.2 * cm, 4.5 * cm, 3 * cm, 2.8 * cm, 3 * cm]
            row_heights = [None] + [25 * mm] * len(player_list)
            tbl = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 2 * mm),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 2 * mm),
            ]))
            elements.append(tbl)
            elements.append(Spacer(1, 0.5 * cm))

        _build_player_table(starters, "Starting XI")
        _build_player_table(subs, "Substitutes")

        # Footer
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=1)
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph(
            f"Generated on {timezone.now().strftime('%d %B %Y at %H:%M')} — MKJ SUPA CUP CMS | Confidential — For authorised personnel only",
            footer_style,
        ))

        doc.build(elements)
        buffer.seek(0)

        team_name = squad.team.name.replace(' ', '_')
        filename = f"MKJ_SUPA_CUP_Squad_{team_name}_{match_date.replace(' ', '_')}.pdf"
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except ImportError:
        messages.error(request, 'PDF generation requires the reportlab package.')
        return redirect('dashboard')
