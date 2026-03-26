"""
Management command: wipe_data
-------------------------------
Wipes ALL competition, match, team, player, referee, news, and appeal data
from the database so the system can start fresh for a new season.

Superuser / staff accounts are preserved.
Django system tables (sessions, content types, permissions, etc.) are untouched.

Usage:
    python manage.py wipe_data               # interactive confirmation
    python manage.py wipe_data --yes         # skip confirmation (CI / Railway console)
    python manage.py wipe_data --keep-users  # also keep all regular user accounts
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Wipe all competition data and start fresh (preserves superuser accounts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the interactive confirmation prompt.",
        )
        parser.add_argument(
            "--keep-users",
            action="store_true",
            dest="keep_users",
            help="Preserve ALL user accounts (not just superusers).",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "\n============================================================\n"
            "  MKJ SUPA CUP — FULL DATA WIPE\n"
            "============================================================\n"
            "  This will permanently delete:\n"
            "    • All competitions, pools, fixtures, venues\n"
            "    • All teams, players, squad submissions\n"
            "    • All match reports, scores, statistics\n"
            "    • All referees and referee assignments\n"
            "    • All appeals, news articles, and media\n"
            "    • All admin activity logs and undo records\n"
            "    • All non-superuser accounts (unless --keep-users)\n"
            "\n  SUPERUSER accounts are always preserved.\n"
            "============================================================\n"
        ))

        if not options["yes"]:
            confirm = input("Type  YES  (all caps) to proceed: ")
            if confirm.strip() != "YES":
                self.stdout.write(self.style.SUCCESS("Aborted — nothing was changed."))
                return

        with transaction.atomic():
            self._wipe(options["keep_users"])

        self.stdout.write(self.style.SUCCESS(
            "\n✓ Data wipe complete. The system is ready for a fresh start.\n"
            "  Run 'python manage.py createsuperuser' if you need a new admin.\n"
        ))

    # ------------------------------------------------------------------
    def _wipe(self, keep_users: bool):

        # ── Admin activity logs ────────────────────────────────────────
        self._delete("admin_dashboard", "ActivityLog")
        self._delete("admin_dashboard", "UndoRecord")

        # ── Appeals ───────────────────────────────────────────────────
        self._delete("appeals", "Evidence")
        self._delete("appeals", "AppealNote")
        self._delete("appeals", "Appeal")

        # ── News / media ───────────────────────────────────────────────
        self._delete("news_media", "MediaFile")
        self._delete("news_media", "Article")
        self._delete("news_media", "NewsCategory")

        # ── Match data ────────────────────────────────────────────────
        self._delete("matches", "MatchEvent")
        self._delete("matches", "MatchStatistic")
        self._delete("matches", "SquadPlayer")
        self._delete("matches", "SquadSubmission")
        self._delete("matches", "MatchReport")
        self._delete("matches", "Match")

        # ── Referees ──────────────────────────────────────────────────
        self._delete("referees", "RefereeAssignment")
        self._delete("referees", "Referee")

        # ── Teams / players ───────────────────────────────────────────
        self._delete("teams",   "PlayerTransfer")
        self._delete("teams",   "Player")
        self._delete("teams",   "TeamOfficial")
        self._delete("teams",   "Team")
        self._delete("teams",   "SubCounty")

        # ── Competitions ──────────────────────────────────────────────
        self._delete("competitions", "PoolStanding")
        self._delete("competitions", "Pool")
        self._delete("competitions", "Venue")
        self._delete("competitions", "Round")
        self._delete("competitions", "Competition")

        # ── User accounts ─────────────────────────────────────────────
        if not keep_users:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            deleted, _ = User.objects.filter(is_superuser=False).delete()
            self.stdout.write(f"  • Deleted {deleted} non-superuser account(s).")
        else:
            self.stdout.write("  • User accounts kept (--keep-users flag set).")

    # ------------------------------------------------------------------
    def _delete(self, app_label: str, model_name: str):
        from django.apps import apps as django_apps
        try:
            Model = django_apps.get_model(app_label, model_name)
            count, _ = Model.objects.all().delete()
            self.stdout.write(f"  • Deleted {count:>6}  {app_label}.{model_name}")
        except LookupError:
            # Model doesn't exist in this installation — skip silently
            pass
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"  ! Could not delete {app_label}.{model_name}: {exc}"
            ))
