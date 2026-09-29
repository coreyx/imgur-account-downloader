"""Metadata preservation engine: EXIF injection, filesystem timestamps, and JSON sidecars."""

from __future__ import annotations

import datetime
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ImgurAlbum, ImgurImage

logger = logging.getLogger(__name__)

# Optional Windows API for setting file creation time (ctime)
HAS_WIN32 = False
try:
    import pywintypes
    import win32con
    import win32file

    HAS_WIN32 = True
except ImportError:
    pass

# Piexif for lossless EXIF modification on JPEGs
HAS_PIEXIF = False
try:
    import piexif
    import piexif.helper

    HAS_PIEXIF = True
except ImportError:
    pass


def format_exif_datetime(timestamp: Optional[int]) -> Optional[str]:
    """Format Unix timestamp as standard EXIF datetime string 'YYYY:MM:DD HH:MM:SS'."""
    if timestamp is None:
        return None
    try:
        dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        return dt.strftime("%Y:%m:%d %H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return None


def set_file_timestamps(filepath: str | Path, timestamp: Optional[int]) -> None:
    """Set file access, modification, and (on Windows) creation times to the timestamp."""
    if timestamp is None:
        return

    path_obj = Path(filepath)
    if not path_obj.exists():
        return

    # 1. Standard POSIX / cross-platform mtime & atime
    try:
        os.utime(path_obj, (timestamp, timestamp))
    except Exception as e:
        logger.debug("Failed setting os.utime for %s: %s", filepath, e)

    # 2. Windows-specific creation time (ctime)
    if HAS_WIN32 and os.name == "nt":
        try:
            wintime = pywintypes.Time(int(timestamp))
            handle = win32file.CreateFile(
                str(path_obj),
                win32con.GENERIC_WRITE,
                win32con.FILE_SHARE_READ
                | win32con.FILE_SHARE_WRITE
                | win32con.FILE_SHARE_DELETE,
                None,
                win32con.OPEN_EXISTING,
                0,
                None,
            )
            try:
                win32file.SetFileTime(handle, wintime, wintime, wintime)
            finally:
                win32file.CloseHandle(handle)
        except Exception as e:
            logger.debug("Failed setting Windows ctime for %s: %s", filepath, e)


def embed_jpeg_exif(filepath: str | Path, image_meta: ImgurImage) -> bool:
    """Embed EXIF metadata losslessly into a JPEG file without recompressing."""
    if not HAS_PIEXIF:
        return False

    path_obj = Path(filepath)
    try:
        with open(path_obj, "rb") as f:
            data = f.read()

        # Load existing exif or initialize new dict
        try:
            exif_dict = piexif.load(data)
        except Exception:
            exif_dict = {
                "0th": {},
                "Exif": {},
                "GPS": {},
                "1st": {},
                "interop": {},
            }

        zeroth = exif_dict.get("0th", {})
        exif = exif_dict.get("Exif", {})

        # 1. Description and Title
        desc_parts = []
        if image_meta.title:
            desc_parts.append(image_meta.title)
        if image_meta.description:
            desc_parts.append(image_meta.description)
        full_desc = " - ".join(desc_parts)

        if full_desc:
            zeroth[piexif.ImageIFD.ImageDescription] = full_desc.encode(
                "utf-8", errors="replace"
            )

        # 2. Software
        zeroth[piexif.ImageIFD.Software] = b"Imgur Account Downloader"

        # 3. Datetime
        exif_dt = format_exif_datetime(image_meta.datetime)
        if exif_dt:
            dt_bytes = exif_dt.encode("ascii")
            zeroth[piexif.ImageIFD.DateTime] = dt_bytes
            exif[piexif.ExifIFD.DateTimeOriginal] = dt_bytes
            exif[piexif.ExifIFD.DateTimeDigitized] = dt_bytes

        # 4. UserComment with structured details
        comment_info = {
            "imgur_id": image_meta.id,
            "url": image_meta.link,
            "views": image_meta.views,
            "bandwidth": image_meta.bandwidth,
            "album_ids": image_meta.album_ids,
        }
        comment_str = json.dumps(comment_info)
        exif[piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(
            comment_str, encoding="unicode"
        )

        # 5. Windows Explorer specific tags (XPTitle, XPComment, XPAuthor)
        if image_meta.title:
            zeroth[piexif.ImageIFD.XPTitle] = image_meta.title.encode("utf-16le")
        if full_desc:
            zeroth[piexif.ImageIFD.XPComment] = full_desc.encode("utf-16le")
        if image_meta.tags:
            zeroth[piexif.ImageIFD.XPKeywords] = ";".join(image_meta.tags).encode(
                "utf-16le"
            )

        exif_dict["0th"] = zeroth
        exif_dict["Exif"] = exif

        exif_bytes = piexif.dump(exif_dict)
        out_buf = io.BytesIO()
        piexif.insert(exif_bytes, data, out_buf)

        with open(path_obj, "wb") as f:
            f.write(out_buf.getvalue())

        return True

    except Exception as e:
        logger.debug("Failed embedding EXIF for %s: %s", filepath, e)
        return False


def apply_image_metadata(
    filepath: str | Path,
    image_meta: ImgurImage,
    embed_exif: bool = True,
    set_timestamps: bool = True,
    write_sidecar: bool = False,
) -> None:
    """Apply all available metadata to the image file and directory."""
    path_obj = Path(filepath)
    ext = path_obj.suffix.lower()

    # 1. Embed EXIF for JPEGs
    if embed_exif and ext in (".jpg", ".jpeg"):
        embed_jpeg_exif(path_obj, image_meta)

    # 2. Set filesystem timestamps
    if set_timestamps and image_meta.datetime:
        set_file_timestamps(path_obj, image_meta.datetime)

    # 3. Optional individual sidecar JSON
    if write_sidecar:
        sidecar_path = path_obj.with_name(f"{path_obj.name}.json")
        try:
            with open(sidecar_path, "w", encoding="utf-8") as f:
                json.dump(image_meta.to_dict(), f, indent=2, ensure_ascii=False)
            if set_timestamps and image_meta.datetime:
                set_file_timestamps(sidecar_path, image_meta.datetime)
        except Exception as e:
            logger.debug("Failed writing sidecar JSON for %s: %s", filepath, e)


def write_album_metadata(
    album_dir: str | Path,
    album: ImgurAlbum,
    set_timestamps: bool = True,
) -> Path:
    """Write album_metadata.json and README.md into the album folder."""
    dir_path = Path(album_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    # 1. JSON metadata file
    meta_path = dir_path / "album_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(album.to_dict(), f, indent=2, ensure_ascii=False)

    # 2. Human-readable README.md
    readme_path = dir_path / "README.md"
    if album.id.startswith("_"):
        readme_lines = [
            f"# {album.display_title}",
            "",
            "- **Collection Type:** Non-Album Media (Catch-All)",
            f"- **Total Images:** {len(album.images)}",
        ]
    else:
        readme_lines = [
            f"# {album.display_title}",
            "",
            f"- **Imgur Album ID:** `{album.id}`",
            f"- **URL:** [{album.link or f'https://imgur.com/a/{album.id}'}]({album.link or f'https://imgur.com/a/{album.id}'})",
            f"- **Date Created:** {album.datetime_iso or 'Unknown'}",
            f"- **Total Images:** {len(album.images)}",
        ]
    if album.views is not None:
        readme_lines.append(f"- **Views:** {album.views:,}")
    if album.privacy:
        readme_lines.append(f"- **Privacy:** `{album.privacy}`")
    if album.description:
        readme_lines.extend(["", "### Description", "", album.description])

    readme_lines.extend(["", "### Images in this Album", ""])
    for idx, img in enumerate(album.images, start=1):
        name_or_id = img.title or img.id
        desc_str = f" - *{img.description}*" if img.description else ""
        date_str = f" ({img.datetime_iso[:10]})" if img.datetime_iso else ""
        readme_lines.append(
            f"{idx}. **[{img.id}]** {name_or_id}{desc_str}{date_str}"
        )

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(readme_lines) + "\n")

    # Set timestamps for metadata files and album directory
    if set_timestamps and album.datetime:
        set_file_timestamps(meta_path, album.datetime)
        set_file_timestamps(readme_path, album.datetime)
        set_file_timestamps(dir_path, album.datetime)

    return meta_path
