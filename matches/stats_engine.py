"""
MKJ SUPA CUP Matches - Stats Engine
Automatically updates pool standings and player statistics
when a match report is approved.
Supports sport-specific scoring: football, volleyball, basketball, handball.
"""
import logging
from django.db import transaction
from django.db.models import ExpressionWrapper, F, IntegerField, Sum
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)


def sort_pool_standings(pool_teams, sport_type=None):
    """
    Sort pool teams by the correct international criteria for each sport.
    - Football (FIFA):      Points, Goal Difference, Goals For
    - Volleyball (FIVB):    Points, Set Ratio (difference), Point Difference, Points For
    - Basketball (FIBA):    Points, Point Difference, Points For
    - Handball (IHF):       Points, Goal Difference, Goals For
    """
    from matches.models import get_sport_family
    family = get_sport_family(sport_type) if sport_type else "football"

    if family == "volleyball":
        return sorted(
            pool_teams,
            key=lambda pt: (pt.points, pt.set_difference, pt.goal_difference, pt.goals_for),
            reverse=True,
        )
    else:
        # Football, Basketball, Handball all use: Points → GD/PD → GF/PF
        return sorted(
            pool_teams,
            key=lambda pt: (pt.points, pt.goal_difference, pt.goals_for),
            reverse=True,
        )


def process_approved_report(report):
    """
    Master function: called when a MatchReport is approved.
    Updates pool standings + player statistics in one atomic transaction.
    """
    fixture = report.fixture
    with transaction.atomic():
        update_pool_standings(fixture, report)
        update_player_statistics(report)
        # For knockout matches, determine the winner
        if fixture.is_knockout:
            fixture.determine_winner()
            fixture.save(update_fields=["winner"])


def update_pool_standings(fixture, report=None):
    """
    Recalculate pool team standings after a completed fixture.
    Sport-aware: uses correct points system for each sport family.
    """
    from competitions.models import PoolTeam
    from matches.models import get_sport_family, SPORT_CONFIG

    pool = fixture.pool
    if not pool:
        return  # Knockout match or no pool assigned

    hs = fixture.home_score
    as_ = fixture.away_score
    if hs is None or as_ is None:
        return

    try:
        home_pt = PoolTeam.objects.get(pool=pool, team=fixture.home_team)
        away_pt = PoolTeam.objects.get(pool=pool, team=fixture.away_team)
    except PoolTeam.DoesNotExist:
        logger.warning(
            f"PoolTeam not found for fixture {fixture.id} "
            f"(home={fixture.home_team}, away={fixture.away_team}, pool={pool})"
        )
        return

    sport_family = get_sport_family(fixture.competition.sport_type)
    cfg = SPORT_CONFIG.get(sport_family, SPORT_CONFIG["football"])
    pts_cfg = cfg["standings_points"]

    home_pt.played += 1
    away_pt.played += 1
    home_pt.goals_for += hs
    home_pt.goals_against += as_
    away_pt.goals_for += as_
    away_pt.goals_against += hs

    if sport_family == "volleyball":
        # Volleyball uses set-score-based points (FIVB system)
        home_sets = report.home_sets if report else 0
        away_sets = report.away_sets if report else 0
        home_pt.sets_won += home_sets
        home_pt.sets_lost += away_sets
        away_pt.sets_won += away_sets
        away_pt.sets_lost += home_sets

        if home_sets > away_sets:
            home_pt.won += 1
            away_pt.lost += 1
            key_w = f"win_{home_sets}_{away_sets}"
            key_l = f"loss_{away_sets}_{home_sets}"
            home_pt.bonus_points += pts_cfg.get(key_w, 3)
            away_pt.bonus_points += pts_cfg.get(key_l, 0)
        else:
            away_pt.won += 1
            home_pt.lost += 1
            key_w = f"win_{away_sets}_{home_sets}"
            key_l = f"loss_{home_sets}_{away_sets}"
            away_pt.bonus_points += pts_cfg.get(key_w, 3)
            home_pt.bonus_points += pts_cfg.get(key_l, 0)

    elif sport_family in ("basketball_5x5", "basketball_3x3"):
        # Basketball: no draws; winner gets 2, loser gets 1 (FIBA)
        if hs > as_:
            home_pt.won += 1
            away_pt.lost += 1
            home_pt.bonus_points += pts_cfg.get("win", 2)
            away_pt.bonus_points += pts_cfg.get("loss", 1)
        else:
            away_pt.won += 1
            home_pt.lost += 1
            away_pt.bonus_points += pts_cfg.get("win", 2)
            home_pt.bonus_points += pts_cfg.get("loss", 1)

    elif sport_family == "handball":
        # Handball: 2 pts win, 1 pt draw, 0 pts loss (IHF)
        if hs > as_:
            home_pt.won += 1
            away_pt.lost += 1
        elif as_ > hs:
            away_pt.won += 1
            home_pt.lost += 1
        else:
            home_pt.drawn += 1
            away_pt.drawn += 1

    else:
        # Football: 3 pts win, 1 pt draw, 0 pts loss
        if hs > as_:
            home_pt.won += 1
            away_pt.lost += 1
        elif as_ > hs:
            away_pt.won += 1
            home_pt.lost += 1
        else:
            home_pt.drawn += 1
            away_pt.drawn += 1

    home_pt.save()
    away_pt.save()
    logger.info(f"Pool standings updated for fixture {fixture.id} (sport: {sport_family})")


def update_player_statistics(report):
    """
    Update PlayerStatistics records for all players involved in a match.
    Creates stat records on the fly if they don't exist yet.
    Sport-aware event tallying for football, volleyball, basketball, handball.
    """
    from matches.models import SquadSubmission, SquadPlayer, MatchEvent, PlayerStatistics, get_sport_family
    from teams.models import Player

    fixture = report.fixture
    competition = fixture.competition
    if not competition:
        return

    sport_family = get_sport_family(competition.sport_type)

    # Get squads for both teams
    squads = SquadSubmission.objects.filter(
        fixture=fixture, status="approved"
    ).prefetch_related("squad_players__player")

    # Track all players who appeared in this match
    players_in_match = {}  # player_id -> {team, is_starter, minutes}

    for squad in squads:
        for sp in squad.squad_players.all():
            if sp.player_id:
                players_in_match[sp.player_id] = {
                    "player": sp.player,
                    "team": squad.team,
                    "is_starter": sp.is_starter,
                }

    # Process match events
    events = report.events.select_related("player", "team").all()

    # Build event tallies per player
    event_tallies = {}  # player_id -> {goals, assists, yellows, reds, ...}
    for event in events:
        if not event.player_id:
            continue
        pid = event.player_id
        if pid not in event_tallies:
            event_tallies[pid] = {
                "goals": 0, "assists": 0, "yellow_cards": 0,
                "red_cards": 0, "penalties_scored": 0,
                "penalties_missed": 0, "own_goals": 0,
            }
        t = event_tallies[pid]
        et = event.event_type

        if sport_family == "football":
            if et == "goal":
                t["goals"] += 1
            elif et == "assist":
                t["assists"] += 1
            elif et == "yellow":
                t["yellow_cards"] += 1
            elif et in ("red", "second_yellow"):
                t["red_cards"] += 1
            elif et == "penalty":
                t["penalties_scored"] += 1
                t["goals"] += 1
            elif et == "penalty_miss":
                t["penalties_missed"] += 1
            elif et == "og":
                t["own_goals"] += 1

        elif sport_family == "volleyball":
            if et == "yellow":
                t["yellow_cards"] += 1
            elif et in ("red", "expulsion"):
                t["red_cards"] += 1

        elif sport_family in ("basketball_5x5", "basketball_3x3"):
            if et == "two_pointer":
                t["goals"] += 2
            elif et == "three_pointer":
                t["goals"] += 3
            elif et == "one_pointer":
                t["goals"] += 1
            elif et == "free_throw":
                t["goals"] += 1
                t["penalties_scored"] += 1
            elif et == "free_throw_miss":
                t["penalties_missed"] += 1
            elif et == "foul":
                t["yellow_cards"] += 1  # personal fouls mapped to yellow
            elif et in ("tech_foul", "unsportsmanlike", "disqualifying"):
                t["red_cards"] += 1

        elif sport_family == "handball":
            if et == "goal":
                t["goals"] += 1
            elif et == "assist":
                t["assists"] += 1
            elif et == "seven_m_goal":
                t["goals"] += 1
                t["penalties_scored"] += 1
            elif et == "seven_m_miss":
                t["penalties_missed"] += 1
            elif et == "yellow":
                t["yellow_cards"] += 1
            elif et in ("red", "blue_card"):
                t["red_cards"] += 1
            elif et == "two_min":
                t["yellow_cards"] += 1  # suspensions tracked as yellow equivalent

    # Determine clean sheet info (football/handball goalkeepers)
    home_conceded = report.away_score
    away_conceded = report.home_score

    # Update or create PlayerStatistics for each player
    for pid, info in players_in_match.items():
        player = info["player"]
        team = info["team"]
        is_starter = info["is_starter"]

        stats, created = PlayerStatistics.objects.get_or_create(
            player=player,
            competition=competition,
            defaults={"team": team}
        )
        if not created and stats.team != team:
            stats.team = team

        # Appearance
        stats.matches_played += 1
        if is_starter:
            stats.matches_started += 1
        else:
            stats.matches_sub += 1

        # Estimate minutes
        match_duration = getattr(report, "match_duration", 90) or 90
        if is_starter:
            stats.minutes_played += match_duration
        else:
            stats.minutes_played += match_duration // 2

        # Event-based stats
        tally = event_tallies.get(pid, {})
        stats.goals += tally.get("goals", 0)
        stats.assists += tally.get("assists", 0)
        stats.yellow_cards += tally.get("yellow_cards", 0)
        stats.red_cards += tally.get("red_cards", 0)
        stats.penalties_scored += tally.get("penalties_scored", 0)
        stats.penalties_missed += tally.get("penalties_missed", 0)
        stats.own_goals += tally.get("own_goals", 0)

        # Goalkeeper clean sheet check (football & handball)
        if sport_family in ("football", "handball") and player.position == "GK" and is_starter:
            if team == fixture.home_team:
                conceded = home_conceded or 0
            else:
                conceded = away_conceded or 0
            stats.goals_conceded += conceded
            if conceded == 0:
                stats.clean_sheets += 1

        stats.save()

    logger.info(
        f"Player statistics updated for {len(players_in_match)} players "
        f"(fixture {fixture.id}, competition {competition.name}, sport: {sport_family})"
    )


def recalculate_pool_standings(pool):
    """
    Full recalculation of pool standings from scratch.
    Sport-aware: uses correct points system.
    """
    from competitions.models import PoolTeam, Fixture, FixtureStatus
    from matches.models import MatchReport, get_sport_family, SPORT_CONFIG

    # Reset all standings
    PoolTeam.objects.filter(pool=pool).update(
        played=0, won=0, drawn=0, lost=0,
        goals_for=0, goals_against=0,
        sets_won=0, sets_lost=0, bonus_points=0,
    )

    # Replay all completed fixtures in this pool
    completed = Fixture.objects.filter(
        pool=pool, status=FixtureStatus.COMPLETED
    ).select_related("home_team", "away_team", "competition")

    for fixture in completed:
        if fixture.home_score is None or fixture.away_score is None:
            continue
        try:
            report = MatchReport.objects.get(fixture=fixture, status="approved")
        except MatchReport.DoesNotExist:
            report = None
        update_pool_standings(fixture, report)

    logger.info(f"Pool standings fully recalculated for {pool}")


def recalculate_player_stats(competition):
    """
    Full recalculation of player statistics for a competition from scratch.
    Wipes and rebuilds all stats from approved match reports.
    """
    from matches.models import MatchReport, PlayerStatistics

    # Delete existing stats for this competition
    PlayerStatistics.objects.filter(competition=competition).delete()

    # Replay all approved reports
    approved_reports = MatchReport.objects.filter(
        fixture__competition=competition,
        status="approved"
    ).select_related("fixture__competition", "fixture__home_team", "fixture__away_team")

    for report in approved_reports:
        update_player_statistics(report)

    logger.info(f"Player statistics fully recalculated for {competition.name}")


def get_top_scorers(competition, limit=20):
    """Return top scorers for a competition."""
    from matches.models import PlayerStatistics
    return PlayerStatistics.objects.filter(
        competition=competition, goals__gt=0
    ).select_related("player", "team").order_by("-goals", "-assists")[:limit]


def get_top_assisters(competition, limit=20):
    """Return top assist providers for a competition."""
    from matches.models import PlayerStatistics
    return PlayerStatistics.objects.filter(
        competition=competition, assists__gt=0
    ).select_related("player", "team").order_by("-assists", "-goals")[:limit]


def get_disciplinary_table(competition, limit=20):
    """Return most-carded players for a competition."""
    from matches.models import PlayerStatistics
    from django.db.models import F
    return PlayerStatistics.objects.filter(
        competition=competition
    ).annotate(
        total_cards=F("yellow_cards") + F("red_cards")
    ).filter(total_cards__gt=0).select_related(
        "player", "team"
    ).order_by("-red_cards", "-yellow_cards")[:limit]


def get_clean_sheet_leaders(competition, limit=10):
    """Return goalkeepers with most clean sheets."""
    from matches.models import PlayerStatistics
    return PlayerStatistics.objects.filter(
        competition=competition, clean_sheets__gt=0,
        player__position="GK"
    ).select_related("player", "team").order_by("-clean_sheets")[:limit]


def get_fair_play_table(competition, limit=20):
    """
    Return teams ranked by fewest sanctions.

    Fair play points formula:
    - Yellow card: 1 point
    - Red card: 3 points
    Lower total is better.
    """
    from matches.models import PlayerStatistics

    return (
        PlayerStatistics.objects.filter(competition=competition)
        .values('team__id', 'team__name')
        .annotate(
            yellow_total=Coalesce(Sum('yellow_cards'), 0),
            red_total=Coalesce(Sum('red_cards'), 0),
        )
        .annotate(
            fair_play_points=ExpressionWrapper(
                F('yellow_total') + (F('red_total') * 3),
                output_field=IntegerField(),
            )
        )
        .order_by('fair_play_points', 'red_total', 'team__name')[:limit]
    )
