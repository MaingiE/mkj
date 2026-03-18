from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompetitionViewSet, VenueViewSet, PoolViewSet, FixtureViewSet, PoolTeamManageView

router = DefaultRouter()
router.register(r"",        CompetitionViewSet, basename="competition")
router.register(r"venues",  VenueViewSet,       basename="venue")
router.register(r"pools",   PoolViewSet,        basename="pool")
router.register(r"fixtures",FixtureViewSet,     basename="fixture")

urlpatterns = [
    path("pools/add-team/", PoolTeamManageView.as_view(), name="pool-add-team"),
    path("", include(router.urls)),
]
