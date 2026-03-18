from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView, LogoutView, RegisterView,
    ProfileView, ChangePasswordView,
    UserListView, UserDetailView,
)

urlpatterns = [
    # ── JWT AUTH ──────────────────────────────────────────────────────────────
    path("login/",           LoginView.as_view(),         name="auth-login"),
    path("logout/",          LogoutView.as_view(),         name="auth-logout"),
    path("token/refresh/",   TokenRefreshView.as_view(),   name="token-refresh"),

    # ── USER ──────────────────────────────────────────────────────────────────
    path("register/",        RegisterView.as_view(),       name="auth-register"),
    path("profile/",         ProfileView.as_view(),        name="auth-profile"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),

    # ── USER MANAGEMENT ───────────────────────────────────────────────────────
    path("users/",           UserListView.as_view(),       name="user-list"),
    path("users/<int:pk>/",  UserDetailView.as_view(),     name="user-detail"),
]
