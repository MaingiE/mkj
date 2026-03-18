from django import forms
from .models import Team, Player
from django.core.exceptions import ValidationError
import datetime

class TeamRegistrationForm(forms.ModelForm):
    captain_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Captain Name (Optional)'
        })
    )
    
    coordinates = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., -0.05181, 37.6456'
        })
    )
    
    phone_digits = forms.CharField(
        max_length=9,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '712345678',
            'id': 'phone-input',
            'pattern': '[0-9]{9}',
            'maxlength': '9'
        }),
        help_text="Enter 9 digits only (e.g., 712345678). Will be saved as +254XXXXXXXXX"
    )

    class Meta:
        model = Team
        fields = [
            'team_name', 'location', 'home_ground', 
            'map_location', 'contact_person', 'email',
            'logo'
        ]
        widgets = {
            'team_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter team name'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Meru Town'}),
            'home_ground': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Meru Stadium'}),
            'map_location': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Google Maps URL (optional)'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Manager name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'manager@example.com'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        """Validate all fields including phone_digits"""
        cleaned_data = super().clean()
        team_name = cleaned_data.get('team_name')
        email = cleaned_data.get('email')
        phone_digits = cleaned_data.get('phone_digits', '')
        
        if team_name and Team.objects.filter(team_name__iexact=team_name).exists():
            raise ValidationError(f'Team "{team_name}" already exists!')
        
        if email and Team.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered!')
        
        # Validate and create phone number
        if phone_digits:
            # Remove any non-digit characters
            phone_digits = ''.join(filter(str.isdigit, phone_digits))
            
            if len(phone_digits) != 9:
                raise forms.ValidationError({'phone_digits': 'Please enter exactly 9 digits'})
            
            if not phone_digits[0] in ['0', '1', '7']:
                raise forms.ValidationError({'phone_digits': 'Phone number must start with 0, 1, or 7'})
            
            # Create full phone number with +254 prefix
            full_phone = f'+254{phone_digits}'
            
            # Check if already exists (excluding current instance if editing)
            existing = Team.objects.filter(phone_number=full_phone)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError({
                    'phone_digits': f"This phone number (+254{phone_digits}) is already registered to another team."
                })
            
            cleaned_data['phone_number'] = full_phone
        else:
            raise forms.ValidationError({'phone_digits': 'Phone number is required'})
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Set the phone_number from cleaned_data
        instance.phone_number = self.cleaned_data.get('phone_number', '')
        if commit:
            instance.save()
        return instance

class TeamManagerLoginForm(forms.Form):
    team_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your Team Code'
        }),
        label="Team Code"
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        team_code = cleaned_data.get('team_code')
        password = cleaned_data.get('password')
        
        if team_code and password:
            try:
                team = Team.objects.get(team_code=team_code)
                cleaned_data['team'] = team
            except Team.DoesNotExist:
                raise forms.ValidationError("Invalid team code")
        
        return cleaned_data


class PlayerRegistrationForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = [
            'first_name', 'last_name', 'date_of_birth', 
            'id_number', 'fkf_license_number', 'license_expiry_date',
            'position', 'jersey_number', 'photo', 'is_captain'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID/Passport Number'}),
            'fkf_license_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FKF License Number (Optional)'}),
            'license_expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 10', 'min': '1', 'max': '99'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'is_captain': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_id_number(self):
        """Validate ID number format and check for duplicates + IPRS verification"""
        from .id_verification import IDVerification, DuplicatePlayerChecker
        from .external_verification import IPRSVerification
        
        id_number = self.cleaned_data.get('id_number')
        
        # 1. Validate format
        id_number = IDVerification.validate_kenyan_id(id_number)
        
        # 2. Check for duplicates (exclude current player if editing)
        exclude_id = self.instance.id if self.instance.pk else None
        DuplicatePlayerChecker.check_id_number(id_number, exclude_player_id=exclude_id)
        
        # 3. Verify with IPRS (Kenya National Registration Bureau)
        iprs = IPRSVerification()
        first_name = self.data.get('first_name', '').strip()
        last_name = self.data.get('last_name', '').strip()
        dob = self.data.get('date_of_birth')
        
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
            iprs_result = iprs.verify_id_number(id_number, full_name=full_name, date_of_birth=dob)
            
            # Store result for later use
            self.iprs_verification = iprs_result
            
            if not iprs_result['valid'] and iprs_result['verified']:
                # Only raise error if verification was successful but ID is invalid
                errors = iprs_result['errors']
                raise forms.ValidationError(
                    f"IPRS Verification Failed: {'; '.join(errors)}"
                )
        
        return id_number
    
    def clean_jersey_number(self):
        jersey_number = self.cleaned_data.get('jersey_number')
        if jersey_number is not None:
            if jersey_number < 1 or jersey_number > 99:
                raise forms.ValidationError("Jersey number must be between 1 and 99")
        return jersey_number
    
    def clean_date_of_birth(self):
        """Validate age eligibility"""
        from .id_verification import IDVerification
        
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            # Check age eligibility (16-45 years)
            IDVerification.check_age_eligibility(dob, min_age=16, max_age=45)
        return dob
    
    def clean(self):
        """Additional validation for duplicate players by name and DOB + FIFA verification"""
        from .id_verification import DuplicatePlayerChecker
        from .external_verification import FIFAConnectVerification
        from django.utils import timezone
        
        cleaned_data = super().clean()
        
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        date_of_birth = cleaned_data.get('date_of_birth')
        
        if first_name and last_name and date_of_birth:
            # Check for duplicate name + DOB
            exclude_id = self.instance.id if self.instance.pk else None
            DuplicatePlayerChecker.check_name_and_dob(
                first_name, last_name, date_of_birth, 
                exclude_player_id=exclude_id
            )
            
            # Verify with FIFA Connect
            fifa = FIFAConnectVerification()
            player_data = {
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': date_of_birth,
                'nationality': cleaned_data.get('nationality', 'Kenyan'),
                'id_number': cleaned_data.get('id_number')
            }
            
            fifa_result = fifa.verify_player(player_data)
            
            # Store FIFA result for later use
            self.fifa_verification = fifa_result
            
            if not fifa_result['valid'] and fifa_result['verified']:
                # Player has FIFA sanctions or transfer ban
                errors = fifa_result['errors']
                raise forms.ValidationError(
                    f"FIFA Connect Verification Failed: {'; '.join(errors)}"
                )
            
            # Store verification results on instance if saving
            if hasattr(self, 'iprs_verification') or fifa_result.get('verified'):
                verification_data = {
                    'iprs': getattr(self, 'iprs_verification', None),
                    'fifa': fifa_result,
                    'verified_at': timezone.now().isoformat()
                }
                
                # Update instance verification fields
                if hasattr(self, 'iprs_verification'):
                    iprs = self.iprs_verification
                    if iprs.get('verified'):
                        self.instance.iprs_verified = iprs.get('valid', False)
                        self.instance.iprs_verification_date = timezone.now()
                
                if fifa_result.get('verified'):
                    self.instance.fifa_verified = fifa_result.get('valid', False)
                    self.instance.fifa_verification_date = timezone.now()
                    if fifa_result.get('data', {}).get('fifa_id'):
                        self.instance.fifa_id = fifa_result['data']['fifa_id']
                
                self.instance.verification_results = verification_data
                
                # Collect warnings
                warnings = []
                if hasattr(self, 'iprs_verification'):
                    warnings.extend(self.iprs_verification.get('errors', []))
                warnings.extend(fifa_result.get('errors', []))
                
                if warnings:
                    self.instance.verification_warnings = '\n'.join(warnings)
        
        return cleaned_data
        if first_name and last_name and date_of_birth:
            exclude_id = self.instance.id if self.instance.pk else None
            try:
                DuplicatePlayerChecker.check_duplicate_by_name_dob(
                    first_name, last_name, date_of_birth, exclude_player_id=exclude_id
                )
            except forms.ValidationError as e:
                self.add_error(None, e)
        
        return cleaned_data
    
    def clean_license_expiry_date(self):
        expiry_date = self.cleaned_data.get('license_expiry_date')
        if expiry_date:
            if expiry_date < datetime.date.today():
                raise forms.ValidationError("License expiry date cannot be in the past")
        return expiry_date


class TeamKitForm(forms.ModelForm):
    """Form for team to select kit colors including GK kits"""
    
    class Meta:
        model = Team
        fields = [
            # Player Kits
            'home_jersey_color', 'home_shorts_color', 'home_socks_color',
            'away_jersey_color', 'away_shorts_color', 'away_socks_color',
            'third_jersey_color', 'third_shorts_color', 'third_socks_color',
            # GK Kits
            'gk_home_jersey_color', 'gk_home_shorts_color', 'gk_home_socks_color',
            'gk_away_jersey_color', 'gk_away_shorts_color', 'gk_away_socks_color',
            'gk_third_jersey_color', 'gk_third_shorts_color', 'gk_third_socks_color',
        ]
        widgets = {
            # Player Home Kit
            'home_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'home_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'home_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # Player Away Kit
            'away_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'away_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'away_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # Player Third Kit
            'third_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'third_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'third_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # GK Home Kit
            'gk_home_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_home_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_home_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # GK Away Kit
            'gk_away_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_away_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_away_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # GK Third Kit
            'gk_third_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_third_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_third_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check player kits are different
        player_home_same = (
            cleaned_data.get('home_jersey_color') == cleaned_data.get('away_jersey_color') and
            cleaned_data.get('home_shorts_color') == cleaned_data.get('away_shorts_color')
        )
        
        # Check GK kits are different from player kits
        gk_home_diff_player_home = (
            cleaned_data.get('gk_home_jersey_color') != cleaned_data.get('home_jersey_color') or
            cleaned_data.get('gk_home_shorts_color') != cleaned_data.get('home_shorts_color')
        )
        
        gk_away_diff_player_away = (
            cleaned_data.get('gk_away_jersey_color') != cleaned_data.get('away_jersey_color') or
            cleaned_data.get('gk_away_shorts_color') != cleaned_data.get('away_shorts_color')
        )
        
        if player_home_same:
            raise forms.ValidationError("Player Home and Away kits must be different!")
        
        if not gk_home_diff_player_home:
            raise forms.ValidationError("Goalkeeper Home kit must be different from Player Home kit!")
        
        if not gk_away_diff_player_away:
            raise forms.ValidationError("Goalkeeper Away kit must be different from Player Away kit!")
        
        return cleaned_data