from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from competitions.models import Competition, Fixture, SportType
from matches.models import MatchReport, MatchReportStatus
from referees.models import (
    AppointmentRole,
    AppointmentStatus,
    RefereeAppointment,
    RefereeLevel,
    RefereeProfile,
)
from teams.models import County, Team, TeamStatus


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class MatchReportingConsistencyTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        self.county_home, _ = County.objects.get_or_create(
            name="Makueni",
            defaults={"code": "MKU"},
        )
        self.county_away, _ = County.objects.get_or_create(
            name="Kitui",
            defaults={"code": "KTI"},
        )
        self.coordinator = self.create_user(
            email="coordinator@example.com",
            first_name="Cora",
            last_name="Dinato",
            phone="+254700000001",
            role=UserRole.COORDINATOR,
            assigned_discipline="football",
        )
        self.competition = Competition.objects.create(
            name="U17 Football Cup",
            sport_type=SportType.FOOTBALL_MEN,
            season="2025",
            start_date=date(2025, 1, 10),
            end_date=date(2025, 1, 20),
        )
        self.home_team = self.create_team("Makueni Stars", self.county_home)
        self.away_team = self.create_team("Kitui United", self.county_away)
        self.fixture = Fixture.objects.create(
            competition=self.competition,
            home_team=self.home_team,
            away_team=self.away_team,
            match_date=date(2025, 1, 12),
            kickoff_time=time(15, 0),
            status="confirmed",
        )

    def create_user(self, **kwargs):
        defaults = {
            "email": "user@example.com",
            "first_name": "Test",
            "last_name": "User",
            "phone": "+254700000099",
            "role": UserRole.TEAM_MANAGER,
        }
        defaults.update(kwargs)
        return User.objects.create_user(password="pass1234", **defaults)

    def create_team(self, name, county):
        return Team.objects.create(
            name=name,
            county=county,
            sport_type=SportType.FOOTBALL_MEN,
            status=TeamStatus.REGISTERED,
            contact_phone="+254711111111",
            contact_email=f"{name.lower().replace(' ', '')}@example.com",
        )

    def create_referee(self, email, first_name, last_name, approved=True):
        user = self.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=f"+2547{User.objects.count():08d}",
            role=UserRole.REFEREE,
        )
        profile, _ = RefereeProfile.objects.get_or_create(user=user)
        profile.license_number = profile.license_number or f"LIC-{user.pk:04d}"
        profile.level = RefereeLevel.COUNTY
        profile.county = self.county_home.name
        profile.is_approved = approved
        profile.id_number = f"1234{user.pk}"
        profile.save()
        return user, profile

    def create_appointment(self, referee_profile, role, status):
        return RefereeAppointment.objects.create(
            fixture=self.fixture,
            referee=referee_profile,
            role=role,
            status=status,
            appointed_by=self.coordinator,
        )

    def report_payload(self, fixture=None, referee_id=None):
        payload = {
            "fixture": (fixture or self.fixture).pk,
            "events": [],
            "home_score": 2,
            "away_score": 1,
            "home_yellow_cards": 1,
            "away_yellow_cards": 0,
            "home_red_cards": 0,
            "away_red_cards": 0,
            "match_duration": 90,
            "added_time_ht": 1,
            "added_time_ft": 3,
            "pitch_condition": "good",
            "weather": "Sunny",
            "attendance": 120,
            "referee_notes": "Match completed normally.",
            "is_abandoned": False,
            "abandonment_reason": "",
        }
        if referee_id is not None:
            payload["referee"] = referee_id
        return payload

    def test_duplicate_fixture_role_is_rejected(self):
        _, first_referee = self.create_referee("ref1@example.com", "Ada", "One")
        _, second_referee = self.create_referee("ref2@example.com", "Bea", "Two")

        self.create_appointment(first_referee, AppointmentRole.REFEREE, AppointmentStatus.CONFIRMED)

        with self.assertRaises(ValidationError):
            self.create_appointment(second_referee, AppointmentRole.REFEREE, AppointmentStatus.PENDING)

    def test_report_create_requires_confirmed_head_official(self):
        referee_user, referee_profile = self.create_referee("ref3@example.com", "Cara", "Three")
        self.create_appointment(referee_profile, AppointmentRole.AR1, AppointmentStatus.CONFIRMED)

        self.api_client.force_authenticate(user=referee_user)
        response = self.api_client.post(reverse("match-report-list"), self.report_payload(), format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(MatchReport.objects.count(), 0)
        self.assertIn("confirmed head official", str(response.data["detail"]).lower())

    def test_report_create_binds_authenticated_referee_and_snapshots_officials(self):
        referee_user, head_referee = self.create_referee("ref4@example.com", "Duke", "Four")
        _, assistant_referee = self.create_referee("ref5@example.com", "Eli", "Five")

        self.create_appointment(head_referee, AppointmentRole.REFEREE, AppointmentStatus.CONFIRMED)
        self.create_appointment(assistant_referee, AppointmentRole.AR1, AppointmentStatus.PENDING)

        self.api_client.force_authenticate(user=referee_user)
        response = self.api_client.post(
            reverse("match-report-list"),
            self.report_payload(referee_id=assistant_referee.pk),
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        report = MatchReport.objects.get()
        self.assertEqual(report.status, MatchReportStatus.SUBMITTED)
        self.assertEqual(report.referee, head_referee)
        self.assertEqual(len(report.appointment_snapshot), 2)
        self.assertEqual(report.appointment_snapshot[0]["role"], AppointmentRole.AR1)
        self.assertEqual(report.appointment_snapshot[1]["role"], AppointmentRole.REFEREE)
        self.assertEqual(response.data["referee"], head_referee.pk)

    def test_coordinator_reports_page_shows_appointed_officials_summary(self):
        referee_user, head_referee = self.create_referee("ref6@example.com", "Faye", "Six")
        _, assistant_referee = self.create_referee("ref7@example.com", "Glen", "Seven")

        self.create_appointment(head_referee, AppointmentRole.REFEREE, AppointmentStatus.CONFIRMED)
        self.create_appointment(assistant_referee, AppointmentRole.AR1, AppointmentStatus.PENDING)

        report = MatchReport.objects.create(
            fixture=self.fixture,
            referee=head_referee,
            status=MatchReportStatus.SUBMITTED,
            home_score=1,
            away_score=0,
            home_yellow_cards=0,
            away_yellow_cards=0,
            home_red_cards=0,
            away_red_cards=0,
            match_duration=90,
            added_time_ht=0,
            added_time_ft=0,
            pitch_condition="good",
            weather="Warm",
            attendance=200,
            referee_notes="Solid performance.",
            is_abandoned=False,
            abandonment_reason="",
        )

        self.client.force_login(self.coordinator)
        response = self.client.get(reverse("coordinator_match_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Officials Appointed")
        self.assertContains(response, head_referee.user.get_full_name())
        self.assertContains(response, assistant_referee.user.get_full_name())
        self.assertContains(response, "Assistant Referee 1 (AR1)")
        self.assertContains(response, report.get_status_display())