from django import forms
from .models import NewsArticle, NewsCategory, GalleryAlbum, GalleryImage, Video


class NewsArticleForm(forms.ModelForm):
    class Meta:
        model = NewsArticle
        fields = [
            "title", "category", "featured_image", "excerpt",
            "content", "is_highlight", "is_featured", "status",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. MKJ SUPA CUP 2026 Draw Ceremony Held in Nairobi"}),
            "excerpt": forms.Textarea(attrs={"rows": 3, "placeholder": "Short summary shown in listings..."}),
            "content": forms.Textarea(attrs={"rows": 12, "placeholder": "Full article body..."}),
        }


class NewsCategoryForm(forms.ModelForm):
    class Meta:
        model = NewsCategory
        fields = ["name", "icon"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Match Reports"}),
            "icon": forms.TextInput(attrs={"placeholder": "bi-tag"}),
        }


class GalleryAlbumForm(forms.ModelForm):
    class Meta:
        model = GalleryAlbum
        fields = ["title", "description", "cover_image", "event_date", "is_published"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. MKJ SUPA CUP 2026 Opening Ceremony"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Brief album description..."}),
            "event_date": forms.DateInput(attrs={"type": "date"}),
        }


class VideoForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = [
            "title", "description", "thumbnail", "source",
            "video_file", "video_url", "duration",
            "is_featured", "is_published",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. MKJ SUPA CUP 2026 Highlights — Nairobi vs Mombasa"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Video description..."}),
            "video_url": forms.URLInput(attrs={"placeholder": "https://www.youtube.com/watch?v=..."}),
            "duration": forms.TextInput(attrs={"placeholder": "e.g. 3:45"}),
        }
