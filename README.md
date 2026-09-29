# Imgur Account Downloader & Album Organizer

A Python CLI tool designed to retrieve and organize **all images** from an Imgur account into their original **album folders** with **maximal metadata preservation**.

If you have already downloaded your account backup using Imgur's *"Download account images"* feature (e.g. a multi-gigabyte `.zip` containing files like `1 - TzIN9Qm.png`), this tool automatically reads the local archive to organize everything into folders without having to re-download gigabytes of data over the network!

---

## Highlights & Features

- 📁 **Organizes by Original Albums**: Creates a dedicated folder for each album (e.g. `Vacation [aBcDe]`) and places all corresponding images inside in album order.
- 📦 **Zero-Re-download Local Extraction**: Auto-detects and indexes your existing Imgur account `.zip` dump (or folder). Images are streamed directly from the zip to their destination folders.
- 🕒 **True File Timestamp Preservation**: Sets filesystem Modification Time (`mtime`), Access Time (`atime`), and Windows Creation Time (`ctime`) to the exact Imgur upload date. Your photos will sort chronologically in Windows Explorer, Apple Photos, and Google Photos.
- 🏷️ **Lossless EXIF Metadata Embedding**: Injects Title, Description, Upload Date (`DateTimeOriginal`), Imgur URL, View counts, and Windows Explorer tags (`XPTitle`, `XPComment`) directly into JPEGs without recompressing or losing quality.
- 📄 **Complete Sidecar & Manifest Documentation**:
  - `album_metadata.json` & `README.md` inside every album directory.
  - Root `manifest.json` cataloging all albums and images.
  - Interactive, offline-ready `catalog.html` gallery for browsing your archive visually.
- 🔍 **Uncategorized Image Preservation**: Any images not belonging to an album are placed in an `_Uncategorized/` folder with their original index and filename intact. No image is ever skipped or lost.
- 🛡️ **Rate-Limit & Error Resilient**: Built-in exponential backoff, rate limit header tracking, and local JSON metadata caching.

---

## Installation

```bash
git clone https://github.com/coreyx/imgur-account-downloader.git
cd imgur-account-downloader
pip install -e .
```

Dependencies (`requests`, `click`, `rich`, `pillow`, `piexif`) are installed automatically.

---

## Quickstart

### 1. Inspect Your Local Zip Archive
Verify that the tool recognizes your Imgur account dump:

```bash
python -m imgur_downloader inspect-archive
```

This auto-detects `*Imgur*.zip` in the current directory and outputs file counts, formats, and sample IDs.

### 2. How to Authenticate

To retrieve your album list and metadata, you can provide an authentication token from your browser session in 10 seconds:

1. Open [imgur.com](https://imgur.com) in Chrome, Edge, or Firefox (logged into your account).
2. Press `F12` to open Developer Tools and select the **Application** tab (or **Storage** tab in Firefox).
3. In the left sidebar, click **Cookies** -> `https://imgur.com`.
4. Copy the value of the `accesstoken` cookie.

### 3. Configure via `config.yml` (Recommended)

Copy `config.example.yml` to `config.yml` and configure your credentials and archive path:

```yaml
token: "YOUR_ACCESS_TOKEN_HERE"

# Path to your Imgur zip backup file (or leave empty to auto-detect):
local_archive: "imgur_account_backup.zip"
```

> **Security Note:** `config.yml` is automatically ignored in `.gitignore` so your secret token will never be committed to git.

Then run:

```bash
python -m imgur_downloader
```

### Alternatively: Pass via CLI or Environment Variable

```bash
python -m imgur_downloader --token YOUR_ACCESS_TOKEN
```

*(You can also set `IMGUR_ACCESS_TOKEN=YOUR_ACCESS_TOKEN`)*

If you don't pass a token, the CLI will prompt you interactively:

```bash
python -m imgur_downloader
```

### Dry Run (Preview without writing)
To test and see which albums and images will be organized without touching any files:

```bash
python -m imgur_downloader --token YOUR_TOKEN --dry-run
```

---

## Alternative: Using an Album List

If you do not want to use an access token or have specific public/hidden album links:

Create a file named `albums.txt` containing your album URLs or hashes (one per line):
```text
https://imgur.com/a/abc1234
https://imgur.com/a/xyz9876
5H0E6cH
```

Then run:
```bash
python -m imgur_downloader --albums-file albums.txt
```

---

## Output Structure

The tool creates a structured directory tree:

```text
imgur_archive/
├── catalog.html               <-- Responsive offline visual photo catalog
├── README.md                  <-- Summary table of all albums and counts
├── manifest.json              <-- Complete machine-readable archive manifest
│
├── Summer Vacation [abc123]/
│   ├── gallery.html           <-- Full-featured offline photo gallery with Lightbox
│   ├── album_metadata.json    <-- Full album and image metadata from Imgur
│   ├── README.md              <-- Human-readable album notes and image list
│   ├── 001 - TziN9Qm - Beach.jpg
│   ├── 002 - BHY6CTE - Sunset.png
│   └── 003 - wXPiGCU.gif
│
├── Project Design [def456]/
│   ├── gallery.html
│   ├── album_metadata.json
│   ├── README.md
│   └── 001 - jgsZeGT.jpg
│
└── Non-Album Images [_uncategorized]/  <-- Dedicated catch-all album for media without an album
    ├── gallery.html                   <-- Full-featured gallery & lightbox
    ├── album_metadata.json            <-- Catch-all collection metadata
    ├── README.md                      <-- Image index & collection notes
    ├── 15 - iIvS8sg.jpg
    └── 19 - rkJAxKs.jpg
```

---

## Configuring Your Local Archive (ZIP Dump)

Every user's Imgur export `.zip` has a unique filename and path (for example, `imgur_account_backup.zip`). You can configure the archive path in multiple flexible ways:

1. **In `config.yml`:**
   ```yaml
   # Windows absolute path:
   local_archive: "C:/Users/username/Downloads/imgur_account_backup.zip"

   # Home shortcut:
   local_archive: "~/Downloads/imgur_account_backup.zip"

   # Relative path or filename in project folder:
   local_archive: "my_imgur_export.zip"

   # Extracted folder:
   local_archive: "C:/Users/username/Downloads/extracted_backup"
   ```

2. **Via Command Line (`--local-archive`, `-a`, or `--archive`):**
   ```bash
   python -m imgur_downloader -a "~/Downloads/my_backup.zip"
   python -m imgur_downloader --archive "D:/Backups/imgur_dump.zip"
   ```

3. **Via Environment Variable:**
   ```bash
   # Linux / macOS:
   export IMGUR_LOCAL_ARCHIVE="~/Downloads/my_backup.zip"

   # Windows PowerShell:
   $env:IMGUR_LOCAL_ARCHIVE = "C:\Users\username\Downloads\my_backup.zip"
   ```

4. **Zero-Configuration Auto-Detection:**
   If you leave `local_archive` empty or omit the CLI flag, the tool automatically scans your current directory, followed by your system `~/Downloads` folder, locating any Imgur backup archive automatically.

---

## Curated Output & Filtering

You can curate your export by skipping specific albums by title, album ID, or glob patterns (via `config.yml` or CLI):

```bash
# Skip specific albums by title or wildcard pattern
python -m imgur_downloader --ignore-album "Memes" --ignore-album "Screenshots*"

# Or provide a text file with ignored albums
python -m imgur_downloader --ignore-albums-file ignored.txt
```

By default, images belonging to ignored albums are completely excluded from both album folders and the catch-all album (`--exclude-ignored-images`). If you want their images to fall into the catch-all album instead, pass `--include-ignored-images`.

### Leaving Out Non-Album Images

If you only want organized album folders and wish to omit uncategorized standalone images entirely:
- In `config.yml`: set `leave_out_non_album_images: true`
- Or via CLI: `python -m imgur_downloader --leave-out-non-album-images`

When enabled, no catch-all folder is created, zero non-album images are extracted or downloaded, and only true albums appear in `catalog.html`.

---

## CLI Options Reference

| Option | Shorthand / Alias | Description | Default |
| :--- | :---: | :--- | :--- |
| `--config` | | Path to YAML config file. | `config.yml` |
| `--local-archive` | `-a`, `--archive` | Path to local `.zip` file or directory (`IMGUR_LOCAL_ARCHIVE`). | Auto-detects in `.` or `~/Downloads` |
| `--output-dir` | `-o` | Destination directory for organized folders. | `./imgur_archive` |
| `--token` | `-t` | Imgur access token or Bearer token (`IMGUR_ACCESS_TOKEN`). | None |
| `--cookie` | `-c` | Imgur cookie string or value (`IMGUR_COOKIE`). | None |
| `--cookies-file` | | Path to `cookies.txt` in Netscape format. | None |
| `--albums-file` | | Text file with album URLs/IDs (one per line). | None |
| `--album` | | Single album ID/URL (can be repeated). | None |
| `--ignore-album` | | Album ID, title, or wildcard to skip (can be repeated). | None |
| `--ignore-albums-file` | | Text file with album IDs/titles to ignore (one per line). | None |
| `--exclude-ignored-images` / `--include-ignored-images` | | Exclude images of ignored albums from catch-all. | `True` |
| `--enable-catch-all` / `--no-catch-all` | | Create catch-all album for media not in any album. | `True` |
| `--leave-out-non-album-images` / `--include-non-album-images` | | Omit non-album images entirely (no catch-all folder). | `False` |
| `--catch-all-title` | | Display title for catch-all album. | `'Non-Album Images'` |
| `--catch-all-folder` | | Output folder name for catch-all album. | `'Non-Album Images [_uncategorized]'` |
| `--dry-run` | | Simulate organization without modifying disk. | False |
| `--cache-file` | | Path to cache metadata JSON. | `imgur_metadata_cache.json` |
| `--no-cache` | | Bypass existing cache and re-fetch from Imgur. | False |
| `--embed-exif` / `--no-embed-exif` | | Lossless EXIF embedding for JPEGs. | `True` |
| `--set-timestamps` / `--no-timestamps` | | Set filesystem mtime/ctime to upload date. | `True` |
| `--sidecar-json` | | Generate individual `.json` sidecar for every image. | `False` |
| `--preserve-filenames` | | Keep original archive filename (`1 - TzIN9Qm.png`). | `False` |
| `--folder-template` | | Naming template for album directories. | `{title} [{id}]` |

---

## Metadata Preservation Details

1. **Filesystem Timestamps**:
   - Both `mtime` (modified time) and `atime` (accessed time) are set to the exact Unix timestamp of when the image was uploaded to Imgur.
   - On Windows, `ctime` (creation time) is also synchronized via the Windows Win32 API (`SetFileTime`).
2. **Lossless EXIF Injection**:
   - Operates directly on the JPEG header markers using `piexif.insert()` without decoding and re-compressing the image, preserving pixel integrity 100%.
   - Sets standard EXIF tags: `DateTimeOriginal`, `DateTimeDigitized`, `ImageDescription`, `UserComment`, and `Software`.
   - Populates Windows Explorer extended tags: `XPTitle`, `XPComment`, `XPKeywords`.
3. **JSON & Manifest Sidecars**:
   - Captures album titles, descriptions, privacy settings, view counts, bandwidth stats, cover image IDs, image order, tags, and deletion hashes if available.

---

## Running Tests

Run the test suite using standard Python:

```bash
python -m unittest discover tests
```

---

## License

MIT License.
