from django.contrib import admin
from .models import NewsCategory, NewsArticle, GalleryAlbum, GalleryImage, Video


@admin.register(NewsCategory)
class NewsCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 3
    fields = ("image", "caption", "order")


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "is_featured", "is_highlight", "published_at")
    list_filter = ("status", "category", "is_featured", "is_highlight")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("status", "is_featured", "is_highlight")
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        if not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(GalleryAlbum)
class GalleryAlbumAdmin(admin.ModelAdmin):
    list_display = ("title", "event_date", "is_published", "photo_count", "created_at")
    list_filter = ("is_published",)
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [GalleryImageInline]

    def photo_count(self, obj):
        return obj.images.count()
    photo_count.short_description = "Photos"

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "is_featured", "is_published", "created_at")
    list_filter = ("source", "is_featured", "is_published")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_featured", "is_published")

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
