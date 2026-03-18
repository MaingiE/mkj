from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify


class NewsCategory(models.Model):
    """Categories for news articles (e.g., Match Reports, Transfers, Announcements)."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    icon = models.CharField(max_length=50, default="bi-tag", help_text="Bootstrap Icon class")

    class Meta:
        verbose_name_plural = "News Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class NewsArticle(models.Model):
    """News articles and highlights."""
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
    ]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True, blank=True)
    category = models.ForeignKey(
        NewsCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="articles"
    )
    featured_image = models.ImageField(upload_to="news/images/", blank=True, null=True)
    excerpt = models.TextField(max_length=500, blank=True, help_text="Short summary shown in listings")
    content = models.TextField(help_text="Full article body")
    is_highlight = models.BooleanField(default=False, help_text="Mark as a highlight for featured display")
    is_featured = models.BooleanField(default=False, help_text="Pin to top of news page")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="news_articles"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while NewsArticle.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def reading_time(self):
        word_count = len(self.content.split())
        return max(1, word_count // 200)


class GalleryAlbum(models.Model):
    """Photo gallery albums."""
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="gallery/covers/", blank=True, null=True)
    event_date = models.DateField(null=True, blank=True, help_text="Date of the event in photos")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_date", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while GalleryAlbum.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def photo_count(self):
        return self.images.count()

    @property
    def display_cover(self):
        if self.cover_image:
            return self.cover_image.url
        first = self.images.first()
        return first.image.url if first else None


class GalleryImage(models.Model):
    """Individual photos within a gallery album."""
    album = models.ForeignKey(GalleryAlbum, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="gallery/photos/")
    caption = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "uploaded_at"]

    def __str__(self):
        return self.caption or f"Photo #{self.order} — {self.album.title}"


class Video(models.Model):
    """Video content — supports both uploads and YouTube/external embeds."""
    SOURCE_CHOICES = [
        ("upload", "Direct Upload"),
        ("youtube", "YouTube"),
        ("external", "External URL"),
    ]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True, blank=True)
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to="videos/thumbnails/", blank=True, null=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="youtube")
    video_file = models.FileField(
        upload_to="videos/uploads/", blank=True, null=True,
        help_text="For direct uploads (MP4 recommended)"
    )
    video_url = models.URLField(
        blank=True, help_text="YouTube URL or external video link"
    )
    duration = models.CharField(max_length=20, blank=True, help_text="e.g. 3:45")
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Video.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def embed_url(self):
        """Convert YouTube watch URLs to embed URLs."""
        if self.source == "youtube" and self.video_url:
            url = self.video_url
            if "watch?v=" in url:
                video_id = url.split("watch?v=")[1].split("&")[0]
                return f"https://www.youtube.com/embed/{video_id}"
            if "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]
                return f"https://www.youtube.com/embed/{video_id}"
            if "/embed/" in url:
                return url
        return self.video_url or ""

    @property
    def youtube_id(self):
        if self.source != "youtube" or not self.video_url:
            return None
        url = self.video_url
        if "watch?v=" in url:
            return url.split("watch?v=")[1].split("&")[0]
        if "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        if "/embed/" in url:
            return url.split("/embed/")[1].split("?")[0]
        return None
