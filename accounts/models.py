"""
MKJ SUPA CUP Accounts — Custom User Model with Role-Based Access
"""
import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# Shared phone validator: +254 followed by exactly 9 digits
kenya_phone_validator = RegexValidator(
    regex=r'^\+254\d{9}$',
    message='Phone number must be in the format +254XXXXXXXXX (country code + 9 digits).',
)

# Shared national ID validator: digits only, 5 to 10 characters.
national_id_validator = RegexValidator(
    regex=r'^\d{5,10}$',
    message='ID number must contain 5 to 10 digits.',
)


def normalize_kenya_phone_digits(raw_phone: str) -> str:
    """Return the local 9-digit Kenyan phone number without the +254 prefix."""
    phone = re.sub(r'\D', '', (raw_phone or '').strip())
    if not phone:
        return ''
    if phone.startswith('254') and len(phone) == 12:
        phone = phone[3:]
    elif phone.startswith('0') and len(phone) == 10:
        phone = phone[1:]
    if re.fullmatch(r'\d{9}', phone):
        return phone
    return ''


def normalize_kenya_phone(raw_phone: str) -> str:
    digits = normalize_kenya_phone_digits(raw_phone)
    return f'+254{digits}' if digits else ''


def validate_kenya_phone_or_raise(raw_phone: str, label: str = 'Phone number') -> str:
    normalized = normalize_kenya_phone(raw_phone)
    if not normalized:
        raise ValidationError(f'{label} must contain exactly 9 digits after the +254 prefix.')
    return normalized


def normalize_national_id(raw_id: str) -> str:
    return re.sub(r'\D', '', (raw_id or '').strip())


def validate_national_id_or_raise(raw_id: str, label: str = 'ID number') -> str:
    normalized = normalize_national_id(raw_id)
    if not re.fullmatch(r'\d{5,10}', normalized):
        raise ValidationError(f'{label} must contain 5 to 10 digits.')
    return normalized


class UserRole(models.TextChoices):
    COMPETITION_MANAGER = "competition_manager", "Organising Secretary"
    COORDINATOR         = "coordinator",         "Discipline Coordinator"
    VERIFICATION_OFFICER = "verification_officer", "Verification Officer"
    REFEREE             = "referee",             "Referee"
    TEAM_MANAGER        = "team_manager",        "Team Manager"
    CEC_SPORTS_MEMBER = "cec_sports", "County CEC Member - Sports"
    TREASURER           = "treasurer",           "Treasurer"
    JURY_CHAIR          = "jury_chair",          "Chair of the Jury"
    MEDIA_MANAGER       = "media_manager",       "Media Manager"
    SECRETARY_GENERAL   = "secretary_general",   "Secretary General"
    SCOUT               = "scout",               "Scout"
    SUBCOUNTY_SPORTS_OFFICER = "subcounty_sports_officer", "Sub-County Sports Officer"
    CHIEF_SPORTS_OFFICER = "chief_sports_officer", "Chief Sports Officer"
    DIRECTOR_SPORTS     = "director_sports",     "Director of Sports"
    CHIEF_OFFICER_SPORTS = "chief_officer_sports", "Chief Officer - Sports"
    ADMIN               = "admin",               "System Admin"


class MakueniSubCounty(models.TextChoices):
    MAKUENI      = "Makueni",      "Makueni"
    KIBWEZI_WEST = "Kibwezi West", "Kibwezi West"
    KIBWEZI_EAST = "Kibwezi East", "Kibwezi East"
    KAITI        = "Kaiti",        "Kaiti"
    KILOME       = "Kilome",       "Kilome"
    MBOONI       = "Mbooni",       "Mbooni"


# ── Ward mapping per Makueni sub-county (IEBC boundaries) ─────────────────
MAKUENI_SUBCOUNTY_WARDS = {
    "Makueni": [
        "Wote", "Muvau/Kikumini", "Mavindini",
        "Kitise/Kithuki", "Kathonzweni", "Nzaui/Kilili/Kalamba", "Mbitini",
    ],
    "Kibwezi West": [
        "Makindu", "Nguu/Masumba", "Emali/Mulala", "Nguumo",
    ],
    "Kibwezi East": [
        "Masongaleni", "Mtito Andei", "Thange", "Ivingoni/Nzambani",
    ],
    "Kaiti": [
        "Ukia", "Kee", "Kilungu", "Ilima",
    ],
    "Kilome": [
        "Kasikeu", "Mukaa", "Kiima Kiu/Kalanzoni",
    ],
    "Mbooni": [
        "Tulimani", "Mbooni", "Kithungo/Kitundu", "Kiteta/Kisau", "Waia/Kako",
    ],
}


def get_wards_for_subcounty(sub_county):
    """Return list of ward names for a Makueni sub-county."""
    return MAKUENI_SUBCOUNTY_WARDS.get(sub_county, [])


def get_all_wards_flat():
    """Return all wards as a flat sorted list of (value, label) tuples."""
    wards = []
    for sc_wards in MAKUENI_SUBCOUNTY_WARDS.values():
        for w in sc_wards:
            wards.append((w, w))
    return sorted(set(wards))


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff",     True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role",         UserRole.ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Central MKJ SUPA CUP user — single table, role differentiates access.
    """
    email       = models.EmailField(unique=True)
    first_name  = models.CharField(max_length=100)
    last_name   = models.CharField(max_length=100)
    phone       = models.CharField(max_length=13, validators=[kenya_phone_validator])
    role        = models.CharField(max_length=30, choices=UserRole.choices, default=UserRole.TEAM_MANAGER)
    county      = models.CharField(max_length=100, blank=True, help_text="Kenyan county")
    sub_county  = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Sub-county or constituency assignment for sub-county sports officers",
    )
    profile_photo = models.ImageField(upload_to="profiles/", null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False, help_text="Admin-suspended account")
    assigned_discipline = models.CharField(
        max_length=30, blank=True, default="",
        help_text="Sport family or discipline this user manages (for Coordinator / Scout roles)",
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text="When True the user must set a new password on next login.",
    )
    date_joined = models.DateTimeField(default=timezone.now)
    last_login  = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name      = "User"
        verbose_name_plural = "Users"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    # ── Role helpers ──────────────────────────────────────────────────────────
    @property
    def is_competition_manager(self): return self.role == UserRole.COMPETITION_MANAGER
    @property
    def is_coordinator(self): return self.role == UserRole.COORDINATOR
    @property
    def is_verification_officer(self): return self.role == UserRole.VERIFICATION_OFFICER
    @property
    def is_referee_manager(self): return self.is_coordinator  # backwards compat
    @property
    def is_referee(self): return self.role == UserRole.REFEREE
    @property
    def is_team_manager(self): return self.role == UserRole.TEAM_MANAGER
    @property
    def is_cec_sports_member(self): return self.role == UserRole.CEC_SPORTS_MEMBER
    @property
    def is_treasurer(self): return self.role == UserRole.TREASURER
    @property
    def is_jury_chair(self): return self.role == UserRole.JURY_CHAIR
    @property
    def is_scout(self): return self.role == UserRole.SCOUT
    @property
    def is_secretary_general(self): return self.role == UserRole.SECRETARY_GENERAL
    @property
    def is_subcounty_sports_officer(self): return self.role == UserRole.SUBCOUNTY_SPORTS_OFFICER
    @property
    def is_chief_sports_officer(self): return self.role == UserRole.CHIEF_SPORTS_OFFICER
    @property
    def is_director_sports(self): return self.role == UserRole.DIRECTOR_SPORTS
    @property
    def is_chief_officer_sports(self): return self.role == UserRole.CHIEF_OFFICER_SPORTS
    @property
    def is_admin(self): return self.role == UserRole.ADMIN or self.is_superuser


class KenyaCounty(models.TextChoices):
    MOMBASA      = "Mombasa",       "Mombasa"
    KWALE        = "Kwale",         "Kwale"
    KILIFI       = "Kilifi",        "Kilifi"
    TANA_RIVER   = "Tana River",    "Tana River"
    LAMU         = "Lamu",          "Lamu"
    TAITA_TAVETA = "Taita Taveta",  "Taita Taveta"
    GARISSA      = "Garissa",       "Garissa"
    WAJIR        = "Wajir",         "Wajir"
    MANDERA      = "Mandera",       "Mandera"
    MARSABIT     = "Marsabit",      "Marsabit"
    ISIOLO       = "Isiolo",        "Isiolo"
    MERU         = "Meru",          "Meru"
    THARAKA_NITHI = "Tharaka Nithi","Tharaka Nithi"
    EMBU         = "Embu",          "Embu"
    KITUI        = "Kitui",         "Kitui"
    MACHAKOS     = "Machakos",      "Machakos"
    MAKUENI      = "Makueni",       "Makueni"
    NYANDARUA    = "Nyandarua",     "Nyandarua"
    NYERI        = "Nyeri",         "Nyeri"
    KIRINYAGA    = "Kirinyaga",     "Kirinyaga"
    MURANGA      = "Muranga",       "Murang'a"
    KIAMBU       = "Kiambu",        "Kiambu"
    TURKANA      = "Turkana",       "Turkana"
    WEST_POKOT   = "West Pokot",    "West Pokot"
    SAMBURU      = "Samburu",       "Samburu"
    TRANS_NZOIA  = "Trans Nzoia",   "Trans Nzoia"
    UASIN_GISHU  = "Uasin Gishu",  "Uasin Gishu"
    ELGEYO_MARAKWET = "Elgeyo Marakwet", "Elgeyo Marakwet"
    NANDI        = "Nandi",         "Nandi"
    BARINGO      = "Baringo",       "Baringo"
    LAIKIPIA     = "Laikipia",      "Laikipia"
    NAKURU       = "Nakuru",        "Nakuru"
    NAROK        = "Narok",         "Narok"
    KAJIADO      = "Kajiado",       "Kajiado"
    KERICHO      = "Kericho",       "Kericho"
    BOMET        = "Bomet",         "Bomet"
    KAKAMEGA     = "Kakamega",      "Kakamega"
    VIHIGA       = "Vihiga",        "Vihiga"
    BUNGOMA      = "Bungoma",       "Bungoma"
    BUSIA        = "Busia",         "Busia"
    SIAYA        = "Siaya",         "Siaya"
    KISUMU       = "Kisumu",        "Kisumu"
    HOMA_BAY     = "Homa Bay",      "Homa Bay"
    MIGORI       = "Migori",        "Migori"
    KISII        = "Kisii",         "Kisii"
    NYAMIRA      = "Nyamira",       "Nyamira"
    NAIROBI      = "Nairobi",       "Nairobi"
