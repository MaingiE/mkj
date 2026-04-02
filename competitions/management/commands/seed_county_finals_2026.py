"""
Management command: Seed MKJ Supa Cup County Finals 2026 â€” Day 1 results
and Day 2 semi-final fixtures.

Usage:
    python manage.py seed_county_finals_2026
    python manage.py seed_county_finals_2026 --dry-run
"""
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


# â”€â”€ Sub-county name mapping (short â†’ canonical) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SC = {
    'mkn': 'Makueni',
    'makueni': 'Makueni',
    'mbooni': 'Mbooni',
    'ke': 'Kibwezi East',
    'kbz east': 'Kibwezi East',
    'kibwezi east': 'Kibwezi East',
    'kw': 'Kibwezi West',
    'kbz west': 'Kibwezi West',
    'kibwezi west': 'Kibwezi West',
    'kaiti': 'Kaiti',
    'kilome': 'Kilome',
}

TODAY = datetime.date(2026, 4, 1)
TOMORROW = datetime.date(2026, 4, 2)


class Command(BaseCommand):
    help = 'Seed MKJ Supa Cup County Finals 2026 â€” Day 1 results & Day 2 semi-finals'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print what would be done without writing to DB')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        from competitions.models import (
            Competition, Pool, PoolTeam, Fixture, FixtureStatus,
            KnockoutRound, SportType, CompetitionFormat, CompetitionStatus,
            AgeGroup, GenderChoice, Venue,
        )
        from teams.models import Team, County, TeamStatus
        from matches.stats_engine import recalculate_pool_standings

        # â”€â”€ Venue â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        venue, _ = Venue.objects.get_or_create(
            name__iexact='County Finals Venue',
            defaults={'name': 'County Finals Venue', 'county': 'Makueni', 'city': 'Wote'},
        )

        # â”€â”€ County â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        makueni_county, _ = County.objects.get_or_create(
            name='Makueni', defaults={'code': 'MAK', 'capital': 'Wote'},
        )

        # â”€â”€ Helper: ensure team exists â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def ensure_team(sub_county, sport_type):
            label = dict(SportType.choices).get(sport_type, sport_type)
            team_name = f"{sub_county} {label}"
            team, created = Team.objects.get_or_create(
                name=team_name,
                defaults={
                    'county': makueni_county,
                    'sub_county': sub_county,
                    'sport_type': sport_type,
                    'status': TeamStatus.REGISTERED,
                    'contact_phone': '+254700000000',
                },
            )
            if team.status != TeamStatus.REGISTERED:
                team.status = TeamStatus.REGISTERED
                team.save(update_fields=['status'])
            return team

        # â”€â”€ Helper: ensure competition exists â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def ensure_comp(sport_type):
            gender_map = {'men': GenderChoice.MEN, 'women': GenderChoice.WOMEN}
            gender = GenderChoice.MEN
            for k, v in gender_map.items():
                if k in sport_type:
                    gender = v
                    break
            label = dict(SportType.choices).get(sport_type, sport_type)
            comp, created = Competition.objects.get_or_create(
                sport_type=sport_type, season='2026',
                defaults={
                    'name': f'MKJ SUPA CUP 2026 {label}',
                    'gender': gender,
                    'format_type': CompetitionFormat.GROUP_AND_KNOCKOUT,
                    'age_group': AgeGroup.OPEN,
                    'status': CompetitionStatus.GROUP_STAGE,
                    'start_date': TODAY,
                    'end_date': TODAY + datetime.timedelta(days=7),
                    'max_teams': 12,
                    'teams_per_group': 3,
                    'qualify_from_group': 2,
                },
            )
            # Force status to GROUP_STAGE if competition already existed
            if not created and comp.status == CompetitionStatus.UPCOMING:
                comp.status = CompetitionStatus.GROUP_STAGE
                comp.save(update_fields=['status'])
            return comp

        # â”€â”€ Helper: create pool + teams â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def ensure_pool(comp, pool_name, subcounties):
            pool, _ = Pool.objects.get_or_create(
                competition=comp, name=pool_name,
                defaults={'venue': venue},
            )
            teams = []
            for sc in subcounties:
                team = ensure_team(sc, comp.sport_type)
                if not PoolTeam.objects.filter(pool=pool, team=team).exists():
                    PoolTeam.objects.create(pool=pool, team=team)
                teams.append(team)
            return pool, teams

        # â”€â”€ Helper: create completed fixture â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def create_result(comp, pool, home_sc, away_sc, home_score, away_score,
                          kickoff='10:00', is_knockout=False, ko_round='', bracket_pos=None):
            home = ensure_team(home_sc, comp.sport_type)
            away = ensure_team(away_sc, comp.sport_type)
            fixture, created = Fixture.objects.get_or_create(
                competition=comp,
                home_team=home,
                away_team=away,
                pool=pool,
                is_knockout=is_knockout,
                defaults={
                    'match_date': TODAY,
                    'kickoff_time': datetime.datetime.strptime(kickoff, '%H:%M').time(),
                    'venue': venue,
                    'status': FixtureStatus.COMPLETED,
                    'home_score': home_score,
                    'away_score': away_score,
                    'knockout_round': ko_round,
                    'bracket_position': bracket_pos,
                },
            )
            if not created and (fixture.home_score != home_score or fixture.away_score != away_score):
                fixture.home_score = home_score
                fixture.away_score = away_score
                fixture.status = FixtureStatus.COMPLETED
                fixture.save(update_fields=['home_score', 'away_score', 'status', 'updated_at'])
            if is_knockout:
                fixture.determine_winner()
                fixture.save(update_fields=['winner'])
            return fixture

        # â”€â”€ Helper: create semi-final fixture â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def create_semi(comp, home_sc, away_sc, bracket_pos, kickoff='09:00'):
            home = ensure_team(home_sc, comp.sport_type)
            away = ensure_team(away_sc, comp.sport_type)
            fixture, created = Fixture.objects.get_or_create(
                competition=comp,
                home_team=home,
                away_team=away,
                is_knockout=True,
                knockout_round=KnockoutRound.SEMIFINAL,
                defaults={
                    'match_date': TOMORROW,
                    'kickoff_time': datetime.datetime.strptime(kickoff, '%H:%M').time(),
                    'venue': venue,
                    'status': FixtureStatus.PENDING,
                    'bracket_position': bracket_pos,
                },
            )
            return fixture, created

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN â€” no changes will be made'))
            self.stdout.write('Would create competitions, pools, fixtures for:')
            self.stdout.write('  Basketball 3x3 Men & Women')
            self.stdout.write('  Basketball 5x5 Men & Women')
            self.stdout.write('  Handball Men & Women')
            self.stdout.write('  Volleyball Men & Women')
            return

        with transaction.atomic():
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            #  BASKETBALL 3x3 â€” MEN
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            comp = ensure_comp(SportType.BASKETBALL_3X3_MEN)
            self.stdout.write(f'\n=== {comp.name} ===')

            pool_a, _ = ensure_pool(comp, 'Pool A', ['Makueni', 'Mbooni', 'Kibwezi East'])
            pool_b, _ = ensure_pool(comp, 'Pool B', ['Kaiti', 'Kilome', 'Kibwezi West'])

            # Pool A results
            create_result(comp, pool_a, 'Makueni', 'Mbooni', 5, 13)
            create_result(comp, pool_a, 'Kibwezi East', 'Makueni', 9, 8)
            create_result(comp, pool_a, 'Mbooni', 'Kibwezi East', 10, 8)

            # Pool B results
            create_result(comp, pool_b, 'Kaiti', 'Kilome', 6, 8)
            create_result(comp, pool_b, 'Kibwezi West', 'Kaiti', 17, 10)
            create_result(comp, pool_b, 'Kilome', 'Kibwezi West', 3, 13)

            recalculate_pool_standings(pool_a)
            recalculate_pool_standings(pool_b)

            # Semis: Mbooni vs Kilome, KW vs KE
            create_semi(comp, 'Mbooni', 'Kilome', 1)
            create_semi(comp, 'Kibwezi West', 'Kibwezi East', 2)
            self.stdout.write(self.style.SUCCESS('  âœ“ Pool results + semis created'))

            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            #  BASKETBALL 3x3 â€” WOMEN
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            comp = ensure_comp(SportType.BASKETBALL_3X3_WOMEN)
            self.stdout.write(f'\n=== {comp.name} ===')

            pool_a, _ = ensure_pool(comp, 'Pool A', ['Mbooni', 'Kaiti'])
            pool_b, _ = ensure_pool(comp, 'Pool B', ['Kibwezi West', 'Makueni', 'Kibwezi East'])

            # Pool A: Mbooni 13 - Kaiti 1, Kilome has no 3x3 team
            create_result(comp, pool_a, 'Mbooni', 'Kaiti', 13, 1)

            # Pool B
            create_result(comp, pool_b, 'Kibwezi West', 'Makueni', 9, 5)
            create_result(comp, pool_b, 'Kibwezi East', 'Kibwezi West', 4, 6)
            create_result(comp, pool_b, 'Makueni', 'Kibwezi East', 14, 6)

            recalculate_pool_standings(pool_a)
            recalculate_pool_standings(pool_b)

            # Semis: Mbooni vs Mkn, KW vs Kaiti
            create_semi(comp, 'Mbooni', 'Makueni', 1)
            create_semi(comp, 'Kibwezi West', 'Kaiti', 2)
            self.stdout.write(self.style.SUCCESS('  âœ“ Pool results + semis created'))

            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            #  BASKETBALL 5x5 â€” MEN
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            comp = ensure_comp(SportType.BASKETBALL_MEN)
            self.stdout.write(f'\n=== {comp.name} ===')

            pool_a, _ = ensure_pool(comp, 'Pool A', ['Kilome', 'Makueni', 'Kibwezi East'])
            pool_b, _ = ensure_pool(comp, 'Pool B', ['Kibwezi West', 'Mbooni', 'Kaiti'])

            # Pool A
            create_result(comp, pool_a, 'Kilome', 'Makueni', 28, 37)
            create_result(comp, pool_a, 'Kibwezi East', 'Kilome', 35, 28)
            create_result(comp, pool_a, 'Makueni', 'Kibwezi East', 40, 33)

            # Pool B
            create_result(comp, pool_b, 'Kibwezi West', 'Mbooni', 50, 34)
            create_result(comp, pool_b, 'Kaiti', 'Kibwezi West', 33, 38)
            create_result(comp, pool_b, 'Mbooni', 'Kaiti', 33, 39)

            recalculate_pool_standings(pool_a)
            recalculate_pool_standings(pool_b)

            # Semis: Makueni vs Kaiti, KW vs KE
            create_semi(comp, 'Makueni', 'Kaiti', 1)
            create_semi(comp, 'Kibwezi West', 'Kibwezi East', 2)
            self.stdout.write(self.style.SUCCESS('  âœ“ Pool results + semis created'))

            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            #  BASKETBALL 5x5 â€” WOMEN
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            comp = ensure_comp(SportType.BASKETBALL_WOMEN)
            self.stdout.write(f'\n=== {comp.name} ===')

            pool_a, _ = ensure_pool(comp, 'Pool A', ['Makueni', 'Kibwezi West', 'Mbooni'])
            pool_b, _ = ensure_pool(comp, 'Pool B', ['Kaiti', 'Kibwezi East', 'Kilome'])

            # Pool A
            create_result(comp, pool_a, 'Makueni', 'Kibwezi West', 21, 51)
            create_result(comp, pool_a, 'Makueni', 'Mbooni', 30, 36)
            create_result(comp, pool_a, 'Kibwezi West', 'Mbooni', 45, 26)

            # Pool B
            create_result(comp, pool_b, 'Kaiti', 'Kibwezi East', 11, 55)
            create_result(comp, pool_b, 'Kilome', 'Kaiti', 24, 12)
            # KE vs Kilome â€” tomorrow at 8am (not yet played)
            home = ensure_team('Kibwezi East', comp.sport_type)
            away = ensure_team('Kilome', comp.sport_type)
            Fixture.objects.get_or_create(
                competition=comp, home_team=home, away_team=away,
                pool=Pool.objects.get(competition=comp, name='Pool B'),
                is_knockout=False,
                defaults={
                    'match_date': TOMORROW,
                    'kickoff_time': datetime.time(8, 0),
                    'venue': venue,
                    'status': FixtureStatus.PENDING,
                },
            )

            recalculate_pool_standings(pool_a)
            recalculate_pool_standings(pool_b)
            self.stdout.write(self.style.SUCCESS('  âœ“ Pool results created (KE vs Kilome pending for tomorrow 8am)'))

            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            #  HANDBALL â€” MEN (BOYS)
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            comp = ensure_comp(SportType.HANDBALL_MEN)
            self.stdout.write(f'\n=== {comp.name} ===')

            pool_a, _ = ensure_pool(comp, 'Pool A', ['Kilome', 'Mbooni', 'Kibwezi West'])
            pool_b, _ = ensure_pool(comp, 'Pool B', ['Kibwezi East', 'Kaiti', 'Makueni'])

            # Pool A
            create_result(comp, pool_a, 'Kilome', 'Mbooni', 20, 11)
            create_result(comp, pool_a, 'Kibwezi West', 'Kilome', 11, 22)
            create_result(comp, pool_a, 'Mbooni', 'Kibwezi West', 16, 21)

            # Pool B
            create_result(comp, pool_b, 'Kibwezi East', 'Kaiti', 24, 21)
            create_result(comp, pool_b, 'Makueni', 'Kibwezi East', 14, 14)
            create_result(comp, pool_b, 'Kaiti', 'Makueni', 19, 24)

            recalculate_pool_standings(pool_a)
            recalculate_pool_standings(pool_b)

            # Semis: Kilome (A1) vs KE (B2), Makueni (B1) vs KW (A2)
            create_semi(comp, 'Kilome', 'Kibwezi East', 1, '09:00')
            create_semi(comp, 'Makueni', 'Kibwezi West', 2, '09:00')
            self.stdout.write(self.style.SUCCESS('  âœ“ Pool results + semis created'))

            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            #  HANDBALL â€” WOMEN (LADIES)
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            comp = ensure_comp(SportType.HANDBALL_WOMEN)
            self.stdout.write(f'\n=== {comp.name} ===')

            pool_a, _ = ensure_pool(comp, 'Pool A', ['Kaiti', 'Mbooni', 'Kibwezi West'])
            pool_b, _ = ensure_pool(comp, 'Pool B', ['Kilome', 'Makueni', 'Kibwezi East'])

            # Pool A
            create_result(comp, pool_a, 'Kaiti', 'Mbooni', 22, 5)
            create_result(comp, pool_a, 'Kibwezi West', 'Kaiti', 17, 13)
            create_result(comp, pool_a, 'Mbooni', 'Kibwezi West', 3, 17)

            # Pool B
            create_result(comp, pool_b, 'Kilome', 'Makueni', 14, 28)
            create_result(comp, pool_b, 'Kibwezi East', 'Kilome', 28, 14)
            # Mkn vs KBZ East â€” abandoned at 6th min 2nd half, to be continued 14 mins tomorrow 8am
            home = ensure_team('Makueni', comp.sport_type)
            away = ensure_team('Kibwezi East', comp.sport_type)
            Fixture.objects.get_or_create(
                competition=comp, home_team=home, away_team=away,
                pool=Pool.objects.get(competition=comp, name='Pool B'),
                is_knockout=False,
                defaults={
                    'match_date': TOMORROW,
                    'kickoff_time': datetime.time(8, 0),
                    'venue': venue,
                    'status': FixtureStatus.PENDING,
                },
            )

            recalculate_pool_standings(pool_a)
            recalculate_pool_standings(pool_b)
            self.stdout.write(self.style.SUCCESS('  âœ“ Pool results created (Mkn vs KE abandoned, continues tomorrow 8am)'))

            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            #  VOLLEYBALL â€” MEN
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            comp = ensure_comp(SportType.VOLLEYBALL_MEN)
            self.stdout.write(f'\n=== {comp.name} ===')

            pool_a, _ = ensure_pool(comp, 'Pool A', ['Makueni', 'Mbooni', 'Kilome'])
            pool_b, _ = ensure_pool(comp, 'Pool B', ['Kaiti', 'Kibwezi West', 'Kibwezi East'])

            # Pool A: Volleyball â€” using set wins (3-0 = W, total sets in GF/GA)
            # Makueni vs Mbooni 3-0
            create_result(comp, pool_a, 'Makueni', 'Mbooni', 3, 0)
            # Kilome vs Makueni 0-3
            create_result(comp, pool_a, 'Kilome', 'Makueni', 0, 3)
            # Mbooni vs Kilome 3-1
            create_result(comp, pool_a, 'Mbooni', 'Kilome', 3, 1)

            # Pool B
            # Kaiti vs KBZ West 0-3
            create_result(comp, pool_b, 'Kaiti', 'Kibwezi West', 0, 3)
            # KBZ East vs Kaiti 3-0
            create_result(comp, pool_b, 'Kibwezi East', 'Kaiti', 3, 0)
            # KBZ West vs KBZ East 3-2
            create_result(comp, pool_b, 'Kibwezi West', 'Kibwezi East', 3, 2)

            recalculate_pool_standings(pool_a)
            recalculate_pool_standings(pool_b)

            # Semis: Makueni vs KBZ East 9am, KBZ West vs Mbooni 9am
            create_semi(comp, 'Makueni', 'Kibwezi East', 1, '09:00')
            create_semi(comp, 'Kibwezi West', 'Mbooni', 2, '09:00')
            self.stdout.write(self.style.SUCCESS('  âœ“ Pool results + semis created'))

            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            #  VOLLEYBALL â€” WOMEN
            # â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
            comp = ensure_comp(SportType.VOLLEYBALL_WOMEN)
            self.stdout.write(f'\n=== {comp.name} ===')

            pool_a, _ = ensure_pool(comp, 'Pool A', ['Kaiti', 'Kilome', 'Kibwezi West'])
            pool_b, _ = ensure_pool(comp, 'Pool B', ['Mbooni', 'Kibwezi East', 'Makueni'])

            # Pool A
            # Kaiti vs Kilome 1-3
            create_result(comp, pool_a, 'Kaiti', 'Kilome', 1, 3)
            # KBZ West vs Kaiti 3-0
            create_result(comp, pool_a, 'Kibwezi West', 'Kaiti', 3, 0)
            # Kilome vs KBZ West 2-3
            create_result(comp, pool_a, 'Kilome', 'Kibwezi West', 2, 3)

            # Pool B
            # Mbooni vs KBZ East 0-3
            create_result(comp, pool_b, 'Mbooni', 'Kibwezi East', 0, 3)
            # KBZ East vs Makueni 3-0
            create_result(comp, pool_b, 'Kibwezi East', 'Makueni', 3, 0)
            # Makueni vs Mbooni 3-2
            create_result(comp, pool_b, 'Makueni', 'Mbooni', 3, 2)

            recalculate_pool_standings(pool_a)
            recalculate_pool_standings(pool_b)

            # Semis: KBZ West vs Makueni 9am, KBZ East vs Kilome 9am
            create_semi(comp, 'Kibwezi West', 'Makueni', 1, '09:00')
            create_semi(comp, 'Kibwezi East', 'Kilome', 2, '09:00')
            self.stdout.write(self.style.SUCCESS('  âœ“ Pool results + semis created'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('â•' * 60))
        self.stdout.write(self.style.SUCCESS('All Day 1 results seeded & Day 2 semi-finals created!'))
        self.stdout.write(self.style.SUCCESS('â•' * 60))
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('  1. Basketball 5x5 Women: KE vs Kilome â€” play tomorrow 8am, then create semis')
        self.stdout.write('  2. Handball Women: Mkn vs KE â€” continue 14 mins tomorrow 8am, then create semis')
        self.stdout.write('  3. All other sports: Semi-finals are ready for Day 2')
        self.stdout.write('  4. Use coordinator portal Live Match to run semi-finals in real-time')

