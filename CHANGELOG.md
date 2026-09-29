# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-09-28

### Added

- **First-Class Catch-All Album for Non-Album Media**:
  - Automatically identifies all images from the local archive not associated with any active album.
  - Treats the catch-all collection as a first-class album (`Non-Album Images [_uncategorized]`): extracts media, synchronizes creation/modification timestamps, embeds EXIF, and generates `album_metadata.json`, `README.md`, and an interactive `gallery.html` with lightbox.
  - Seamlessly integrates into root `catalog.html`, `README.md`, and `manifest.json` with dedicated badge indicators.
  - Configurable collection title (`--catch-all-title` / `catch_all_title`, default: `"Non-Album Images"`) and folder name (`--catch-all-folder` / `catch_all_folder`, default: `"Non-Album Images [_uncategorized]"`).
  - Can be toggled on/off via `--enable-catch-all` / `--no-catch-all` (or `enable_catch_all` in config).

- **Curated Output & Album Filtering (`ignore_albums`)**:
  - Filter out and skip albums during organization by exact album ID, exact title, or wildcard glob patterns (e.g. `"Memes"`, `"Screenshots*"`).
  - Case-insensitive pattern matching against both album IDs and titles via `fnmatch`.
  - Configurable via CLI (`--ignore-album <pattern>`), batch text file (`--ignore-albums-file <path>`), or YAML configuration (`ignore_albums: [...]` and `ignore_albums_file: <path>`).
  - Configurable image exclusion policy (`--exclude-ignored-images` / `--include-ignored-images` or `exclude_ignored_images: true/false`): completely excludes ignored album images from both album directories and the catch-all album (default), or allows skipped album images to fall into the catch-all collection instead.

- **Fully Configurable Archive Path & Smart Auto-Detection**:
  - Fully configurable `local_archive` in `config.yml` supporting absolute paths (Windows & POSIX), relative paths, tilde (`~`) home shortcuts, and custom filenames.
  - Added CLI flag aliases `--local-archive`, `-a`, and `--archive`, plus environment variable `IMGUR_LOCAL_ARCHIVE`.
  - Upgraded `find_local_archive()` auto-discovery to search both the current working directory and the user's system `~/Downloads` folder.
  - Enhanced `inspect-archive` command to load archive path directly from `config.yml` or auto-detect in Downloads when no path argument is provided.

- **Configurable Non-Album Media Omission (`leave_out_non_album_images`)**:
  - Added boolean option `leave_out_non_album_images` in `config.yml` (supports aliases `exclude_non_album_images`, `omit_non_album_images`, `skip_non_album_images`, and inverted `include_non_album_images`).
  - Added dual CLI flags `--leave-out-non-album-images` and `--include-non-album-images`.
  - When enabled, leaves out all images that are not associated with an album: suppresses catch-all directory creation, extracts/downloads 0 standalone images, excludes them from root `catalog.html`, `README.md`, and `manifest.json`, and reports `"Non-Album Images Omitted"` in the execution summary table.

- **Interactive Gallery Direct Image Click**:
  - Clicking an image or video thumbnail in per-album `gallery.html` now directly triggers the fullscreen lightbox modal, matching the action of the "View" button.
  - Added accessibility attributes (`role="button"`, `tabindex="0"`, `aria-label`), keyboard activation (Enter/Space), `:focus-visible` styling, and card body click delegation while preserving direct link functionality on "File" and "Imgur" buttons.

- **Expanded Automated Test Suite**:
  - Added unit tests for `is_album_ignored()` across IDs, exact titles, wildcard patterns, and case-insensitivity.
  - Added end-to-end integration tests for ignored album exclusion and fallback catch-all behavior.
  - Added test coverage for catch-all album metadata and gallery generation.
  - Added test coverage for `leave_out_non_album_images` in both `ArchiveOrganizer` and YAML config loading.
  - Added test assertions for direct thumbnail click handlers and lightbox activation in `gallery.html`.

---

## [1.0.0] - 2026-09-28

### Added

- **Local Archive Indexer (`imgur_downloader.archive`)**:
  - High-speed scanner and parser for local Imgur account backup `.zip` files and folders.
  - Regex-based identifier extraction supporting standard Imgur ID formats, numeric prefixes, and comma/hyphen variations (e.g. `1 - TzIN9Qm.png`, `2, - BHY6CTE.png`).
  - Zero-re-download extraction: streams image data directly from the archive into album destination folders without re-downloading gigabytes of data over the network.
  - Auto-discovery mechanism to detect Imgur backups in the working directory automatically.

- **Imgur API & Web Client (`imgur_downloader.client`)**:
  - Unified client supporting standard Imgur API v3 endpoints and internal web post endpoints (`/post/v1/accounts/me/all_posts`, `/post/v1/accounts/me/hidden_albums`).
  - Multi-tier authentication: OAuth Bearer tokens, browser `accesstoken` session cookies, Netscape `cookies.txt`, and Client-ID.
  - Proactive rate-limit tracking for `X-RateLimit-*` headers with automatic exponential backoff on HTTP 429 and 503 responses.
  - Fallback network image downloader with retry logic for any images not present in local backup files.

- **Album & Image Organizer (`imgur_downloader.organizer`)**:
  - Automatic directory creation per album using customizable folder templates (default: `{title} [{id}]`).
  - Cross-platform filename and path sanitization eliminating illegal filesystem characters (`< > : " / \ | ? *`) and Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`).
  - Ordering of album images by their natural album position or original archive dump names.
  - `_Uncategorized/` preservation directory guaranteeing that 100% of backup images are retained even if they do not belong to an album.

- **Maximal Metadata Preservation Engine (`imgur_downloader.metadata`)**:
  - Filesystem timestamp synchronization setting Modification Time (`mtime`) and Access Time (`atime`) to the image's original Imgur upload timestamp.
  - Windows API integration (`win32file.SetFileTime`) setting file Creation Time (`ctime`) to match upload dates on NTFS filesystems.
  - Lossless EXIF metadata injection for JPEGs using `piexif.insert`, embedding Title, Description, Upload Date (`DateTimeOriginal`), Imgur URL, View counts, and Windows Explorer tags (`XPTitle`, `XPComment`, `XPKeywords`) without re-compressing pixels.
  - Per-album `album_metadata.json` and human-readable `README.md` sidecar documentation.
  - Optional per-image `.json` sidecar export.

- **Offline Visual Catalog & Per-Album Galleries (`imgur_downloader.catalog`)**:
  - Full-featured, standalone HTML gallery generated inside every album folder (`<album_dir>/gallery.html`) and `_Uncategorized/gallery.html`.
  - Native `<dialog>` fullscreen Lightbox modal with keyboard shortcuts (ArrowLeft/ArrowRight navigation, Escape to close), light dismiss, and touch swipe.
  - Interactive photo metadata drawer displaying dimensions, formatted file size, upload timestamp, view counts, and direct links.
  - Client-side real-time filter bar within each album gallery.
  - Root `catalog.html` album card navigation: "Gallery" is now the primary button and default card navigation target on hover/click, while preserving the directory file index under "Open Folder".
  - Root `README.md` containing a tabular index of all albums with cover thumbnails, dates, and direct links.
  - Machine-readable root `manifest.json` cataloging all processed and uncategorized media.

- **Interactive Command-Line Interface (`imgur_downloader.cli`)**:
  - Rich-powered CLI with colored tables, status badges, and real-time progress bars.
  - Subcommands:
    - `organize` (default workflow with `--dry-run` support).
    - `inspect-archive` (inspection of local backup archives without network calls).
    - `fetch-metadata` (retrieval and JSON caching of account albums).
  - Built-in interactive guidance for retrieving browser session cookies in seconds.

- **Configuration File Support (`config.yml` & `config.example.yml`)**:
  - Secure configuration loading from `config.yml` (or custom `--config <path>`) with `.gitignore` protection to prevent accidental secret leaks.
  - Granular option control: `token`, `cookie`, `client_id`, `output_dir`, `albums`, `embed_exif`, `set_timestamps`, and `folder_template`.

- **Automated Test Suite (`tests/`)**:
  - Full unit test coverage across archive parsing, EXIF injection, timestamp application, filename sanitization, client auth, and end-to-end organization flows using Python's standard `unittest` framework.
