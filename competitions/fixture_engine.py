"""
MKJ SUPA CUP Competitions - Fixture Generation Engine
Generates group-stage round-robin and knockout-bracket fixtures.
"""
import logging
from itertools import combinations
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_group_fixtures(competition, start_date, kickoff_time, interval_days=7,
                            venue=None, created_by=None):
    """
    Generate round-robin fixtures for every pool in a competition.
    Each team plays every other team in its pool exactly once.

    Returns the list of created Fixture objects.
    """
    from competitions.models import Pool, PoolTeam, Fixture

    pools = Pool.objects.filter(competition=competition).prefetch_related('pool_teams__team')
    if not pools.exists():
        raise ValueError("No pools found. Create pools and assign teams first.")

    created_fixtures = []
    current_date = start_date
    round_number = 1

    with transaction.atomic():
        for pool in pools:
            teams = [pt.team for pt in pool.pool_teams.all()]
            if len(teams) < 2:
                continue

            matchups = list(combinations(teams, 2))
            for home, away in matchups:
                fixture = Fixture.objects.create(
                    competition=competition,
                    pool=pool,
                    home_team=home,
                    away_team=away,
                    venue=venue,
                    match_date=current_date,
                    kickoff_time=kickoff_time,
                    status='pending',
                    round_number=round_number,
                    is_knockout=False,
                    created_by=created_by,
                )
                created_fixtures.append(fixture)
                round_number += 1
                # Stagger fixtures across dates
                if round_number % 3 == 0:
                    current_date += timedelta(days=interval_days)

    logger.info(
        f"Generated {len(created_fixtures)} group-stage fixtures for {competition.name}"
    )
    return created_fixtures


def generate_knockout_fixtures(competition, num_teams, start_date, kickoff_time,
                               interval_days=3, venue=None, created_by=None):
    """
    Generate blank knockout bracket fixtures for a competition.
    Creates placeholder fixtures from Round of N down to the Final.

    num_teams must be a power of 2 (4, 8, 16, 32).
    Teams are NOT assigned - they are filled in as group stage completes
    or manually by the Competition Manager.
    """
    from competitions.models import Fixture, KnockoutRound

    ROUND_MAP = {
        32: KnockoutRound.ROUND_OF_32,
        16: KnockoutRound.ROUND_OF_16,
        8:  KnockoutRound.QUARTERFINAL,
        4:  KnockoutRound.SEMIFINAL,
        2:  KnockoutRound.FINAL,
    }

    # Validate num_teams
    valid_sizes = [4, 8, 16, 32]
    if num_teams not in valid_sizes:
        raise ValueError(f"Number of teams must be one of {valid_sizes}")

    # We need a placeholder team for TBD slots
    from teams.models import Team
    tbd_home, _ = Team.objects.get_or_create(
        name="TBD (Home)",
        defaults={"county": "TBD", "status": "pending"}
    )
    tbd_away, _ = Team.objects.get_or_create(
        name="TBD (Away)",
        defaults={"county": "TBD", "status": "pending"}
    )

    created_fixtures = []
    current_date = start_date
    current_size = num_teams

    with transaction.atomic():
        while current_size >= 2:
            round_key = ROUND_MAP.get(current_size)
            if not round_key:
                break

            num_matches = current_size // 2

            # Add 3rd place playoff before final
            if current_size == 2:
                # Third place playoff
                tp = Fixture.objects.create(
                    competition=competition,
                    home_team=tbd_home,
                    away_team=tbd_away,
                    venue=venue,
                    match_date=current_date,
                    kickoff_time=kickoff_time,
                    status='pending',
                    is_knockout=True,
                    knockout_round=KnockoutRound.THIRD_PLACE,
                    bracket_position=1,
                    created_by=created_by,
                )
                created_fixtures.append(tp)

            for pos in range(1, num_matches + 1):
                fixture = Fixture.objects.create(
                    competition=competition,
                    home_team=tbd_home,
                    away_team=tbd_away,
                    venue=venue,
                    match_date=current_date,
                    kickoff_time=kickoff_time,
                    status='pending',
                    is_knockout=True,
                    knockout_round=round_key,
                    bracket_position=pos,
                    created_by=created_by,
                )
                created_fixtures.append(fixture)

            current_date += timedelta(days=interval_days)
            current_size //= 2

    logger.info(
        f"Generated {len(created_fixtures)} knockout fixtures for {competition.name}"
    )
    return created_fixtures


def generate_all_fixtures(competition, start_date, kickoff_time,
                          group_interval=7, knockout_interval=3,
                          knockout_teams=None, venue=None, created_by=None):
    """
    Generate all fixtures for a competition based on its format.
    - GROUP_STAGE: round-robin only
    - KNOCKOUT: knockout bracket only
    - GROUP_AND_KNOCKOUT: round-robin + knockout bracket
    """
    from competitions.models import CompetitionFormat, Pool

    created = []

    if competition.has_group_stage:
        group_fixtures = generate_group_fixtures(
            competition, start_date, kickoff_time,
            interval_days=group_interval, venue=venue, created_by=created_by,
        )
        created.extend(group_fixtures)

        # Estimate knockout start date after group stage
        if group_fixtures:
            last_group_date = max(f.match_date for f in group_fixtures)
            ko_start = last_group_date + timedelta(days=knockout_interval)
        else:
            ko_start = start_date
    else:
        ko_start = start_date

    if competition.has_knockout:
        # Determine number of knockout teams
        if knockout_teams is None:
            if competition.has_group_stage:
                pools = Pool.objects.filter(competition=competition)
                knockout_teams = pools.count() * competition.qualify_from_group
            else:
                knockout_teams = competition.max_teams

        # Round down to nearest power of 2
        for size in [32, 16, 8, 4]:
            if knockout_teams >= size:
                knockout_teams = size
                break
        else:
            knockout_teams = 4

        ko_fixtures = generate_knockout_fixtures(
            competition, knockout_teams, ko_start, kickoff_time,
            interval_days=knockout_interval, venue=venue, created_by=created_by,
        )
        created.extend(ko_fixtures)

    return created
