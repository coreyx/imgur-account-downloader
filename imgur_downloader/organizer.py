"""Album and image organizer: structures files into album folders, applies metadata, and builds catalog."""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn

from .archive import ArchiveItem, LocalArchive
from .catalog import (
    generate_album_gallery,
    generate_html_catalog,
    generate_manifest,
    generate_readme,
    generate_uncategorized_gallery,
)
from .client import ImgurClient
from .metadata import apply_image_metadata, write_album_metadata
from .models import ImgurAlbum, ImgurImage

logger = logging.getLogger(__name__)

# Reserved names in Windows
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_filename(name: str, max_length: int = 180) -> str:
    """Sanitize string for cross-platform safe filenames (Windows, macOS, Linux)."""
    # Replace illegal filesystem characters: < > : " / \ | ? *
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Remove leading/trailing spaces and dots (problematic on Windows)
    cleaned = cleaned.strip(". ")
    stem = Path(cleaned).stem.upper()
    if not cleaned or stem in WINDOWS_RESERVED_NAMES or cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}" if cleaned else "unnamed"
    return cleaned[:max_length]


class ArchiveOrganizer:
    """Coordinates local archive extraction, metadata fetching, and organization into album directories."""

    def __init__(
        self,
        output_dir: str | Path,
        archive: Optional[LocalArchive] = None,
        client: Optional[ImgurClient] = None,
        console: Optional[Console] = None,
        embed_exif: bool = True,
        set_timestamps: bool = True,
        write_sidecars: bool = False,
        preserve_archive_filenames: bool = False,
        folder_template: str = "{title} [{id}]",
        ignore_albums: Optional[List[str]] = None,
        exclude_ignored_images: bool = True,
        enable_catch_all: bool = True,
        leave_out_non_album_images: bool = False,
        catch_all_title: str = "Non-Album Images",
        catch_all_folder: str = "Non-Album Images [_uncategorized]",
        dry_run: bool = False,
    ):
        self.output_dir = Path(output_dir).resolve()
        self.archive = archive
        self.client = client
        self.console = console or Console()
        self.embed_exif = embed_exif
        self.set_timestamps = set_timestamps
        self.write_sidecars = write_sidecars
        self.preserve_archive_filenames = preserve_archive_filenames
        self.folder_template = folder_template
        self.ignore_albums = [s.strip() for s in (ignore_albums or []) if s.strip()]
        self.exclude_ignored_images = exclude_ignored_images
        self.leave_out_non_album_images = leave_out_non_album_images
        self.enable_catch_all = enable_catch_all and not leave_out_non_album_images
        self.catch_all_title = catch_all_title
        self.catch_all_folder = catch_all_folder
        self.dry_run = dry_run

    def is_album_ignored(self, album: ImgurAlbum) -> bool:
        """Check if an album matches any configured ignore patterns (ID, title, display title, or folder)."""
        if not self.ignore_albums:
            return False
        a_id = album.id.lower()
        a_title = (album.title or "").strip().lower()
        a_display_title = (album.display_title or "").strip().lower()
        bracket_id = f"[{a_id}]"

        for pat in self.ignore_albums:
            p = pat.lower()
            if p in (a_id, a_title, a_display_title, bracket_id):
                return True
            if (
                fnmatch.fnmatch(a_id, p)
                or (a_title and fnmatch.fnmatch(a_title, p))
                or fnmatch.fnmatch(a_display_title, p)
                or fnmatch.fnmatch(bracket_id, p)
            ):
                return True
        return False

    def format_album_dirname(self, album: ImgurAlbum) -> str:
        """Format and sanitize the folder name for an album."""
        title = (album.title or "").strip()
        if not title:
            return f"[{album.id}]"

        try:
            raw_name = self.folder_template.format(
                title=title,
                id=album.id,
                date=album.datetime_iso[:10] if album.datetime_iso else "",
            )
        except Exception:
            raw_name = f"{title} [{album.id}]"

        return sanitize_filename(raw_name)

    def format_image_filename(
        self,
        image: ImgurImage,
        order: int,
        archive_item: Optional[ArchiveItem],
    ) -> str:
        """Format safe filename for an image within an album."""
        if self.preserve_archive_filenames and archive_item:
            return sanitize_filename(os.path.basename(archive_item.filename))

        # Determine extension
        ext = "jpg"
        if archive_item:
            ext = archive_item.extension
        elif image.type:
            ext = image.type.split("/")[-1].replace("jpeg", "jpg")
        elif image.link:
            ext = image.link.split(".")[-1].split("?")[0].lower()

        # If extension is mp4 or gifv
        if image.mp4 and ext in ("gif", "gifv"):
            ext = "mp4"

        title_suffix = ""
        if image.title:
            cleaned_title = sanitize_filename(image.title, max_length=60)
            if cleaned_title:
                title_suffix = f" - {cleaned_title}"

        raw_filename = f"{order:03d} - {image.id}{title_suffix}.{ext}"
        return sanitize_filename(raw_filename)

    def organize(
        self,
        albums: List[ImgurAlbum],
        account_images: Optional[List[ImgurImage]] = None,
    ) -> Dict[str, Any]:
        """Execute the full organization workflow."""
        if not self.dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.console.print(
            f"[bold green]Starting organization into:[/bold green] [cyan]{self.output_dir}[/cyan]"
        )
        if self.dry_run:
            self.console.print("[bold yellow]*** DRY-RUN MODE: No files will be modified ***[/bold yellow]")

        # 1. Filter out ignored albums for curated output
        active_albums: List[ImgurAlbum] = []
        ignored_image_ids: Set[str] = set()
        ignored_count = 0

        for album in albums:
            if self.is_album_ignored(album):
                ignored_count += 1
                if self.exclude_ignored_images:
                    for img in album.images:
                        ignored_image_ids.add(img.id)
                continue
            active_albums.append(album)

        if ignored_count > 0:
            self.console.print(
                f"[bold yellow]Curated Output:[/bold yellow] Skipping [dim]{ignored_count}[/dim] ignored album(s)."
            )

        album_dir_map: Dict[str, str] = {}
        processed_image_ids: Set[str] = set()

        stats = {
            "albums_processed": 0,
            "albums_ignored": ignored_count,
            "images_extracted_from_archive": 0,
            "images_downloaded": 0,
            "catch_all_images": 0,
            "uncategorized_images": 0,
            "non_album_images_omitted": 0,
            "errors": 0,
        }

        # Progress reporting
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=self.console,
        ) as progress:

            album_task = progress.add_task("[cyan]Processing albums...", total=len(active_albums))

            for album in active_albums:
                folder_name = self.format_album_dirname(album)
                album_dir = self.output_dir / folder_name
                album_dir_map[album.id] = folder_name

                if not self.dry_run:
                    album_dir.mkdir(parents=True, exist_ok=True)

                img_task = progress.add_task(
                    f"  [dim]{folder_name[:30]}[/dim]",
                    total=len(album.images),
                )

                album_image_files: List[Tuple[ImgurImage, str]] = []

                for idx, img in enumerate(album.images, start=1):
                    processed_image_ids.add(img.id)
                    archive_item = self.archive.get_item(img.id) if self.archive else None
                    filename = self.format_image_filename(img, idx, archive_item)
                    dest_file = album_dir / filename
                    album_image_files.append((img, filename))

                    if not self.dry_run:
                        # 1. Obtain image data (from local archive or download)
                        if archive_item and self.archive:
                            try:
                                self.archive.extract_file(img.id, dest_file)
                                stats["images_extracted_from_archive"] += 1
                            except Exception as e:
                                logger.error("Failed extracting %s from archive: %s", img.id, e)
                                stats["errors"] += 1
                        elif self.client and img.link:
                            try:
                                self.client.download_image(img.link, dest_file)
                                stats["images_downloaded"] += 1
                            except Exception as e:
                                logger.error("Failed downloading %s: %s", img.id, e)
                                stats["errors"] += 1

                        # 2. Preserve metadata
                        if dest_file.exists():
                            apply_image_metadata(
                                dest_file,
                                img,
                                embed_exif=self.embed_exif,
                                set_timestamps=self.set_timestamps,
                                write_sidecar=self.write_sidecars,
                            )

                    progress.advance(img_task)

                progress.remove_task(img_task)

                # Write album metadata JSON, README, and full interactive HTML gallery
                if not self.dry_run:
                    write_album_metadata(
                        album_dir,
                        album,
                        set_timestamps=self.set_timestamps,
                    )
                    generate_album_gallery(
                        album_dir,
                        album,
                        album_image_files,
                    )

                stats["albums_processed"] += 1
                progress.advance(album_task)

            # -------------------------------------------------------------
            # Catch-All Album: Images in archive not belonging to any album
            # -------------------------------------------------------------
            archive_ids = self.archive.all_ids() if self.archive else set()
            candidate_ids = archive_ids - processed_image_ids
            if self.exclude_ignored_images:
                candidate_ids = candidate_ids - ignored_image_ids

            uncat_ids = sorted(candidate_ids)
            catch_all_album: Optional[ImgurAlbum] = None

            if self.leave_out_non_album_images or not self.enable_catch_all:
                stats["non_album_images_omitted"] = len(uncat_ids)
                if uncat_ids:
                    self.console.print(
                        f"[dim]Leaving out {len(uncat_ids)} non-album image(s) as configured.[/dim]"
                    )
            elif uncat_ids:
                catch_all_folder_name = sanitize_filename(self.catch_all_folder)
                catch_all_dir = self.output_dir / catch_all_folder_name
                album_dir_map["_uncategorized"] = catch_all_folder_name

                if not self.dry_run:
                    catch_all_dir.mkdir(parents=True, exist_ok=True)

                catch_all_task = progress.add_task(
                    f"[yellow]Organizing {self.catch_all_title}...",
                    total=len(uncat_ids),
                )

                catch_all_images: List[ImgurImage] = []
                catch_all_image_files: List[Tuple[ImgurImage, str]] = []

                for idx, img_id in enumerate(uncat_ids, start=1):
                    archive_item = self.archive.get_item(img_id)
                    raw_filename = (
                        os.path.basename(archive_item.filename)
                        if archive_item
                        else f"{img_id}.jpg"
                    )
                    safe_filename = sanitize_filename(raw_filename)
                    dest_file = catch_all_dir / safe_filename

                    uncat_img = ImgurImage(
                        id=img_id,
                        order=idx,
                        original_archive_name=archive_item.filename if archive_item else None,
                        original_archive_index=archive_item.index if archive_item else None,
                        link=f"https://i.imgur.com/{img_id}.{archive_item.extension if archive_item else 'jpg'}",
                    )
                    catch_all_images.append(uncat_img)
                    catch_all_image_files.append((uncat_img, safe_filename))

                    if not self.dry_run:
                        if archive_item and self.archive:
                            try:
                                self.archive.extract_file(img_id, dest_file)
                                stats["images_extracted_from_archive"] += 1
                            except Exception as e:
                                logger.error("Failed extracting catch-all %s: %s", img_id, e)
                                stats["errors"] += 1

                        if dest_file.exists():
                            apply_image_metadata(
                                dest_file,
                                uncat_img,
                                embed_exif=self.embed_exif,
                                set_timestamps=self.set_timestamps,
                                write_sidecar=self.write_sidecars,
                            )

                    stats["catch_all_images"] += 1
                    stats["uncategorized_images"] += 1
                    progress.advance(catch_all_task)

                catch_all_album = ImgurAlbum(
                    id="_uncategorized",
                    title=self.catch_all_title,
                    description=f"Catch-all album containing {len(catch_all_images)} media items without an album association.",
                    cover=catch_all_images[0].id if catch_all_images else None,
                    images_count=len(catch_all_images),
                    images=catch_all_images,
                )

                if not self.dry_run:
                    write_album_metadata(
                        catch_all_dir,
                        catch_all_album,
                        set_timestamps=self.set_timestamps,
                    )
                    generate_album_gallery(
                        catch_all_dir,
                        catch_all_album,
                        catch_all_image_files,
                    )

        # Generate root catalogs (including the catch-all album in the main index)
        all_output_albums = list(active_albums)
        if catch_all_album:
            all_output_albums.append(catch_all_album)

        if not self.dry_run:
            generate_manifest(
                self.output_dir,
                all_output_albums,
                [],
                archive_source=str(self.archive.path) if self.archive else None,
            )
            generate_readme(
                self.output_dir,
                all_output_albums,
                [],
                archive_source=str(self.archive.path) if self.archive else None,
                album_dir_map=album_dir_map,
            )
            generate_html_catalog(
                self.output_dir,
                all_output_albums,
                [],
                album_dir_map,
            )

        return stats
