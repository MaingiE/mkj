"""
MKJ SUPA CUP Accounts — Serializers
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class MKJTokenObtainSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer — embeds user role and name in the token payload
    and returns user profile with the tokens.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"]       = user.role
        token["full_name"]  = user.get_full_name()
        token["email"]      = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Attach full user profile to login response
        data["user"] = UserProfileSerializer(self.user).data
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    full_name   = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model  = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name",
            "phone", "role", "role_display", "county",
            "profile_photo", "date_joined", "is_active",
        ]
        read_only_fields = ["id", "date_joined", "is_active"]

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserRegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label="Confirm Password")

    class Meta:
        model  = User
        fields = [
            "email", "first_name", "last_name", "phone",
            "role", "county", "password", "password2",
        ]

    def validate(self, data):
        if data["password"] != data.pop("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return data

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
