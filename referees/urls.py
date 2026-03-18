from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RefereeListView, RefereeDetailView, RefereeRegisterView, RefereeApproveView,
    MyAppointmentsView, AppointmentConfirmView,
    AppointmentViewSet, AvailabilityViewSet, ReviewViewSet,
)

router = DefaultRouter()
router.register(r"appointments",  AppointmentViewSet,  basename="appointment")
router.register(r"availability",  AvailabilityViewSet, basename="availability")
router.register(r"reviews",       ReviewViewSet,       basename="review")

urlpatterns = [
    path("",                                    RefereeListView.as_view(),    name="referee-list"),
    path("register/",                           RefereeRegisterView.as_view(),name="referee-register"),
    path("<int:pk>/",                           RefereeDetailView.as_view(),  name="referee-detail"),
    path("<int:pk>/approve/",                   RefereeApproveView.as_view(), name="referee-approve"),
    path("my-appointments/",                    MyAppointmentsView.as_view(), name="my-appointments"),
    path("appointments/<int:pk>/confirm/",      AppointmentConfirmView.as_view(), name="appointment-confirm"),
    path("", include(router.urls)),
]
