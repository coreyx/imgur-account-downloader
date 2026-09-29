"""Local archive loader for Imgur account image dumps (zip files or directories)."""

from __future__ import annotations

import glob
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


# Regex pattern to match filenames from Imgur account dump:
# e.g.: "1 - TzIN9Qm.png", "2, - BHY6CTE.png", "2189 - wXPiGCU.gif", "TzIN9Qm.jpg"
FILENAME_PATTERN = re.compile(
    r"^(?:(?P<index>\d+)[\s,-]*)?\s*(?:-\s*)?(?P<id>[a-zA-Z0-9]{4,16})\.(?P<ext>[a-zA-Z0-9]+)$",
    re.IGNORECASE,
)


@dataclass
class ArchiveItem:
    """Represents an image item within the local zip or directory archive."""

    id: str
    filename: str
    extension: str
    index: Optional[int] = None
    size: Optional[int] = None
    is_zip_member: bool = True


class LocalArchive:
    """Provides fast access to images stored in a zip archive or folder."""

    def __init__(self, archive_path: str | Path):
        self.path = Path(archive_path).expanduser().resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"Archive path not found: {self.path}")

        self.is_zip = self.path.is_file() and zipfile.is_zipfile(self.path)
        self.is_dir = self.path.is_dir()

        if not self.is_zip and not self.is_dir:
            raise ValueError(
                f"Path is neither a valid zip file nor a directory: {self.path}"
            )

        self._items_by_id: Dict[str, ArchiveItem] = {}
        self._zip_ref: Optional[zipfile.ZipFile] = None
        self._index_archive()

    def _index_archive(self) -> None:
        """Scan and index all files in the archive by their Imgur ID."""
        if self.is_zip:
            self._zip_ref = zipfile.ZipFile(self.path, "r")
            for info in self._zip_ref.infolist():
                if info.is_dir():
                    continue
                basename = os.path.basename(info.filename)
                m = FILENAME_PATTERN.match(basename)
                if m:
                    img_id = m.group("id")
                    idx = int(m.group("index")) if m.group("index") else None
                    ext = m.group("ext").lower()
                    self._items_by_id[img_id] = ArchiveItem(
                        id=img_id,
                        filename=info.filename,
                        extension=ext,
                        index=idx,
                        size=info.file_size,
                        is_zip_member=True,
                    )
        else:
            for entry in os.scandir(self.path):
                if entry.is_file():
                    m = FILENAME_PATTERN.match(entry.name)
                    if m:
                        img_id = m.group("id")
                        idx = int(m.group("index")) if m.group("index") else None
                        ext = m.group("ext").lower()
                        self._items_by_id[img_id] = ArchiveItem(
                            id=img_id,
                            filename=entry.path,
                            extension=ext,
                            index=idx,
                            size=entry.stat().st_size,
                            is_zip_member=False,
                        )

    def close(self) -> None:
        """Close any open zip file handles."""
        if self._zip_ref is not None:
            self._zip_ref.close()
            self._zip_ref = None

    def __enter__(self) -> LocalArchive:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __len__(self) -> int:
        return len(self._items_by_id)

    def contains(self, image_id: str) -> bool:
        """Check if an image ID exists in the local archive."""
        return image_id in self._items_by_id

    def get_item(self, image_id: str) -> Optional[ArchiveItem]:
        """Retrieve archive metadata for an image ID."""
        return self._items_by_id.get(image_id)

    def all_ids(self) -> Set[str]:
        """Return the set of all unique Imgur IDs found in the archive."""
        return set(self._items_by_id.keys())

    def all_items(self) -> List[ArchiveItem]:
        """Return all indexed archive items."""
        return list(self._items_by_id.values())

    def read_bytes(self, image_id: str) -> bytes:
        """Read the raw image bytes for a given image ID."""
        item = self._items_by_id.get(image_id)
        if not item:
            raise KeyError(f"Image ID '{image_id}' not found in archive.")

        if self.is_zip:
            if self._zip_ref is None:
                self._zip_ref = zipfile.ZipFile(self.path, "r")
            return self._zip_ref.read(item.filename)
        else:
            with open(item.filename, "rb") as f:
                return f.read()

    def extract_file(
        self,
        image_id: str,
        dest_path: str | Path,
        buffer_size: int = 1024 * 1024,
    ) -> Path:
        """Extract or copy the file directly to dest_path without loading entire file in memory."""
        item = self._items_by_id.get(image_id)
        if not item:
            raise KeyError(f"Image ID '{image_id}' not found in archive.")

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if self.is_zip:
            if self._zip_ref is None:
                self._zip_ref = zipfile.ZipFile(self.path, "r")
            with self._zip_ref.open(item.filename) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst, length=buffer_size)
        else:
            shutil.copyfile(item.filename, dest)

        return dest


def find_local_archive(
    search_dirs: Optional[str | Path | Iterable[str | Path]] = None,
) -> Optional[Path]:
    """Auto-detect a local Imgur archive zip file or folder in candidate directories.

    If search_dirs is omitted, checks the current working directory, followed by
    the user's system Downloads folder (~/Downloads).
    """
    if search_dirs is None:
        dirs_to_check: List[Path] = [Path(".").resolve()]
        downloads = Path.home() / "Downloads"
        if downloads.exists() and downloads.resolve() != dirs_to_check[0]:
            dirs_to_check.append(downloads.resolve())
    elif isinstance(search_dirs, (str, Path)):
        dirs_to_check = [Path(search_dirs).expanduser().resolve()]
    else:
        dirs_to_check = [Path(d).expanduser().resolve() for d in search_dirs]

    for s_path in dirs_to_check:
        if not s_path.exists():
            continue

        # 1. Check for zip files with imgur or account in name
        candidates = list(s_path.glob("*[Ii]mgur*.zip")) + list(
            s_path.glob("*[Aa]ccount*.zip")
        )
        for c in candidates:
            if c.is_file() and zipfile.is_zipfile(c):
                return c

        # 2. Check all other zips in s_path by inspecting internal member filenames
        for z in s_path.glob("*.zip"):
            try:
                with zipfile.ZipFile(z, "r") as zf:
                    names = zf.namelist()[:10]
                    if any(FILENAME_PATTERN.match(os.path.basename(n)) for n in names):
                        return z
            except Exception:
                continue

        # 3. Check for extracted folders matching naming pattern with dump images
        dir_candidates = list(s_path.glob("*[Ii]mgur*")) + list(
            s_path.glob("*[Aa]ccount*")
        )
        for d in dir_candidates:
            if d.is_dir() and d != s_path:
                try:
                    entries = [e.name for e in os.scandir(d) if e.is_file()][:10]
                    if any(FILENAME_PATTERN.match(name) for name in entries):
                        return d
                except Exception:
                    continue

    return None
