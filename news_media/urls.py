from django.urls import path
from . import views

app_name = "news_media"

urlpatterns = [
    path("news/", views.news_list_view, name="news_list"),
    path("news/<slug:slug>/", views.news_detail_view, name="news_detail"),
    path("gallery/", views.gallery_list_view, name="gallery_list"),
    path("gallery/<slug:slug>/", views.gallery_detail_view, name="gallery_detail"),
    path("videos/", views.videos_list_view, name="videos_list"),
]
