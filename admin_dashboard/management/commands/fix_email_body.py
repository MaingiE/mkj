"""
admin_dashboard/management/commands/fix_email_body.py

One-time data repair command.
Finds EmailLog rows where body_html is empty but body_text contains
HTML content (from the period when body_text was incorrectly stripped),
and moves body_text → body_html so the email detail preview renders correctly.

Usage:
    python manage.py fix_email_body          # dry run (shows what would change)
    python manage.py fix_email_body --apply  # actually save changes
"""
from django.core.management.base import BaseCommand
from admin_dashboard.models import EmailLog


class Command(BaseCommand):
    help = 'Repair EmailLog rows: move body_text → body_html where body_html is empty'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually save the changes (default is dry-run).',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        # Find rows where body_html is empty but body_text looks like HTML
        qs = EmailLog.objects.filter(body_html='').exclude(body_text='')
        html_rows = [
            row for row in qs
            if '<html' in row.body_text.lower() or '<!doctype' in row.body_text.lower()
            or ('<div' in row.body_text and '<p' in row.body_text)
        ]

        self.stdout.write(f'Found {len(html_rows)} EmailLog rows to repair.')

        if not html_rows:
            self.stdout.write(self.style.SUCCESS('Nothing to fix.'))
            return

        if not apply:
            self.stdout.write(
                self.style.WARNING(
                    'DRY RUN — no changes saved. '
                    'Run with --apply to apply fixes.'
                )
            )
            for row in html_rows[:10]:
                self.stdout.write(f'  [{row.pk}] {row.subject[:60]} → {row.to_emails[:40]}')
            if len(html_rows) > 10:
                self.stdout.write(f'  ... and {len(html_rows) - 10} more.')
            return

        # Apply: copy body_text → body_html for affected rows
        fixed = 0
        for row in html_rows:
            row.body_html = row.body_text
            row.save(update_fields=['body_html'])
            fixed += 1

        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed} EmailLog rows.'))
