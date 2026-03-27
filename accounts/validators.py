import re

from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    """
    Require at least one uppercase letter, one lowercase letter,
    one digit, and one special character.
    """

    def validate(self, password, user=None):
        errors = []
        if not re.search(r'[A-Z]', password):
            errors.append('at least one uppercase letter')
        if not re.search(r'[a-z]', password):
            errors.append('at least one lowercase letter')
        if not re.search(r'\d', password):
            errors.append('at least one number')
        if not re.search(r'[^A-Za-z0-9]', password):
            errors.append('at least one special character (!@#$%^&* etc.)')
        if errors:
            raise ValidationError(
                'Password must contain ' + ', '.join(errors) + '.',
                code='password_too_weak',
            )

    def get_help_text(self):
        return (
            'Your password must contain at least one uppercase letter, '
            'one lowercase letter, one number, and one special character.'
        )
