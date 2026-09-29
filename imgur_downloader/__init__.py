"""Imgur Account Downloader & Organizer.

Retrieves and organizes all images from an Imgur account by album with maximal metadata preservation.
"""

__version__ = "1.0.0"

from .archive import LocalArchive, find_local_archive
from .client import ImgurClient
from .models import ImgurAlbum, ImgurImage
from .organizer import ArchiveOrganizer

__all__ = [
    "ImgurClient",
    "LocalArchive",
    "ArchiveOrganizer",
    "ImgurAlbum",
    "ImgurImage",
    "find_local_archive",
]
