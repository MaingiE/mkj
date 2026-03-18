from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SquadSubmitView, SquadListView, SquadApproveView,
    MatchReportViewSet, MatchReportApproveView,
)

router = DefaultRouter()
router.register(r"reports", MatchReportViewSet, basename="match-report")

urlpatterns = [
    # Squad
    path("squads/",                  SquadSubmitView.as_view(),    name="squad-submit"),
    path("squads/list/",             SquadListView.as_view(),      name="squad-list"),
    path("squads/<int:pk>/approve/", SquadApproveView.as_view(),   name="squad-approve"),
    # Reports
    path("reports/<int:pk>/approve/",MatchReportApproveView.as_view(), name="report-approve"),
    path("", include(router.urls)),
]
