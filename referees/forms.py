"""
MKJ SUPA CUP Referees — Django Forms for Registration & Management
Adapted from FKFSYS referee registration workflow.
"""
from django import forms
from django.core.exceptions import ValidationError
import re
from .models import RefereeProfile, RefereeLevel
from accounts.models import KenyaCounty, MakueniSubCounty, validate_national_id_or_raise


def normalize_kenya_phone(raw_phone: str) -> str:
    phone = (raw_phone or '').strip().replace(' ', '')
    if not phone:
        return ''

    if phone.startswith('+254') and len(phone) == 13:
        return phone
    if phone.startswith('254') and len(phone) == 12:
        return f'+{phone}'
    if phone.startswith('0') and len(phone) == 10:
        return f'+254{phone[1:]}'
    if phone.startswith('7') and len(phone) == 9:
        return f'+254{phone}'

    return phone


class RefereeRegistrationForm(forms.Form):
    """
    Public referee registration form.
    Creates a User (role=referee) + RefereeProfile (is_approved=False).
    Only 4 required fields: first_name, last_name, email, license_number.
    """
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name',
            'required': True,
        }),
        label='First Name *',
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name',
            'required': True,
        }),
        label='Last Name *',
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'referee@example.com',
            'required': True,
        }),
        label='Email Address *',
        help_text='A valid email for account notifications',
    )
    license_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. REF-2026-1234',
            'required': True,
        }),
        label='License Number *',
        help_text='Your referee license / badge number',
    )
    phone = forms.CharField(
        max_length=13,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '712345678',
            'pattern': '\\d{9}',
            'minlength': '9',
            'maxlength': '9',
            'inputmode': 'numeric',
        }),
        label='Phone Number *',
        help_text='Enter exactly 9 digits after the +254 prefix.',
    )
    county = forms.CharField(
        initial='Makueni',
        widget=forms.HiddenInput(),
        required=False,
        label='County',
    )
    sub_county = forms.ChoiceField(
        choices=[('', '-- Select Sub-County --')] + list(MakueniSubCounty.choices),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
        label='Sub-County',
    )
    level = forms.ChoiceField(
        choices=[('', '-- Select Level --')] + list(RefereeLevel.choices),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
        label='Referee Level',
    )
    id_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'National ID',
            'pattern': '\\d{5,10}',
            'minlength': '5',
            'maxlength': '10',
            'inputmode': 'numeric',
        }),
        label='National ID',
    )
    years_experience = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0',
            'min': '0',
        }),
        label='Years of Experience',
    )
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
        }),
        label='Profile Picture',
        help_text='Passport-size photo (optional)',
    )

    def clean_email(self):
        from accounts.models import User
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_license_number(self):
        lic = self.cleaned_data.get('license_number')
        if RefereeProfile.objects.filter(license_number=lic).exists():
            raise ValidationError('This license number is already registered.')
        return lic

    def clean_phone(self):
        phone = normalize_kenya_phone(self.cleaned_data.get('phone'))
        if not re.match(r'^\+254\d{9}$', phone):
            raise ValidationError('Phone number must be valid. Use 7XXXXXXXX, 07XXXXXXXX or +254XXXXXXXXX.')
        return phone

    def clean_id_number(self):
        id_number = self.cleaned_data.get('id_number')
        if id_number:
            return validate_national_id_or_raise(id_number, 'National ID')
        return id_number
