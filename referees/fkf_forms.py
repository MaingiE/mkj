# File: referees/forms.py
# FIXED VERSION - Updated to match merged models.py

from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.db import models
from fkf_league.validators import normalize_kenya_phone
from fkf_league.constants import KENYA_COUNTIES

from .models import (
    Referee, MatchReport, MatchOfficials, TeamOfficial,
    PlayingKit, MatchVenueDetails, StartingLineup,
    ReservePlayer, Substitution, Caution, Expulsion, MatchGoal, PreMatchMeetingForm
)

from matches.models import Match
from teams.models import Player, Team


class RefereeRegistrationForm(forms.ModelForm):
    """
    SIMPLE REGISTRATION FORM - Only 4 required fields!
    Optional fields: photo, county, id_number, specialization
    """
    phone_digits = forms.CharField(
        max_length=9,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '712345678',
            'pattern': '[0-9]{9}',
            'maxlength': '9',
            'required': True,
        }),
        help_text='Enter 9 digits only (e.g., 712345678). Will be saved as +254XXXXXXXXX',
    )
    
    class Meta:
        model = Referee
        fields = [
            'first_name', 'last_name', 'fkf_number', 'email',  # Required
            'specialization', 'photo', 'county', 'id_number'   # Optional (phone_digits handled separately)
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name',
                'required': True
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name',
                'required': True
            }),
            'fkf_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., FKF-2024-1234',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'referee@example.com',
                'required': True
            }),
            'specialization': forms.Select(attrs={
                'class': 'form-control'
            }),
            'county': forms.Select(attrs={
                'class': 'form-control'
            }),
            'id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'National ID Number'
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        labels = {
            'first_name': 'First Name *',
            'last_name': 'Last Name *',
            'fkf_number': 'FKF License Number *',
            'email': 'Email Address *',
            'specialization': 'Specialization',
            'county': 'County',
            'id_number': 'National ID Number',
            'photo': 'Profile Photo',
        }
        help_texts = {
            'fkf_number': 'Your Football Kenya Federation license number',
            'email': 'A valid email address for account notifications',
            'specialization': 'Choose your primary role: Referee, Assistant Referee, or Match Commissioner',
            'photo': 'Upload a clear passport-size photo (optional)',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        phone_digits = cleaned_data.get('phone_digits', '')
        
        # If phone digits provided, validate and create full phone number
        if phone_digits:
            # Remove any non-digit characters
            phone_digits = ''.join(filter(str.isdigit, phone_digits))
            
            if len(phone_digits) != 9:
                raise forms.ValidationError({'phone_digits': 'Please enter exactly 9 digits'})
            
            if not phone_digits[0] in ['0', '1', '7']:
                raise forms.ValidationError({'phone_digits': 'Phone number must start with 0, 1, or 7'})
            
            # Create full phone number with +254 prefix
            cleaned_data['phone_number'] = f'+254{phone_digits}'
        else:
            cleaned_data['phone_number'] = ''
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Set the phone_number from cleaned_data
        instance.phone_number = self.cleaned_data.get('phone_number', '')
        if commit:
            instance.save()
        return instance


class RefereeProfileUpdateForm(forms.ModelForm):
    """
    Form for referees to update their profile after approval
    """
    phone_digits = forms.CharField(
        max_length=9,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '712345678',
            'pattern': '[0-9]{9}',
            'maxlength': '9',
            'required': True,
        }),
        help_text='Enter 9 digits only (e.g., 712345678). Will be saved as +254XXXXXXXXX',
    )
    
    class Meta:
        model = Referee
        fields = [
            'first_name', 'last_name', 'email', 'fkf_number', 'level', 
            'specialization', 'county', 'id_number', 'photo'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'readonly': True}),
            'fkf_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'level': forms.Select(attrs={'class': 'form-control'}),
            'specialization': forms.Select(attrs={'class': 'form-control'}),
            'county': forms.Select(attrs={'class': 'form-control'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email',
            'fkf_number': 'FKF License Number',
            'level': 'Referee Level',
            'specialization': 'Specialization',
            'county': 'County',
            'id_number': 'National ID Number',
            'photo': 'Profile Photo',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate phone_digits if phone_number exists
        if self.instance and self.instance.phone_number:
            if self.instance.phone_number.startswith('+254'):
                self.fields['phone_digits'].initial = self.instance.phone_number[4:]
    
    def clean(self):
        cleaned_data = super().clean()
        phone_digits = cleaned_data.get('phone_digits', '')
        
        # If phone digits provided, validate and create full phone number
        if phone_digits:
            # Remove any non-digit characters
            phone_digits = ''.join(filter(str.isdigit, phone_digits))
            
            if len(phone_digits) != 9:
                raise forms.ValidationError({'phone_digits': 'Please enter exactly 9 digits'})
            
            if not phone_digits[0] in ['0', '1', '7']:
                raise forms.ValidationError({'phone_digits': 'Phone number must start with 0, 1, or 7'})
            
            # Create full phone number with +254 prefix
            cleaned_data['phone_number'] = f'+254{phone_digits}'
        else:
            cleaned_data['phone_number'] = ''
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Set the phone_number from cleaned_data
        instance.phone_number = self.cleaned_data.get('phone_number', '')
        if commit:
            instance.save()
        return instance


class MatchOfficialsAppointmentForm(forms.ModelForm):
    """
    Form for appointing match officials
    """
    class Meta:
        model = MatchOfficials
        fields = [
            'main_referee', 'assistant_1', 'assistant_2',
            'reserve_referee', 'var', 'avar1', 'avar2', 'match_commissioner'
        ]
        widgets = {
            'main_referee': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'assistant_1': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'assistant_2': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'reserve_referee': forms.Select(attrs={'class': 'form-control'}),
            'var': forms.Select(attrs={'class': 'form-control'}),
            'avar1': forms.Select(attrs={'class': 'form-control'}),
            'avar2': forms.Select(attrs={'class': 'form-control'}),
            'match_commissioner': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'main_referee': 'REFEREE *',
            'assistant_1': 'ASSISTANT REFEREE 1 *',
            'assistant_2': 'ASSISTANT REFEREE 2 *',
            'reserve_referee': 'RESERVE REFEREE',
            'var': 'Video Assistant Referee (VAR)',
            'avar1': 'Assistant VAR 1 (AVAR1)',
            'avar2': 'Assistant VAR 2 (AVAR2)',
            'match_commissioner': 'Match Commissioner',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show approved and active referees
        approved_referees = Referee.objects.filter(status='approved', is_active=True)
        
        # Get match instance if editing
        match_instance = self.instance.match if self.instance and self.instance.pk else None
        
        # Get already appointed referees for this match's round/time slot
        excluded_referees = set()
        if match_instance:
            # Find matches in the same round and similar time
            from matches.models import Match
            from datetime import timedelta
            
            match_date = match_instance.match_date
            time_window_start = match_date - timedelta(hours=2)
            time_window_end = match_date + timedelta(hours=2)
            
            # Get all matches in same time window
            overlapping_matches = Match.objects.filter(
                round_number=match_instance.round_number,
                match_date__gte=time_window_start,
                match_date__lte=time_window_end
            ).exclude(id=match_instance.id)
            
            # Collect all appointed referees from these matches
            for match in overlapping_matches:
                if hasattr(match, 'officials'):
                    officials = match.officials
                    for field in ['main_referee', 'assistant_1', 'assistant_2', 
                                  'reserve_referee', 'var', 'avar1', 'avar2', 'fourth_official', 
                                  'match_commissioner']:
                        referee = getattr(officials, field, None)
                        if referee:
                            excluded_referees.add(referee.id)
        
        # Filter referees by specialization for each role
        # REFEREE role - only REFEREE specialization (can also be VAR, RESERVE)
        referee_specialists = approved_referees.filter(
            models.Q(specialization='REFEREE') | models.Q(specialization__isnull=True)
        ).exclude(id__in=excluded_referees)
        
        # AR1 and AR2 roles - only ASSISTANT_REFEREE specialization
        assistant_referee_specialists = approved_referees.filter(
            models.Q(specialization='ASSISTANT_REFEREE') | models.Q(specialization__isnull=True)
        ).exclude(id__in=excluded_referees)
        
        # AVAR2 role - can be REFEREE or ASSISTANT_REFEREE
        avar2_specialists = approved_referees.filter(
            models.Q(specialization='REFEREE') | 
            models.Q(specialization='ASSISTANT_REFEREE') | 
            models.Q(specialization__isnull=True)
        ).exclude(id__in=excluded_referees)
        
        # COMMISSIONER role - only MATCH_COMMISSIONER specialization
        commissioner_specialists = approved_referees.filter(
            models.Q(specialization='MATCH_COMMISSIONER') | models.Q(specialization__isnull=True)
        ).exclude(id__in=excluded_referees)
        
        # Apply filtered querysets to form fields
        self.fields['main_referee'].queryset = referee_specialists
        self.fields['reserve_referee'].queryset = referee_specialists
        self.fields['var'].queryset = referee_specialists
        
        self.fields['assistant_1'].queryset = assistant_referee_specialists
        self.fields['assistant_2'].queryset = assistant_referee_specialists
        self.fields['avar1'].queryset = assistant_referee_specialists
        
        self.fields['avar2'].queryset = avar2_specialists
        
        self.fields['match_commissioner'].queryset = commissioner_specialists
    
    def clean(self):
        """
        Validate that the same official is not appointed to multiple positions
        """
        cleaned_data = super().clean()
        
        # Collect all appointed officials with their roles
        officials_map = {}
        
        fields_to_check = [
            ('main_referee', 'Referee'),
            ('assistant_1', 'Assistant Referee 1'),
            ('assistant_2', 'Assistant Referee 2'),
            ('reserve_referee', 'Reserve Referee'),
            ('var', 'VAR'),
            ('avar1', 'Assistant VAR 1'),
            ('avar2', 'Assistant VAR 2'),
            ('match_commissioner', 'Match Commissioner'),
        ]
        
        for field_name, role_name in fields_to_check:
            official = cleaned_data.get(field_name)
            if official:
                if official in officials_map:
                    raise forms.ValidationError(
                        f"{official.full_name} cannot be appointed to multiple positions. "
                        f"Already assigned as {officials_map[official]}, cannot also be {role_name}."
                    )
                officials_map[official] = role_name
        
        return cleaned_data


class MatchOfficialsManualEntryForm(forms.ModelForm):
    """
    Emergency manual entry form for officials not in system
    """
    class Meta:
        model = MatchOfficials
        fields = [
            'main_referee_name', 'main_referee_mobile',
            'ar1_name', 'ar1_mobile',
            'ar2_name', 'ar2_mobile'
        ]
        widgets = {
            'main_referee_name': forms.TextInput(attrs={'class': 'form-control'}),
            'main_referee_mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254712345678', 'pattern': '\\+254\\d{9}', 'maxlength': '13'}),
            'ar1_name': forms.TextInput(attrs={'class': 'form-control'}),
            'ar1_mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254712345678', 'pattern': '\\+254\\d{9}', 'maxlength': '13'}),
            'ar2_name': forms.TextInput(attrs={'class': 'form-control'}),
            'ar2_mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254712345678', 'pattern': '\\+254\\d{9}', 'maxlength': '13'}),
        }
        labels = {
            'main_referee_name': 'Main Referee Name',
            'main_referee_mobile': 'Main Referee Mobile',
            'ar1_name': 'AR1 Name',
            'ar1_mobile': 'AR1 Mobile',
            'ar2_name': 'AR2 Name',
            'ar2_mobile': 'AR2 Mobile',
        }


class TeamOfficialForm(forms.ModelForm):
    class Meta:
        model = TeamOfficial
        fields = ['team', 'position', 'name', 'mobile']
        widgets = {
            'team': forms.Select(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254712345678', 'pattern': '\\+254\\d{9}', 'maxlength': '13'}),
        }


class PlayingKitForm(forms.ModelForm):
    class Meta:
        model = PlayingKit
        fields = ['team', 'item', 'condition', 'notes']
        widgets = {
            'team': forms.Select(attrs={'class': 'form-control'}),
            'item': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MatchVenueDetailsForm(forms.ModelForm):
    class Meta:
        model = MatchVenueDetails
        exclude = ['match']
        widgets = {
            'home_changing_room': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'away_changing_room': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'seating_arrangement': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ball_boys': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'security_personnel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'field_markings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ambulance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'stretcher': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pitch_condition': forms.Select(attrs={'class': 'form-control'}),
            'weather_before': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Sunny, Clear'}),
            'weather_during': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Cloudy, Light Rain'}),
            'first_half_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'first_half_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'first_half_duration': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minutes'}),
            'second_half_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'second_half_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'second_half_duration': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minutes'}),
            'attendance': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Number of spectators'}),
        }


class StartingLineupForm(forms.ModelForm):
    class Meta:
        model = StartingLineup
        fields = ['team', 'player', 'jersey_number', 'position']
        widgets = {
            'team': forms.Select(attrs={'class': 'form-control'}),
            'player': forms.Select(attrs={'class': 'form-control'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 99}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Forward, Midfielder'}),
        }


class ReservePlayerForm(forms.ModelForm):
    class Meta:
        model = ReservePlayer
        fields = ['team', 'player', 'jersey_number']
        widgets = {
            'team': forms.Select(attrs={'class': 'form-control'}),
            'player': forms.Select(attrs={'class': 'form-control'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control jersey-number-input', 'min': 1, 'max': 99, 'style': 'max-width:70px;'}),
        }


class SubstitutionForm(forms.ModelForm):
    class Meta:
        model = Substitution
        fields = ['team', 'minute', 'player_out', 'player_in', 'jersey_out', 'jersey_in']
        widgets = {
            'team': forms.Select(attrs={'class': 'form-control'}),
            'minute': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 120}),
            'player_out': forms.Select(attrs={'class': 'form-control'}),
            'player_in': forms.Select(attrs={'class': 'form-control'}),
            'jersey_out': forms.NumberInput(attrs={'class': 'form-control jersey-number-input', 'min': 1, 'max': 99, 'style': 'max-width:70px;'}),
            'jersey_in': forms.NumberInput(attrs={'class': 'form-control jersey-number-input', 'min': 1, 'max': 99, 'style': 'max-width:70px;'}),
        }


class CautionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        match = kwargs.pop('match', None)
        super().__init__(*args, **kwargs)
        if match:
            from teams.models import Team, Player
            self.fields['team'].queryset = Team.objects.filter(pk__in=[match.home_team_id, match.away_team_id])
            # If team is chosen in bound data, filter players by that team; else allow both teams' players
            team_id = (self.data.get(self.add_prefix('team')) if self.data else None) or (self.instance.team_id if self.instance and self.instance.pk else None)
            if team_id:
                self.fields['player'].queryset = Player.objects.filter(team_id=team_id)
            else:
                self.fields['player'].queryset = Player.objects.filter(team_id__in=[match.home_team_id, match.away_team_id])
    class Meta:
        model = Caution
        fields = ['player', 'team', 'minute', 'reason', 'jersey_number']
        widgets = {
            'player': forms.Select(attrs={'class': 'form-control'}),
            'team': forms.Select(attrs={'class': 'form-control'}),
            'minute': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 120}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Reason for caution'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 99}),
        }


class ExpulsionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        match = kwargs.pop('match', None)
        super().__init__(*args, **kwargs)
        if match:
            from teams.models import Team, Player
            self.fields['team'].queryset = Team.objects.filter(pk__in=[match.home_team_id, match.away_team_id])
            team_id = (self.data.get(self.add_prefix('team')) if self.data else None) or (self.instance.team_id if self.instance and self.instance.pk else None)
            if team_id:
                self.fields['player'].queryset = Player.objects.filter(team_id=team_id)
            else:
                self.fields['player'].queryset = Player.objects.filter(team_id__in=[match.home_team_id, match.away_team_id])
    class Meta:
        model = Expulsion
        fields = ['player', 'team', 'minute', 'reason', 'jersey_number']
        widgets = {
            'player': forms.Select(attrs={'class': 'form-control'}),
            'team': forms.Select(attrs={'class': 'form-control'}),
            'minute': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 120}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Reason for expulsion'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 99}),
        }


class MatchGoalForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        match = kwargs.pop('match', None)
        super().__init__(*args, **kwargs)
        if match:
            from teams.models import Team, Player
            self.fields['team'].queryset = Team.objects.filter(pk__in=[match.home_team_id, match.away_team_id])
            # Filter player and assist_by by selected team if available
            team_id = (self.data.get(self.add_prefix('team')) if self.data else None) or (self.instance.team_id if self.instance and self.instance.pk else None)
            base_qs = Player.objects.filter(team_id__in=[match.home_team_id, match.away_team_id])
            if team_id:
                self.fields['player'].queryset = base_qs.filter(team_id=team_id)
                self.fields['assist_by'].queryset = base_qs.filter(team_id=team_id)
            else:
                self.fields['player'].queryset = base_qs
                self.fields['assist_by'].queryset = base_qs
    class Meta:
        model = MatchGoal
        fields = ['team', 'player', 'assist_by', 'minute', 'goal_type', 'jersey_number', 'notes']
        widgets = {
            'team': forms.Select(attrs={'class': 'form-control'}),
            'player': forms.Select(attrs={'class': 'form-control'}),
            'assist_by': forms.Select(attrs={'class': 'form-control'}),
            'minute': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 120}),
            'goal_type': forms.Select(attrs={'class': 'form-control'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 99}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Additional notes'}),
        }


class MatchReportForm(forms.ModelForm):
    class Meta:
        model = MatchReport
        fields = [
            'match_number', 'round_number', 'league_level',
            'penalties_not_converted', 'serious_incidents', 'referee_comments'
        ]
        widgets = {
            'match_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., M-2024-001'}),
            'round_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Round 5'}),
            'league_level': forms.TextInput(attrs={'class': 'form-control', 'value': 'FKF County League'}),
            'penalties_not_converted': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'List any penalties awarded but not converted...'
            }),
            'serious_incidents': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 6,
                'placeholder': 'Describe any serious incidents during the match...'
            }),
            'referee_comments': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Additional referee observations and comments...'
            }),
        }
        labels = {
            'match_number': 'Match Number',
            'round_number': 'Round',
            'league_level': 'League Level',
            'penalties_not_converted': 'Penalties Not Converted',
            'serious_incidents': 'Serious Incidents',
            'referee_comments': 'Referee Comments',
        }

class MatchScoreForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['home_score', 'away_score']
        widgets = {
            'home_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'away_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class PreMatchMeetingFormForm(forms.ModelForm):
    """Form for pre-match meeting - main referee fills this"""
    class Meta:
        model = PreMatchMeetingForm
        exclude = ['match', 'referee', 'status', 'submitted_at', 
                   'admin_approved_at', 'admin_approved_by', 'admin_rejection_reason',
                   'manager_approved_at', 'manager_approved_by', 'manager_rejection_reason',
                   'created_at', 'updated_at', 'is_locked',
                   # Auto-filled fields
                   'match_date', 'match_number', 'home_team', 'away_team', 'venue', 'city', 'stadium']
        
        widgets = {
            # Schedule
            'scheduled_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'actual_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'meeting_end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            
            # Match Officials
            'match_commissioner_name': forms.TextInput(attrs={'class': 'form-control'}),
            'match_commissioner_license': forms.TextInput(attrs={'class': 'form-control'}),
            'match_commissioner_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            
            'centre_referee_name': forms.TextInput(attrs={'class': 'form-control'}),
            'centre_referee_license': forms.TextInput(attrs={'class': 'form-control'}),
            'centre_referee_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            
            'asst1_referee_name': forms.TextInput(attrs={'class': 'form-control'}),
            'asst1_referee_license': forms.TextInput(attrs={'class': 'form-control'}),
            'asst1_referee_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            
            'asst2_referee_name': forms.TextInput(attrs={'class': 'form-control'}),
            'asst2_referee_license': forms.TextInput(attrs={'class': 'form-control'}),
            'asst2_referee_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            
            'fourth_official_name': forms.TextInput(attrs={'class': 'form-control'}),
            'fourth_official_license': forms.TextInput(attrs={'class': 'form-control'}),
            'fourth_official_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Team Officials - Home
            'home_head_coach': forms.TextInput(attrs={'class': 'form-control'}),
            'home_head_coach_license': forms.TextInput(attrs={'class': 'form-control'}),
            'home_head_coach_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'home_team_manager': forms.TextInput(attrs={'class': 'form-control'}),
            'home_team_manager_license': forms.TextInput(attrs={'class': 'form-control'}),
            'home_team_manager_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'home_team_doctor': forms.TextInput(attrs={'class': 'form-control'}),
            'home_team_doctor_license': forms.TextInput(attrs={'class': 'form-control'}),
            'home_team_doctor_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Team Officials - Away
            'away_head_coach': forms.TextInput(attrs={'class': 'form-control'}),
            'away_head_coach_license': forms.TextInput(attrs={'class': 'form-control'}),
            'away_head_coach_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'away_team_manager': forms.TextInput(attrs={'class': 'form-control'}),
            'away_team_manager_license': forms.TextInput(attrs={'class': 'form-control'}),
            'away_team_manager_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'away_team_doctor': forms.TextInput(attrs={'class': 'form-control'}),
            'away_team_doctor_license': forms.TextInput(attrs={'class': 'form-control'}),
            'away_team_doctor_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Uniforms - auto-filled, but editable
            'home_gk_shirt_color': forms.TextInput(attrs={'class': 'form-control'}),
            'home_gk_shirt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'home_gk_short_track': forms.TextInput(attrs={'class': 'form-control'}),
            'home_gk_stocking': forms.TextInput(attrs={'class': 'form-control'}),
            'home_playing_unit_shirt': forms.TextInput(attrs={'class': 'form-control'}),
            'home_playing_unit_short': forms.TextInput(attrs={'class': 'form-control'}),
            'home_playing_unit_stocking': forms.TextInput(attrs={'class': 'form-control'}),
            'home_reserve_gk_shirt': forms.TextInput(attrs={'class': 'form-control'}),
            'home_reserve_gk_short_track': forms.TextInput(attrs={'class': 'form-control'}),
            'home_reserve_gk_stocking': forms.TextInput(attrs={'class': 'form-control'}),
            'home_official_shirt': forms.TextInput(attrs={'class': 'form-control'}),
            'home_official_short': forms.TextInput(attrs={'class': 'form-control'}),
            'home_official_stocking': forms.TextInput(attrs={'class': 'form-control'}),
            'home_warm_up_kit': forms.TextInput(attrs={'class': 'form-control'}),
            'home_reserve_track_suit': forms.TextInput(attrs={'class': 'form-control'}),
            
            'away_gk_shirt_color': forms.TextInput(attrs={'class': 'form-control'}),
            'away_gk_shirt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'away_gk_short_track': forms.TextInput(attrs={'class': 'form-control'}),
            'away_gk_stocking': forms.TextInput(attrs={'class': 'form-control'}),
            'away_playing_unit_shirt': forms.TextInput(attrs={'class': 'form-control'}),
            'away_playing_unit_short': forms.TextInput(attrs={'class': 'form-control'}),
            'away_playing_unit_stocking': forms.TextInput(attrs={'class': 'form-control'}),
            'away_reserve_gk_shirt': forms.TextInput(attrs={'class': 'form-control'}),
            'away_reserve_gk_short_track': forms.TextInput(attrs={'class': 'form-control'}),
            'away_reserve_gk_stocking': forms.TextInput(attrs={'class': 'form-control'}),
            'away_official_shirt': forms.TextInput(attrs={'class': 'form-control'}),
            'away_official_short': forms.TextInput(attrs={'class': 'form-control'}),
            'away_official_stocking': forms.TextInput(attrs={'class': 'form-control'}),
            'away_warm_up_kit': forms.TextInput(attrs={'class': 'form-control'}),
            'away_reserve_track_suit': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Field Captains
            'home_field_captain_name': forms.TextInput(attrs={'class': 'form-control'}),
            'home_field_captain_number': forms.TextInput(attrs={'class': 'form-control'}),
            'home_field_captain_arm_band': forms.TextInput(attrs={'class': 'form-control'}),
            'away_field_captain_name': forms.TextInput(attrs={'class': 'form-control'}),
            'away_field_captain_number': forms.TextInput(attrs={'class': 'form-control'}),
            'away_field_captain_arm_band': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Management
            'reporting_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'checking_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'kick_off_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'number_ball_boys': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'shirt_color': forms.TextInput(attrs={'class': 'form-control'}),
            'or_bib_color': forms.TextInput(attrs={'class': 'form-control'}),
            'home_balls_available': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'away_balls_available': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'expected_spectators': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            
            # Medical
            'quality_personnel': forms.TextInput(attrs={'class': 'form-control'}),
            'stretcher_how_many': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'booked_hospital': forms.TextInput(attrs={'class': 'form-control'}),
            'sitting_arrangement': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Security
            'and_company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'nearest_police_post': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Notes
            'attendance_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'home_officials_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'away_officials_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }