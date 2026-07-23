from datetime import datetime, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from mkj_cms.storage import resolve_cloudinary_config
from mkj_cms.web_views import get_fixture_squad_window_state


class FixtureSquadWindowStateTests(SimpleTestCase):
    def test_window_is_open_before_deadline(self):
        now = timezone.make_aware(datetime(2026, 7, 20, 12, 0, 0))
        fixture = SimpleNamespace(squad_deadline=now + timedelta(hours=1))

        state = get_fixture_squad_window_state(fixture, now=now)

        self.assertFalse(state['deadline_passed'])
        self.assertTrue(state['selection_open'])
        self.assertEqual(state['deadline'], fixture.squad_deadline)

    def test_window_is_closed_after_deadline(self):
        now = timezone.make_aware(datetime(2026, 7, 20, 12, 0, 0))
        fixture = SimpleNamespace(squad_deadline=now - timedelta(minutes=5))

        state = get_fixture_squad_window_state(fixture, now=now)

        self.assertTrue(state['deadline_passed'])
        self.assertFalse(state['selection_open'])


class CloudinaryConfigTests(SimpleTestCase):
    def test_resolves_config_from_individual_environment_variables(self):
        config = resolve_cloudinary_config(
            cloudinary_url="",
            cloud_name="demo-cloud",
            api_key="demo-key",
            api_secret="demo-secret",
        )

        self.assertEqual(config['CLOUD_NAME'], 'demo-cloud')
        self.assertEqual(config['API_KEY'], 'demo-key')
        self.assertEqual(config['API_SECRET'], 'demo-secret')
