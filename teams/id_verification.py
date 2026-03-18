"""
Player ID Verification and Duplicate Prevention System
Implements multiple layers of verification for player registration
"""

from django.core.exceptions import ValidationError
from django.db.models import Q
from datetime import date, datetime, timedelta
import re


class IDVerification:
    """Kenya National ID verification"""
    
    @staticmethod
    def validate_kenyan_id(id_number):
        """
        Validate Kenya National ID format
        Format: 8 digits or new format with letters
        """
        if not id_number:
            raise ValidationError("ID number is required")
        
        # Remove spaces and convert to string
        id_number = str(id_number).replace(' ', '').strip()
        
        # Old format: 8 digits
        old_format = re.match(r'^\d{8}$', id_number)
        
        # New format: Can contain letters and numbers (e.g., 12345678A)
        new_format = re.match(r'^[A-Z0-9]{7,12}$', id_number.upper())
        
        if not (old_format or new_format):
            raise ValidationError(
                "Invalid ID number format. Must be 8 digits (e.g., 12345678) "
                "or new format with 7-12 characters (e.g., 12345678A)"
            )
        
        return id_number.upper()
    
    @staticmethod
    def check_age_eligibility(date_of_birth, min_age=16, max_age=45):
        """Check if player meets age requirements"""
        if not date_of_birth:
            raise ValidationError("Date of birth is required")
        
        today = date.today()
        age = today.year - date_of_birth.year - (
            (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
        )
        
        if age < min_age:
            raise ValidationError(
                f"Player must be at least {min_age} years old. Current age: {age}"
            )
        
        if age > max_age:
            raise ValidationError(
                f"Player cannot be older than {max_age} years. Current age: {age}"
            )
        
        return age


class DuplicatePlayerChecker:
    """Check for duplicate player registrations across the league"""
    
    @staticmethod
    def check_id_number(id_number, exclude_player_id=None):
        """Check if ID number already exists in the system"""
        from teams.models import Player
        
        query = Player.objects.filter(id_number=id_number)
        
        if exclude_player_id:
            query = query.exclude(id=exclude_player_id)
        
        if query.exists():
            existing_player = query.first()
            raise ValidationError(
                f"Player with ID {id_number} already registered in the league. "
                f"Name: {existing_player.full_name}, "
                f"Team: {existing_player.team.team_name}"
            )
        
        return True
    
    @staticmethod
    def check_duplicate_by_name_dob(first_name, last_name, date_of_birth, exclude_player_id=None):
        """Check for potential duplicates using name and date of birth"""
        from teams.models import Player
        
        query = Player.objects.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name,
            date_of_birth=date_of_birth
        )
        
        if exclude_player_id:
            query = query.exclude(id=exclude_player_id)
        
        if query.exists():
            existing_player = query.first()
            raise ValidationError(
                f"A player with the same name and date of birth already exists. "
                f"Team: {existing_player.team.team_name}, "
                f"ID: {existing_player.id_number}"
            )
        
        return True
    
    @staticmethod
    def check_active_registration(id_number):
        """Check if player has active registration in current season"""
        from teams.models import Player
        
        player = Player.objects.filter(id_number=id_number).first()
        
        if player:
            # Check if player is suspended
            if player.is_suspended and player.suspension_end:
                if player.suspension_end >= date.today():
                    raise ValidationError(
                        f"Player is currently suspended until {player.suspension_end}. "
                        f"Reason: {player.suspension_reason}"
                    )
            
            return {
                'exists': True,
                'player': player,
                'team': player.team.team_name,
                'jersey_number': player.jersey_number,
                'is_captain': player.is_captain
            }
        
        return {'exists': False}


class TransferEligibilityChecker:
    """Check if player is eligible for transfer"""
    
    @staticmethod
    def check_transfer_cooldown(player, days=90):
        """
        Check if player has recently transferred
        FIFA rules: minimum 90 days between transfers
        """
        from teams.models import TransferRequest
        
        recent_transfers = TransferRequest.objects.filter(
            player=player,
            status='approved',
            approved_date__gte=datetime.now() - timedelta(days=days)
        )
        
        if recent_transfers.exists():
            last_transfer = recent_transfers.first()
            days_since = (datetime.now().date() - last_transfer.approved_date.date()).days
            days_remaining = days - days_since
            
            raise ValidationError(
                f"Player transferred {days_since} days ago. "
                f"Must wait {days_remaining} more days before next transfer."
            )
        
        return True
    
    @staticmethod
    def check_matches_played(player, min_matches=5):
        """Check if player has played minimum matches to be eligible for transfer"""
        if player.matches_played < min_matches:
            raise ValidationError(
                f"Player must play at least {min_matches} matches before transfer. "
                f"Current matches: {player.matches_played}"
            )
        
        return True


def verify_player_registration(player_data):
    """
    Complete verification workflow for player registration
    
    Args:
        player_data: dict with keys: first_name, last_name, date_of_birth, 
                     id_number, exclude_player_id (optional)
    
    Returns:
        dict: verification results
    
    Raises:
        ValidationError: if any verification fails
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'player_info': None
    }
    
    try:
        # 1. Validate ID format
        id_number = IDVerification.validate_kenyan_id(player_data['id_number'])
        
        # 2. Check age eligibility
        age = IDVerification.check_age_eligibility(player_data['date_of_birth'])
        results['age'] = age
        
        # 3. Check for duplicate ID
        DuplicatePlayerChecker.check_id_number(
            id_number,
            exclude_player_id=player_data.get('exclude_player_id')
        )
        
        # 4. Check for duplicate by name and DOB
        DuplicatePlayerChecker.check_duplicate_by_name_dob(
            player_data['first_name'],
            player_data['last_name'],
            player_data['date_of_birth'],
            exclude_player_id=player_data.get('exclude_player_id')
        )
        
        # 5. Check if player has active registration
        active_check = DuplicatePlayerChecker.check_active_registration(id_number)
        if active_check['exists']:
            results['warnings'].append(
                f"Player already registered with {active_check['team']}"
            )
            results['player_info'] = active_check
        
        results['valid'] = True
        results['id_number'] = id_number
        
    except ValidationError as e:
        results['valid'] = False
        results['errors'].append(str(e))
    
    return results


# Age categories for youth leagues
AGE_CATEGORIES = {
    'U17': {'min': 14, 'max': 17, 'name': 'Under 17'},
    'U20': {'min': 17, 'max': 20, 'name': 'Under 20'},
    'U23': {'min': 20, 'max': 23, 'name': 'Under 23'},
    'SENIOR': {'min': 18, 'max': 45, 'name': 'Senior'},
}


def get_player_age_category(date_of_birth):
    """Determine which age category a player belongs to"""
    from datetime import date
    
    today = date.today()
    age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )
    
    for category_code, category_info in AGE_CATEGORIES.items():
        if category_info['min'] <= age <= category_info['max']:
            return {
                'code': category_code,
                'name': category_info['name'],
                'age': age
            }
    
    return None
