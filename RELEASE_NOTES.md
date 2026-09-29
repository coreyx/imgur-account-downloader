# Release Notes - Imgur Account Downloader

## Release 1.1.0 (September 28, 2026)

**Status:** General Availability  

### Highlights

1. **First-Class Catch-All Album for Non-Album Media**:
   - Media in your account or local archive not assigned to an album is now organized into a dedicated, first-class album (`Non-Album Images [_uncategorized]`).
   - Generates complete sidecars: `album_metadata.json`, `README.md`, and a full interactive `gallery.html` with lightbox modal and filter bar.
   - Fully integrated into root `catalog.html`, `README.md`, and `manifest.json` with dedicated badge indicators.
   - Configurable collection title (`--catch-all-title` / `catch_all_title`) and folder name (`--catch-all-folder` / `catch_all_folder`).

2. **Curated Output & Album Filtering (`ignore_albums`)**:
   - Skip unwanted albums by exact album ID, exact title, or wildcard glob patterns (e.g. `"Memes"`, `"Screenshots*"`).
   - Pattern matching is case-insensitive and operates against both album IDs and titles.
   - Configurable in `config.yml` (`ignore_albums: [...]`) or via CLI (`--ignore-album <pat>`, `--ignore-albums-file <path>`).
   - Image exclusion policy: `--exclude-ignored-images` (default) completely excludes ignored album images, while `--include-ignored-images` allows them to fall into the catch-all album.

3. **Configurable Archive Path & Smart Auto-Discovery**:
   - Every user receives a unique archive zip name and location upon exporting their data from Imgur.
   - Archive path is now fully configurable via `config.yml` (`local_archive: "path/to/archive.zip"`), CLI flags (`--local-archive`, `-a`, `--archive`), or environment variable (`IMGUR_LOCAL_ARCHIVE`).
   - Supports Windows and POSIX absolute paths, tilde (`~`) home shortcuts, and relative paths.
   - Smart auto-detection searches both the working directory and the user's system `~/Downloads` folder.
   - `inspect-archive` now loads the archive from `config.yml` automatically if no argument is passed.

4. **Configurable Non-Album Media Omission (`leave_out_non_album_images`)**:
   - For users who prefer strictly organized album directories without preserving standalone uncategorized images.
   - Configure via `leave_out_non_album_images: true` in `config.yml` or CLI flag `--leave-out-non-album-images` (default: `false` / `--include-non-album-images`).
   - Suppresses creation of the catch-all folder, extracts and downloads zero standalone images, excludes them from root catalogs, and surfaces the omitted count in the execution summary table.

5. **Polished Catalog & Gallery UX**:
   - In per-album `gallery.html`, clicking directly on any image or thumbnail now opens the fullscreen lightbox modal, identical to clicking the "View" button.
   - Enhanced thumbnail accessibility with `role="button"`, `tabindex="0"`, `:focus-visible` styling, and keyboard navigation (Enter/Space).
   - Root `catalog.html` stat badges now distinguish standard albums from non-album media.
   - Gallery top navigation and header dynamically omit external Imgur album links for local catch-all collections.
   - 23 unit tests passing across all components (`python -m unittest discover tests`).

---

## Release 1.0.0 (September 28, 2026)

**Release Date:** September 28, 2026  
**Status:** General Availability  

---

## Executive Summary

**Imgur Account Downloader & Organizer v1.0.0** solves a major problem for Imgur users backing up their media: Imgur's native "Download account images" export produces a flat `.zip` file containing thousands of numbered files with no folder hierarchy, no album association, and stripped filesystem dates.

This tool reorganizes flat backup dumps into their original Imgur album folder structures while embedding and preserving maximal metadata across filesystem dates, image EXIF headers, JSON sidecars, and an offline interactive visual gallery.

---

## Key Highlights

### 1. High-Capacity Local Archive Support (Zero Re-Download)
Instead of forcing users to redownload gigabytes of images across the Imgur API—running into daily IP and client rate limits—this release introduces a high-speed local archive indexer. It parses your local `.zip` backup directly (e.g. `imgur_account_backup.zip`), maps all images to their Imgur IDs in milliseconds, and streams them into their designated album folders.

### 2. Maximal Metadata Preservation Engine
- **Filesystem Timestamps (`os.utime` + Win32 `SetFileTime`)**: Synchronizes `mtime`, `atime`, and Windows `ctime` to the exact Imgur upload timestamp. Windows Explorer, Apple Photos, and Google Photos will sort your photos in chronological order rather than the date you downloaded the `.zip`.
- **Lossless EXIF Injection (`piexif`)**: For JPEG photos, the tool inserts standard EXIF tags (`DateTimeOriginal`, `ImageDescription`, `UserComment`, `Software`) and Windows Explorer extended tags (`XPTitle`, `XPComment`, `XPKeywords`) directly into the file header. This is done losslessly without re-encoding image pixels.
- **Album & Image JSON Sidecars**: Every album directory receives an `album_metadata.json` containing the full API response (privacy, layout, views, cover image ID, descriptions, and image sequence).
- **Human-Readable Album Notes**: Generates a clean `README.md` in each album directory summarizing its contents, Imgur URL, and image list.

### 3. Complete Image Safety Guarantee
Images in your backup that do not belong to an album are extracted to an `_Uncategorized/` directory with their original index and filename preserved. **No image is left behind or skipped.**

### 4. Full-Featured Per-Album Galleries & Visual Catalog
- **Dedicated Album Galleries (`<album>/gallery.html`)**: Every album folder includes its own offline HTML gallery with full-resolution photo inspection, sequential indices, and video player support.
- **Native `<dialog>` Lightbox**: Fullscreen modal with left/right keyboard arrow navigation, light dismiss, and metadata drawer (dimensions, file size, upload dates, views, and direct links).
- **Streamlined Navigation**: In the root `catalog.html`, "Gallery" is the primary button and default hover/click navigation target, while "Open Folder" retains instant access to the local filesystem index. An Uncategorized Gallery is also generated for non-album media.

### 5. Multi-Mode Authentication
- YAML configuration file support (`config.yml` / `config.example.yml`), automatically `.gitignore`d for security.
- Browser session cookie extraction via DevTools (`accesstoken`).
- Imgur OAuth Bearer token (`--token` or `IMGUR_ACCESS_TOKEN`).
- Netscape `cookies.txt` file support (`--cookies-file`).
- Manual album URL/ID lists (`--albums-file` or `--album`).
- Metadata caching (`imgur_metadata_cache.json`) to prevent redundant API queries.

---

## Performance & Test Verification

- **Archive Scan Benchmark**: Indexes thousands of archive files in **< 150 milliseconds**.
- **Test Suite**: 15 automated tests covering archive parsing, regex patterns, lossless EXIF injection, Win32 timestamps, filename sanitization, YAML configuration loading, and full organization workflows (`python -m unittest discover tests` - **100% Passing**).

---

## Getting Started

```bash
# 1. Add your access token to config.yml (git-ignored)
#    (or copy from config.example.yml)

# 2. Inspect local archive
python -m imgur_downloader inspect-archive

# 3. Preview dry-run
python -m imgur_downloader --dry-run

# 4. Organize with maximal metadata
python -m imgur_downloader
```
