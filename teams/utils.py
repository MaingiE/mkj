"""Utility helpers for the teams app."""
import base64
import logging
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


def save_base64_photo(player, base64_string: str) -> bool:
    """
    Decode a Base64-encoded IPRS photo and save it to the player's
    iprs_photo ImageField.

    Returns True on success, False on failure.
    """
    if not base64_string:
        return False
    try:
        photo_data = base64.b64decode(base64_string)
        filename = f"iprs_{player.national_id_number or player.pk}.jpg"
        player.iprs_photo.save(filename, ContentFile(photo_data), save=False)
        return True
    except Exception:
        logger.exception("Failed to save IPRS photo for player %s", player.pk)
        return False
