"""
Media Manager Portal - CRUD views for News, Gallery & Videos.
Accessible by admin and competition_manager roles.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from mkj_cms.web_views import role_required
from .models import NewsArticle, NewsCategory, GalleryAlbum, GalleryImage, Video
from .forms import NewsArticleForm, NewsCategoryForm, GalleryAlbumForm, VideoForm


# ─── MEDIA MANAGER DASHBOARD ─────────────────────────────────────────────────

@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def media_dashboard_view(request):
    articles = NewsArticle.objects.all()
    albums = GalleryAlbum.objects.all()
    videos = Video.objects.all()
    categories = NewsCategory.objects.all()

    return render(request, 'portal/media/dashboard.html', {
        'total_articles': articles.count(),
        'published_articles': articles.filter(status='published').count(),
        'draft_articles': articles.filter(status='draft').count(),
        'total_albums': albums.count(),
        'total_photos': GalleryImage.objects.count(),
        'total_videos': videos.count(),
        'total_categories': categories.count(),
        'recent_articles': articles[:5],
        'recent_albums': albums[:5],
        'recent_videos': videos[:5],
    })


# ─── NEWS ARTICLES ───────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def article_list_view(request):
    articles = NewsArticle.objects.select_related('category', 'author').all()

    status = request.GET.get('status', '')
    if status:
        articles = articles.filter(status=status)

    q = request.GET.get('q', '')
    if q:
        articles = articles.filter(title__icontains=q)

    return render(request, 'portal/media/article_list.html', {
        'articles': articles,
        'status_filter': status,
        'search_query': q,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def article_create_view(request):
    if request.method == 'POST':
        form = NewsArticleForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            messages.success(request, f'Article "{article.title}" created successfully.')
            return redirect('media_article_list')
    else:
        form = NewsArticleForm()

    return render(request, 'portal/media/article_form.html', {
        'form': form,
        'editing': False,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def article_edit_view(request, pk):
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == 'POST':
        form = NewsArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, f'Article "{article.title}" updated.')
            return redirect('media_article_list')
    else:
        form = NewsArticleForm(instance=article)

    return render(request, 'portal/media/article_form.html', {
        'form': form,
        'article': article,
        'editing': True,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def article_delete_view(request, pk):
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == 'POST':
        title = article.title
        article.delete()
        messages.success(request, f'Article "{title}" deleted.')
        return redirect('media_article_list')
    return render(request, 'portal/media/confirm_delete.html', {
        'object': article,
        'object_type': 'Article',
        'back_url': 'media_article_list',
    })


# ─── NEWS CATEGORIES ─────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def category_manage_view(request):
    categories = NewsCategory.objects.all()
    if request.method == 'POST':
        form = NewsCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created.')
            return redirect('media_categories')
    else:
        form = NewsCategoryForm()

    return render(request, 'portal/media/categories.html', {
        'categories': categories,
        'form': form,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def category_delete_view(request, pk):
    cat = get_object_or_404(NewsCategory, pk=pk)
    if request.method == 'POST':
        cat.delete()
        messages.success(request, 'Category deleted.')
    return redirect('media_categories')


# ─── GALLERY ALBUMS ──────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def album_list_view(request):
    albums = GalleryAlbum.objects.prefetch_related('images').all()
    return render(request, 'portal/media/album_list.html', {
        'albums': albums,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def album_create_view(request):
    if request.method == 'POST':
        form = GalleryAlbumForm(request.POST, request.FILES)
        if form.is_valid():
            album = form.save(commit=False)
            album.created_by = request.user
            album.save()

            # Handle multiple photo uploads
            photos = request.FILES.getlist('photos')
            for i, photo in enumerate(photos):
                GalleryImage.objects.create(
                    album=album,
                    image=photo,
                    order=i,
                )

            messages.success(request, f'Album "{album.title}" created with {len(photos)} photos.')
            return redirect('media_album_list')
    else:
        form = GalleryAlbumForm()

    return render(request, 'portal/media/album_form.html', {
        'form': form,
        'editing': False,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def album_edit_view(request, pk):
    album = get_object_or_404(GalleryAlbum, pk=pk)
    if request.method == 'POST':
        form = GalleryAlbumForm(request.POST, request.FILES, instance=album)
        if form.is_valid():
            form.save()

            # Handle additional photo uploads
            photos = request.FILES.getlist('photos')
            existing_count = album.images.count()
            for i, photo in enumerate(photos):
                GalleryImage.objects.create(
                    album=album,
                    image=photo,
                    order=existing_count + i,
                )

            if photos:
                messages.success(request, f'Album updated. {len(photos)} new photos added.')
            else:
                messages.success(request, f'Album "{album.title}" updated.')
            return redirect('media_album_list')
    else:
        form = GalleryAlbumForm(instance=album)

    return render(request, 'portal/media/album_form.html', {
        'form': form,
        'album': album,
        'editing': True,
        'images': album.images.all(),
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def album_delete_view(request, pk):
    album = get_object_or_404(GalleryAlbum, pk=pk)
    if request.method == 'POST':
        title = album.title
        album.delete()
        messages.success(request, f'Album "{title}" and all its photos deleted.')
        return redirect('media_album_list')
    return render(request, 'portal/media/confirm_delete.html', {
        'object': album,
        'object_type': 'Album',
        'back_url': 'media_album_list',
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def photo_delete_view(request, pk):
    image = get_object_or_404(GalleryImage, pk=pk)
    album_pk = image.album.pk
    if request.method == 'POST':
        image.delete()
        messages.success(request, 'Photo removed.')
    return redirect('media_album_edit', pk=album_pk)


# ─── VIDEOS ──────────────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def video_list_view(request):
    videos = Video.objects.all()
    return render(request, 'portal/media/video_list.html', {
        'videos': videos,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def video_create_view(request):
    if request.method == 'POST':
        form = VideoForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.uploaded_by = request.user
            video.save()
            messages.success(request, f'Video "{video.title}" added.')
            return redirect('media_video_list')
    else:
        form = VideoForm()

    return render(request, 'portal/media/video_form.html', {
        'form': form,
        'editing': False,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def video_edit_view(request, pk):
    video = get_object_or_404(Video, pk=pk)
    if request.method == 'POST':
        form = VideoForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, f'Video "{video.title}" updated.')
            return redirect('media_video_list')
    else:
        form = VideoForm(instance=video)

    return render(request, 'portal/media/video_form.html', {
        'form': form,
        'video': video,
        'editing': True,
    })


@login_required
@role_required('admin', 'competition_manager', 'media_manager')
def video_delete_view(request, pk):
    video = get_object_or_404(Video, pk=pk)
    if request.method == 'POST':
        title = video.title
        video.delete()
        messages.success(request, f'Video "{title}" deleted.')
        return redirect('media_video_list')
    return render(request, 'portal/media/confirm_delete.html', {
        'object': video,
        'object_type': 'Video',
        'back_url': 'media_video_list',
    })
