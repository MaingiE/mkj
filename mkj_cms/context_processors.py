"""
MKJ SUPA CUP - Custom Template Context Processors
Injected into every template automatically via TEMPLATES settings.
"""
from django.conf import settings


def seo_context(request):
    """
    Inject SEO-related settings into every template context.
    Provides SITE_URL, SITE_NAME, SITE_DESCRIPTION so templates
    never need to hardcode the domain.
    """
    return {
        'SITE_URL': getattr(settings, 'SITE_URL', 'https://mkjsupacup.com').rstrip('/'),
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'MKJ SUPA CUP'),
        'SITE_DESCRIPTION': getattr(settings, 'SITE_DESCRIPTION', ''),
    }
