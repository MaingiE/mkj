from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend:
    def authenticate(self, request, email=None, password=None, username=None, **kwargs):
        # Accept 'username' kwarg for compatibility with Django admin
        lookup = email or username
        if lookup is None:
            return None
        try:
            user = User.objects.get(email__iexact=lookup)
        except User.DoesNotExist:
            return None

        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
