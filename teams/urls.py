from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TeamViewSet, PlayerViewSet

router = DefaultRouter()
router.register(r"",        TeamViewSet,  basename="team")
router.register(r"players", PlayerViewSet, basename="player")

urlpatterns = [path("", include(router.urls))]
