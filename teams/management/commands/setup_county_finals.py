"""
Management command to set up the MKJ SUPA CUP County Finals tournament data.
Creates disciplines, teams, pools, and group-stage fixtures for all 6 subcounties.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date, time
from itertools import combinations

from competitions.models import Competition, Pool, PoolTeam, Fixture
from teams.models import CountyRegistration, CountyDiscipline, Team
from accounts.models import MAKUENI_SUBCOUNTY_WARDS


SPORT_GENDER_MAP = {
    'football_men': 'men', 'football_women': 'women',
    'volleyball_men': 'men', 'volleyball_women': 'women',
    'basketball_men': 'men', 'basketball_women': 'women',
    'basketball_3x3_men': 'men', 'basketball_3x3_women': 'women',
    'handball_men': 'men', 'handball_women': 'women',
}

SPORT_TYPES = list(SPORT_GENDER_MAP.keys())


class Command(BaseCommand):
    help = 'Set up MKJ SUPA CUP County Finals: teams, pools, fixtures for all 6 subcounties'

    def handle(self, *args, **options):
        subcounties = sorted(MAKUENI_SUBCOUNTY_WARDS.keys())
        self.stdout.write(f"Subcounties: {subcounties}")

        reg = CountyRegistration.objects.filter(county='Makueni', status='approved').first()
        if not reg:
            self.stderr.write("No approved Makueni registration found!")
            return

        # Step 1: Fix competition settings
        self.stdout.write("\n--- Fixing competition settings ---")
        with transaction.atomic():
            for comp in Competition.objects.all():
                comp.max_teams = 6
                comp.teams_per_group = 3
                comp.qualify_from_group = 2
                comp.status = 'group_stage'
                if comp.sport_type in SPORT_GENDER_MAP:
                    comp.gender = SPORT_GENDER_MAP[comp.sport_type]
                comp.save()
                self.stdout.write(f"  Fixed: {comp.name}")

        # Step 2: Create disciplines + teams for all subcounties x sports
        self.stdout.write("\n--- Creating disciplines & teams ---")
        created_disc = 0
        with transaction.atomic():
            for sc in subcounties:
                for sport in SPORT_TYPES:
                    disc, created = CountyDiscipline.objects.get_or_create(
                        registration=reg,
                        sport_type=sport,
                        sub_county=sc,
                    )
                    if created:
                        created_disc += 1
                    disc.ensure_linked_team()
            self.stdout.write(f"  Created {created_disc} new disciplines")
            self.stdout.write(f"  Total disciplines: {CountyDiscipline.objects.count()}")
            self.stdout.write(f"  Total teams: {Team.objects.count()}")

        # Step 3: Link teams to competitions
        self.stdout.write("\n--- Linking teams to competitions ---")
        linked = 0
        with transaction.atomic():
            for comp in Competition.objects.all():
                teams = Team.objects.filter(
                    sport_type=comp.sport_type, competition__isnull=True
                )
                for team in teams:
                    team.competition = comp
                    team.save(update_fields=['competition'])
                    linked += 1
        self.stdout.write(f"  Linked {linked} teams to competitions")

        # Step 4: Create pools (Pool A, Pool B - 3 teams each)
        self.stdout.write("\n--- Creating pools ---")
        with transaction.atomic():
            for comp in Competition.objects.all():
                teams = list(
                    Team.objects.filter(competition=comp).order_by('sub_county')
                )
                if len(teams) != 6:
                    self.stderr.write(
                        f"  WARNING: {comp.name} has {len(teams)} teams, expected 6"
                    )
                    continue

                pool_a, _ = Pool.objects.get_or_create(
                    competition=comp, name='Pool A'
                )
                pool_b, _ = Pool.objects.get_or_create(
                    competition=comp, name='Pool B'
                )

                for team in teams[:3]:
                    PoolTeam.objects.get_or_create(pool=pool_a, team=team)
                for team in teams[3:]:
                    PoolTeam.objects.get_or_create(pool=pool_b, team=team)

                a_names = [t.sub_county for t in teams[:3]]
                b_names = [t.sub_county for t in teams[3:]]
                self.stdout.write(
                    f"  {comp.get_sport_type_display()}: A={a_names}, B={b_names}"
                )

        self.stdout.write(f"  Total pools: {Pool.objects.count()}")

        # Step 5: Generate group stage fixtures
        self.stdout.write("\n--- Generating fixtures ---")
        fixture_dates = [date(2026, 4, 1), date(2026, 4, 2)]
        kickoff_times = [time(9, 0), time(11, 0), time(14, 0), time(16, 0)]
        created_fixtures = 0

        with transaction.atomic():
            comps = Competition.objects.all().order_by('sport_type')
            for comp in comps:
                Fixture.objects.filter(competition=comp).delete()

                for pool in Pool.objects.filter(competition=comp):
                    pt_list = pool.pool_teams.select_related('team').all()
                    teams = [pt.team for pt in pt_list]
                    matchups = list(combinations(teams, 2))

                    for i, (home, away) in enumerate(matchups):
                        kick = kickoff_times[i % len(kickoff_times)]
                        match_date = fixture_dates[0] if i < 2 else fixture_dates[1]
                        Fixture.objects.create(
                            competition=comp,
                            pool=pool,
                            home_team=home,
                            away_team=away,
                            match_date=match_date,
                            kickoff_time=kick,
                            status='scheduled',
                            round_number=i + 1,
                            is_knockout=False,
                        )
                        created_fixtures += 1

        self.stdout.write(f"  Created {created_fixtures} fixtures")
        self.stdout.write(f"  Total fixtures: {Fixture.objects.count()}")

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\nDONE: {Competition.objects.count()} competitions, "
            f"{Team.objects.count()} teams, {Pool.objects.count()} pools, "
            f"{Fixture.objects.count()} fixtures"
        ))
