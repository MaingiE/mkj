"""
MKJ SUPA CUP Teams — Django Forms for Registration & Management
Adapted from FKFSYS teams registration workflow.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
import re
from .models import (
    Team, Player, PLAYER_MIN_AGE, PLAYER_MAX_AGE,
    CountyRegistration, CountyPlayer, CountyDiscipline, SQUAD_LIMITS,
    TechnicalBenchMember, TechnicalBenchRole,
    CountyDelegationMember, CountyDelegationRole,
)
from accounts.models import (
    KenyaCounty,
    User,
    kenya_phone_validator,
    MakueniSubCounty,
    MAKUENI_SUBCOUNTY_WARDS,
    normalize_kenya_phone as shared_normalize_kenya_phone,
    validate_kenya_phone_or_raise as shared_validate_kenya_phone_or_raise,
    validate_national_id_or_raise as shared_validate_national_id_or_raise,
)
from competitions.models import Competition, CompetitionStatus, SportType


def normalize_kenya_phone(raw_phone: str) -> str:
    """Normalize Kenyan phone input to +254XXXXXXXXX format."""
    return shared_normalize_kenya_phone(raw_phone)


def validate_kenya_phone_or_raise(phone: str, label: str = 'Phone number') -> str:
    return shared_validate_kenya_phone_or_raise(phone, label)


def validate_national_id_or_raise(id_number: str, label: str = 'ID number') -> str:
    return shared_validate_national_id_or_raise(id_number, label)


class TeamRegistrationForm(forms.ModelForm):
    """
    Public team registration form.
    Creates a team with 'pending' status awaiting admin approval.
    """
    competition = forms.ModelChoiceField(
        queryset=Competition.objects.filter(
            status__in=[CompetitionStatus.REGISTRATION, CompetitionStatus.UPCOMING],
        ),
        required=False,
        empty_label="— Select a competition (optional) —",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_competition'}),
        label="Competition",
        help_text="Competitions currently open for registration.",
    )

    class Meta:
        model = Team
        fields = [
            'name', 'county', 'sport_type', 'competition',
            'contact_phone', 'contact_email',
            # Home kit
            'home_outfield_colour', 'home_shorts_colour', 'home_socks_colour',
            'home_gk_colour', 'home_kit_image',
            # Away kit
            'away_outfield_colour', 'away_shorts_colour', 'away_socks_colour',
            'away_gk_colour', 'away_kit_image',
            # Third kit (optional)
            'third_outfield_colour', 'third_shorts_colour', 'third_socks_colour',
            'third_gk_colour', 'third_kit_image',
            # Badge & logo
            'badge', 'county_logo',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter team name',
                'required': True,
            }),
            'county': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Laikipia',
                'required': True,
            }),
            'sport_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_sport_type',
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '712345678',
                'pattern': '\\d{9}',
                'minlength': '9',
                'maxlength': '9',
                'inputmode': 'numeric',
                'required': True,
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'team@example.com',
            }),
            # Home kit
            'home_outfield_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Green'}),
            'home_shorts_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. White'}),
            'home_socks_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Green'}),
            'home_gk_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Yellow'}),
            'home_kit_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            # Away kit
            'away_outfield_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. White'}),
            'away_shorts_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Black'}),
            'away_socks_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. White'}),
            'away_gk_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Orange'}),
            'away_kit_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            # Third kit
            'third_outfield_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'third_shorts_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'third_socks_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'third_gk_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'third_kit_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            # Badge & logo
            'badge': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'county_logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'name': 'Team Name *',
            'county': 'County *',
            'sport_type': 'Sport *',
            'contact_phone': 'Contact Phone *',
            'contact_email': 'Contact Email',
            'home_outfield_colour': 'Home Jersey Colour *',
            'home_shorts_colour': 'Home Shorts Colour *',
            'home_socks_colour': 'Home Socks Colour *',
            'home_gk_colour': 'Home GK Jersey Colour *',
            'home_kit_image': 'Home Kit Photo',
            'away_outfield_colour': 'Away Jersey Colour *',
            'away_shorts_colour': 'Away Shorts Colour *',
            'away_socks_colour': 'Away Socks Colour *',
            'away_gk_colour': 'Away GK Jersey Colour *',
            'away_kit_image': 'Away Kit Photo',
            'third_outfield_colour': 'Third Jersey Colour',
            'third_shorts_colour': 'Third Shorts Colour',
            'third_socks_colour': 'Third Socks Colour',
            'third_gk_colour': 'Third GK Jersey Colour',
            'third_kit_image': 'Third Kit Photo',
            'badge': 'Team Badge / Logo',
            'county_logo': 'County Logo',
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Team.objects.filter(name__iexact=name).exists():
            raise ValidationError(f'A team named "{name}" already exists.')
        return name

    def clean_contact_email(self):
        email = self.cleaned_data.get('contact_email')
        if email and Team.objects.filter(contact_email=email).exists():
            raise ValidationError('This email is already registered to another team.')
        return email

    def clean_contact_phone(self):
        return validate_kenya_phone_or_raise(self.cleaned_data.get('contact_phone'), 'Contact phone')

    def clean(self):
        cleaned = super().clean()
        sport = cleaned.get('sport_type')
        competition = cleaned.get('competition')
        if competition and sport and competition.sport_type != sport:
            self.add_error('competition', 'Selected competition does not match the chosen sport.')
        return cleaned


class PlayerRegistrationForm(forms.ModelForm):
    """
    Player registration form — used after a team is approved.
    Includes document upload fields and age validation.
    """

    class Meta:
        model = Player
        fields = [
            'first_name', 'last_name', 'date_of_birth',
            'position', 'shirt_number',
            'national_id_number', 'birth_cert_number',
            'fifa_connect_id',
            'photo', 'id_document', 'birth_certificate',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'position': forms.Select(attrs={
                'class': 'form-control',
            }),
            'shirt_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '99',
            }),
            'national_id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 12345678',
                'pattern': '\\d{5,10}',
                'minlength': '5',
                'maxlength': '10',
                'inputmode': 'numeric',
            }),
            'birth_cert_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 0123456789',
            }),
            'fifa_connect_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'FIFA Connect ID (if known)',
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
            'id_document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf',
            }),
            'birth_certificate': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf',
            }),
        }
        labels = {
            'first_name': 'First Name *',
            'last_name': 'Last Name *',
            'date_of_birth': 'Date of Birth *',
            'position': 'Position *',
            'shirt_number': 'Shirt Number *',
            'national_id_number': 'National ID Number',
            'birth_cert_number': 'Birth Certificate Number',
            'fifa_connect_id': 'FIFA Connect ID (optional)',
            'photo': 'Passport-Size Photo *',
            'id_document': 'Copy of National ID *',
            'birth_certificate': 'Copy of Birth Certificate (optional)',
        }
        help_texts = {
            'photo': 'Clear passport-size photograph',
            'id_document': 'Scan or photo of the player\'s National ID',
            'birth_certificate': 'Scan or photo of the player\'s Birth Certificate',
            'date_of_birth': f'Player must be between {PLAYER_MIN_AGE} and {PLAYER_MAX_AGE} years old',
        }

    def clean_date_of_birth(self):
        """Validate age is within the 18-23 bracket."""
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = timezone.now().date()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < PLAYER_MIN_AGE:
                raise ValidationError(
                    f'Player is {age} years old. Minimum age is {PLAYER_MIN_AGE}. '
                    f'Registration is not allowed.'
                )
            if age > PLAYER_MAX_AGE:
                raise ValidationError(
                    f'Player is {age} years old. Maximum age is {PLAYER_MAX_AGE}. '
                    f'Registration is not allowed.'
                )
        return dob

    def clean_national_id_number(self):
        national_id_number = self.cleaned_data.get('national_id_number')
        if national_id_number:
            return validate_national_id_or_raise(national_id_number, 'National ID number')
        return national_id_number


# ══════════════════════════════════════════════════════════════════════════════
#  COUNTY SPORTS ADMIN — Registration Form (public, no login)
# ══════════════════════════════════════════════════════════════════════════════

class CountyAdminRegistrationForm(forms.Form):
    """Public county registration for MKJ SUPA CUP 4th Edition."""
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
        label='First Name *',
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
        label='Last Name *',
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com'}),
        label='Email Address *',
    )
    phone = forms.CharField(
        max_length=13,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '712345678', 'pattern': '\\d{9}', 'minlength': '9', 'maxlength': '9', 'inputmode': 'numeric'}),
        label='Phone Number *',
    )
    county = forms.ChoiceField(
        choices=[('', '— Select your county —')] + list(KenyaCounty.choices),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='County *',
    )

    # Director of Sports — contact person for the county
    director_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name of Director of Sports'}),
        label='Director of Sports — Full Name *',
    )
    director_phone = forms.CharField(
        max_length=13,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '712345678', 'pattern': '\\d{9}', 'minlength': '9', 'maxlength': '9', 'inputmode': 'numeric'}),
        label='Director of Sports — Phone Number *',
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email.lower()

    def clean_county(self):
        county = self.cleaned_data['county']
        if CountyRegistration.objects.filter(county=county).exists():
            raise ValidationError('A county sports director has already registered for this county.')
        return county

    def clean_phone(self):
        return validate_kenya_phone_or_raise(self.cleaned_data.get('phone'), 'Phone number')

    def clean_director_phone(self):
        return validate_kenya_phone_or_raise(self.cleaned_data.get('director_phone'), 'Director phone')


# ══════════════════════════════════════════════════════════════════════════════
#  COUNTY SPORTS ADMIN — Payment Submission
# ══════════════════════════════════════════════════════════════════════════════

class CountyPaymentForm(forms.Form):
    """County admin submits M-Pesa ref or bank slip as payment proof."""
    payment_method = forms.ChoiceField(
        choices=[('mpesa', 'M-Pesa'), ('bank_transfer', 'Bank Transfer')],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Payment Method *',
    )
    mpesa_reference = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'e.g. RIA7K8QX3P',
            'pattern': '[A-Z0-9]{10,}', 'style': 'text-transform:uppercase',
        }),
        label='M-Pesa Transaction Code',
        help_text='Enter the M-Pesa confirmation code from your SMS.',
    )
    bank_slip = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
        label='Bank Slip (image or PDF)',
    )
    bank_reference = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bank transfer reference'}),
        label='Bank Payment Reference',
    )
    payment_amount = forms.DecimalField(
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '250000'}),
        label='Amount Paid (KSh) *',
    )

    def clean(self):
        cd = super().clean()
        method = cd.get('payment_method')
        if method == 'mpesa':
            if not cd.get('mpesa_reference'):
                raise ValidationError('Please enter the M-Pesa transaction code from your confirmation SMS.')
        elif method == 'bank_transfer':
            if not cd.get('bank_slip') and not cd.get('bank_reference'):
                raise ValidationError('Please upload a bank slip or enter the bank payment reference.')
        return cd


# ══════════════════════════════════════════════════════════════════════════════
#  COUNTY SPORTS ADMIN — Add Player Form
# ══════════════════════════════════════════════════════════════════════════════

class CountyPlayerForm(forms.ModelForm):
    """Form for county sports director to register a player under a discipline."""

    def __init__(self, *args, **kwargs):
        self._discipline_sub_county = kwargs.pop('discipline_sub_county', '')
        super().__init__(*args, **kwargs)
        # Huduma number is optional at registration time.
        self.fields['huduma_number'].required = False

        # Build sub_county choices from MakueniSubCounty enum
        sc_choices = [('', '— Select Sub-County —')]
        sc_choices += [(sc.value, sc.label) for sc in MakueniSubCounty]
        self.fields['sub_county'].widget = forms.Select(
            attrs={'class': 'form-control', 'id': 'id_sub_county'},
        )
        self.fields['sub_county'].widget.choices = sc_choices

        # If discipline already has a sub_county, pre-select it
        if self._discipline_sub_county and not self.data:
            self.initial['sub_county'] = self._discipline_sub_county

        # Ward starts empty; JS populates choices dynamically
        self.fields['ward'].widget = forms.Select(
            attrs={'class': 'form-control', 'id': 'id_ward'},
        )
        self.fields['ward'].widget.choices = [('', '— Select Ward —')]

    class Meta:
        model = CountyPlayer
        fields = [
            'first_name', 'last_name', 'date_of_birth',
            'national_id_number', 'huduma_number', 'phone',
            'sub_county', 'ward',
            'position', 'jersey_number',
            'photo', 'id_document', 'birth_certificate',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'huduma_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Huduma Namba (optional)'}),
            'national_id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 12345678', 'pattern': '\\d{5,10}', 'minlength': '5', 'maxlength': '10', 'inputmode': 'numeric'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '712345678', 'pattern': '\\d{9}', 'minlength': '9', 'maxlength': '9', 'inputmode': 'numeric'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. GK, CB, CM, ST'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '99'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'id_document': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
            'birth_certificate': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
        }
        labels = {
            'first_name': 'First Name *',
            'last_name': 'Last Name *',
            'date_of_birth': 'Date of Birth *',
            'national_id_number': 'National ID Number *',
            'huduma_number': 'Huduma Namba (optional)',
            'phone': 'Phone Number *',
            'sub_county': 'Sub-County *',
            'ward': 'Ward *',
            'position': 'Position',
            'jersey_number': 'Jersey Number',
            'photo': 'Passport Photo *',
            'id_document': 'Copy of National ID *',
            'birth_certificate': 'Birth Certificate (optional)',
        }

    def clean_national_id_number(self):
        nid = validate_national_id_or_raise(self.cleaned_data['national_id_number'], 'National ID number')
        qs = CountyPlayer.objects.filter(national_id_number=nid)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            existing = qs.first()
            raise ValidationError(
                f'This National ID is already registered under '
                f'{existing.discipline.registration.county} — {existing.discipline.get_sport_type_display()}.'
            )
        return nid

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = timezone.now().date()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < PLAYER_MIN_AGE:
                raise ValidationError(f'Player is {age} — minimum age is {PLAYER_MIN_AGE}.')
            if age > PLAYER_MAX_AGE:
                raise ValidationError(f'Player is {age} — maximum age is {PLAYER_MAX_AGE}.')
        return dob

    def clean_phone(self):
        return validate_kenya_phone_or_raise(self.cleaned_data.get('phone'), 'Phone number')


# ══════════════════════════════════════════════════════════════════════════════
#  TECHNICAL BENCH — Add / Edit Form
# ══════════════════════════════════════════════════════════════════════════════

class TechnicalBenchForm(forms.ModelForm):
    """Form for county sports director to add a technical bench member."""

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        email = (cleaned.get('email') or '').strip().lower()
        phone = cleaned.get('phone')

        if phone:
            try:
                cleaned['phone'] = validate_kenya_phone_or_raise(phone, 'Phone number')
            except ValidationError as exc:
                self.add_error('phone', exc)

        # Team Manager must always have a login account.
        if role == TechnicalBenchRole.TEAM_MANAGER:
            if not email:
                self.add_error('email', 'Email is required for Team Manager account creation.')
            else:
                existing_user = User.objects.filter(email__iexact=email).first()
                if existing_user and existing_user.role != 'team_manager':
                    self.add_error('email', 'This email already belongs to a non-Team Manager account.')

        return cleaned

    class Meta:
        model = TechnicalBenchMember
        fields = [
            'role', 'first_name', 'last_name', 'email', 'phone',
            'national_id_number', 'photo', 'id_document',
        ]
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '712345678', 'pattern': '\\d{9}', 'minlength': '9', 'maxlength': '9', 'inputmode': 'numeric', 'required': True}),
            'national_id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID', 'pattern': '\\d{5,10}', 'minlength': '5', 'maxlength': '10', 'inputmode': 'numeric'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'id_document': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
        }
        labels = {
            'role': 'Role *',
            'first_name': 'First Name *',
            'last_name': 'Last Name *',
            'email': 'Email Address',
            'phone': 'Phone Number *',
            'national_id_number': 'National ID Number',
            'photo': 'Passport Photo',
            'id_document': 'Copy of National ID',
        }

    def clean_national_id_number(self):
        national_id_number = self.cleaned_data.get('national_id_number')
        if national_id_number:
            return validate_national_id_or_raise(national_id_number, 'National ID number')
        return national_id_number


class CountyDelegationMemberForm(forms.ModelForm):
    """Form for county-level delegation officials (including CECM account setup)."""

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        email = (cleaned.get('email') or '').strip()
        phone = cleaned.get('phone')

        if phone:
            try:
                cleaned['phone'] = validate_kenya_phone_or_raise(phone, 'Phone number')
            except ValidationError as exc:
                self.add_error('phone', exc)

        if role == CountyDelegationRole.CECM_SPORTS and not email:
            self.add_error('email', 'Email is required to create a CECM login account.')

        return cleaned

    class Meta:
        model = CountyDelegationMember
        fields = ['role', 'full_name', 'phone', 'national_id_number', 'email']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full names'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '712345678', 'pattern': '\\d{9}', 'minlength': '9', 'maxlength': '9', 'inputmode': 'numeric'}),
            'national_id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID number', 'pattern': '\\d{5,10}', 'minlength': '5', 'maxlength': '10', 'inputmode': 'numeric'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email (required for CECM account)'}),
        }
        labels = {
            'role': 'Role *',
            'full_name': 'Full Names *',
            'phone': 'Phone Number *',
            'national_id_number': 'ID Number *',
            'email': 'Email Address',
        }

    def clean_national_id_number(self):
        return validate_national_id_or_raise(self.cleaned_data.get('national_id_number'), 'ID number')


# ══════════════════════════════════════════════════════════════════════════════
#  KIT COLORS — County Admin edits the linked Team's kit colours
# ══════════════════════════════════════════════════════════════════════════════

class KitColorsForm(forms.ModelForm):
    """Form for county admin to set home/away kit colours on the linked Team."""

    class Meta:
        model = Team
        fields = [
            'home_outfield_colour', 'home_shorts_colour',
            'home_socks_colour', 'home_gk_colour', 'home_kit_image',
            'away_outfield_colour', 'away_shorts_colour',
            'away_socks_colour', 'away_gk_colour', 'away_kit_image',
        ]
        widgets = {
            'home_outfield_colour': forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height:42px;padding:4px'}),
            'home_shorts_colour':   forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height:42px;padding:4px'}),
            'home_socks_colour':    forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height:42px;padding:4px'}),
            'home_gk_colour':       forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height:42px;padding:4px'}),
            'home_kit_image':       forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'away_outfield_colour': forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height:42px;padding:4px'}),
            'away_shorts_colour':   forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height:42px;padding:4px'}),
            'away_socks_colour':    forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height:42px;padding:4px'}),
            'away_gk_colour':       forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height:42px;padding:4px'}),
            'away_kit_image':       forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'home_outfield_colour': 'Outfield Jersey',
            'home_shorts_colour':   'Shorts',
            'home_socks_colour':    'Socks',
            'home_gk_colour':       'Goalkeeper Jersey',
            'home_kit_image':       'Kit Photo (optional)',
            'away_outfield_colour': 'Outfield Jersey',
            'away_shorts_colour':   'Shorts',
            'away_socks_colour':    'Socks',
            'away_gk_colour':       'Goalkeeper Jersey',
            'away_kit_image':       'Kit Photo (optional)',
        }

