from django.core.management.base import BaseCommand
from admin_dashboard.inbox_fetcher import fetch_inbox


class Command(BaseCommand):
    help = 'Fetch new emails from the IMAP inbox into EmailLog'

    def add_arguments(self, parser):
        parser.add_argument('--folder', default='INBOX', help='IMAP folder to fetch (default: INBOX)')
        parser.add_argument('--limit', type=int, default=50, help='Max messages to fetch (default: 50)')

    def handle(self, *args, **options):
        folder = options['folder']
        limit = options['limit']
        self.stdout.write(f'Fetching up to {limit} messages from {folder}...')
        try:
            new, skipped = fetch_inbox(folder=folder, limit=limit)
            self.stdout.write(self.style.SUCCESS(f'Done: {new} new, {skipped} already imported.'))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Error: {exc}'))
