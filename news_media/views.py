from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import NewsArticle, NewsCategory, GalleryAlbum, Video


def news_list_view(request):
    """Public news listing with category filter and search."""
    articles = NewsArticle.objects.filter(status="published").select_related("category", "author")
    categories = NewsCategory.objects.all()

    # Filters
    category_slug = request.GET.get("category", "")
    search = request.GET.get("q", "")

    if category_slug:
        articles = articles.filter(category__slug=category_slug)
    if search:
        articles = articles.filter(title__icontains=search)

    # Featured / highlights
    featured = articles.filter(is_featured=True).first()
    highlights = articles.filter(is_highlight=True)[:4]

    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "public/news_list.html", {
        "active_page": "news_media",
        "page_obj": page_obj,
        "featured": featured,
        "highlights": highlights,
        "categories": categories,
        "current_category": category_slug,
        "search_query": search,
    })


def news_detail_view(request, slug):
    """Single article detail page."""
    article = get_object_or_404(NewsArticle, slug=slug, status="published")
    related = (
        NewsArticle.objects.filter(status="published", category=article.category)
        .exclude(pk=article.pk)[:3]
    )
    return render(request, "public/news_detail.html", {
        "active_page": "news_media",
        "article": article,
        "related": related,
    })


def gallery_list_view(request):
    """Public gallery albums listing."""
    albums = GalleryAlbum.objects.filter(is_published=True).prefetch_related("images")
    paginator = Paginator(albums, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "public/gallery_list.html", {
        "active_page": "news_media",
        "page_obj": page_obj,
    })


def gallery_detail_view(request, slug):
    """Single album with all photos in a lightbox-style grid."""
    album = get_object_or_404(GalleryAlbum, slug=slug, is_published=True)
    images = album.images.all()
    return render(request, "public/gallery_detail.html", {
        "active_page": "news_media",
        "album": album,
        "images": images,
    })


def videos_list_view(request):
    """Public video listing — uploads + YouTube embeds."""
    videos = Video.objects.filter(is_published=True)
    featured_video = videos.filter(is_featured=True).first()

    paginator = Paginator(videos, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "public/videos_list.html", {
        "active_page": "news_media",
        "page_obj": page_obj,
        "featured_video": featured_video,
    })
