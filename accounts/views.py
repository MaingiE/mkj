1"""
MKJ SUPA CUP Accounts - Views & Permissions
"""
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .serializers import (
    MKJTokenObtainSerializer, UserProfileSerializer,
    UserRegisterSerializer, ChangePasswordSerializer,
)
from .permissions import (
    IsCompetitionManager, IsRefereeManager, IsReferee,
    IsTeamManager, IsAdminOrCompetitionManager,
)

User = get_user_model()


# ── AUTH VIEWS ────────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    """POST /api/v1/auth/login/ - returns access+refresh tokens + user profile"""
    serializer_class = MKJTokenObtainSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["auth"], summary="Login - returns JWT tokens + user profile")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ - blacklists the refresh token"""
    @extend_schema(tags=["auth"], summary="Logout - blacklists refresh token")
    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()
            return Response({"detail": "Successfully logged out."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register/ - create new user"""
    serializer_class   = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["auth"], summary="Register new user")
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"detail": "Account created. Awaiting approval if applicable.", "user_id": user.id},
            status=status.HTTP_201_CREATED
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/auth/profile/ - view or update own profile"""
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    @extend_schema(tags=["auth"], summary="Get or update my profile")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/"""
    @extend_schema(tags=["auth"], summary="Change own password")
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response({"detail": "Password updated successfully."})


# ── USER MANAGEMENT (Admin / Competition Manager) ─────────────────────────────

class UserListView(generics.ListAPIView):
    """GET /api/v1/auth/users/ - list all users (admin only)"""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsAdminOrCompetitionManager]
    filterset_fields   = ["role", "county", "is_active"]
    search_fields      = ["first_name", "last_name", "email"]

    def get_queryset(self):
        return User.objects.all().order_by("last_name")

    @extend_schema(tags=["auth"], summary="List all system users")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/v1/auth/users/<id>/"""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsAdminOrCompetitionManager]
    queryset           = User.objects.all()

    @extend_schema(tags=["auth"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
