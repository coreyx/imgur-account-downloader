# Imgur Account Downloader & Organizer - Walkthrough & Project Wrap-Up

This document provides a walkthrough of the architecture, verification, and usage of the **Imgur Account Downloader & Album Organizer** CLI tool.

---

## 1. Problem Context

When downloading your data from Imgur using the *"Download account images"* option, Imgur provides a single `.zip` file containing thousands of files named in an arbitrary numbered format:

```text
1 - TzIN9Qm.png
2, - BHY6CTE.png
...
2189 - wXPiGCU.gif
...
2195 - xhOLpie.jpg
```

**Key Challenges:**
1. **No Album Folders**: All account images are dumped into a flat list with no association to the albums you created over years of using Imgur.
2. **Missing Metadata**: Album titles, descriptions, view counts, and original ordering are not included.
3. **Lost Timestamps**: File creation and modification dates default to the moment the `.zip` was extracted rather than when the photos were uploaded.
4. **Network Waste**: Re-downloading gigabytes of images from the API would quickly hit Imgur's hourly IP limits (500 requests/hr) and take hours or days.

---

## 2. Solution Architecture

The solution uses a hybrid approach: **fetch album metadata via the API** while **extracting image data directly from the local `.zip` file**.

```
                           +---------------------------------------+
                           | Local Archive (.zip or folder)        |
                           | Backup Images & Media                 |
                           +-------------------+-------------------+
                                               |
                                               v
+-----------------------+           +-------------------+
| Imgur API / Web       |           | LocalArchive      |
| Endpoints             |           | Indexer           |
+-----------+-----------+           +---------+---------+
            |                                 |
            v                                 v
+-------------------------------------------------------+
| ArchiveOrganizer                                      |
|  - Matches Imgur ID (e.g. TzIN9Qm) -> Archive Item    |
|  - Creates album folders: "<Album Title> [<id>]"      |
|  - Streams bytes from zip directly to album folder    |
|  - Routes active album images to "<Album Title> [<id>]"|
|  - Routes non-album media to "Non-Album Images [_uncategorized]"|
|  - Skips ignored albums via pattern matching (ignore_albums) |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
| MetadataEngine & Gallery Generator                    |
|  - Injects lossless EXIF into JPEGs (piexif)          |
|  - Sets Windows ctime & POSIX mtime/atime to upload ts|
|  - Writes album_metadata.json & album README.md       |
|  - Generates per-album gallery.html with Lightbox     |
|  - Generates catalog.html, README.md, & manifest.json |
+-------------------------------------------------------+
```

### Module Breakdown

| Module | Purpose |
| :--- | :--- |
| [`imgur_downloader.archive`](imgur_downloader/archive.py) | Scans and indexes the local zip file or extracted directory in milliseconds using regex pattern `^(?:(?P<index>\d+)[\s,-]*)?\s*(?:-\s*)?(?P<id>[a-zA-Z0-9]{4,16})\.(?P<ext>[a-zA-Z0-9]+)$`. |
| [`imgur_downloader.client`](imgur_downloader/client.py) | Communicates with Imgur REST API v3 and Web Post endpoints (`/post/v1/accounts/me/all_posts`). Handles OAuth Bearer tokens, cookies, rate limits, and pagination. |
| [`imgur_downloader.metadata`](imgur_downloader/metadata.py) | Embeds lossless EXIF tags (`DateTimeOriginal`, `ImageDescription`, `UserComment`, `XPTitle`, `XPComment`), synchronizes filesystem dates (`mtime`, `ctime`), and writes album sidecars. |
| [`imgur_downloader.organizer`](imgur_downloader/organizer.py) | Curates output by skipping ignored albums (`ignore_albums`), manages first-class catch-all album generation (`Non-Album Images [_uncategorized]`), supports omitting standalone media (`leave_out_non_album_images`), and handles cross-platform path sanitization. |
| [`imgur_downloader.catalog`](imgur_downloader/catalog.py) | Generates root `manifest.json`, markdown `README.md`, and an interactive, offline-ready `catalog.html` gallery, plus per-album `gallery.html` with lightbox modal. |
| [`imgur_downloader.cli`](imgur_downloader/cli.py) | Rich-based terminal UI providing commands (`organize`, `inspect-archive`, `fetch-metadata`) with progress bars, colorized tables, and YAML configuration loading. |

---

## 3. Verification & Testing

### 3.1 Local Archive Inspection
Running `python -m imgur_downloader inspect-archive` against the zip file:

```text
Inspecting archive: imgur_account_backup.zip

+------------------------------+
| Property           | Value   |
|--------------------+---------|
| Total Files        | 2,000+  |
| Unique Imgur IDs   | 2,000+  |
| Numbered Prefixes  | 2,000+  |
| Total Archive Size | Multi-GB|
|   Format .png      | Yes     |
|   Format .jpg      | Yes     |
|   Format .gif      | Yes     |
|   Format .mp4      | Yes     |
+------------------------------+
```
- **Result**: 100% of archive files were successfully mapped to their unique Imgur IDs with zero unparsed entries.

### 3.2 Automated Test Suite
Running `python -m unittest discover tests`:

```text
Ran 23 tests in 0.157s

OK
```

The test suite validates:
- Regex parsing across all naming variations (`1 - TzIN9Qm.png`, `2, - BHY6CTE.png`, etc.).
- Extraction and reading from zip archives and extracted directories.
- Multi-directory search and ~/Downloads auto-discovery for local ZIP archives.
- Setting Windows `ctime` and POSIX `mtime` file timestamps.
- Lossless JPEG EXIF tag embedding with `piexif`.
- Folder and filename sanitization against Windows reserved device names (`CON`, `PRN`, `AUX`, etc.).
- Secure YAML configuration loading (`config.yml`).
- Album filtering via exact ID, title, and wildcard pattern (`ignore_albums`).
- Curated exclusion policies (`exclude_ignored_images=True` vs `False`).
- Dedicated first-class catch-all album metadata, README, and gallery generation.
- Complete omission of non-album media when `leave_out_non_album_images=True`.

### 3.3 Live Dry-Run Test
Running a dry-run against public Imgur album `5H0E6cH`:

```text
Fetching 1 specified albums from Imgur...
  OK Thank God they serve beer in Chuck E. Cheese... (2 images)
Starting organization into: .../imgur_archive
*** DRY-RUN MODE: No files will be modified ***
  Processing albums...               1/1 [00:00]
  Organizing uncategorized images... [00:00]
```
- **Result**: Correctly recognized the album, mapped uncategorized media, and made zero disk modifications during the simulation.

---

## 4. How to Run the Tool

### Step 1: Obtain Your `accesstoken`
1. Open [imgur.com](https://imgur.com) in Chrome or Edge (logged into your account).
2. Press <kbd>F12</kbd> (DevTools) &rarr; switch to the **Application** tab (or **Storage** in Firefox).
3. Under **Cookies** in the left sidebar, click `https://imgur.com`.
4. Copy the value of the **`accesstoken`** cookie.

### Step 2: Configure `config.yml` (Git-Ignored)
Open `config.yml` in your editor and configure your token and archive path:

```yaml
token: "YOUR_COPIED_ACCESS_TOKEN"

# Configure your backup ZIP file path:
# Supports absolute paths, ~/Downloads/..., or relative filenames:
local_archive: "imgur_account_backup.zip"
```

*(Note: `config.yml` is automatically excluded in `.gitignore` to guarantee your credentials never get committed or pushed to GitHub!)*

### Step 3: Test with a Dry-Run
Run a simulated run without writing any files:

```powershell
python -m imgur_downloader --dry-run
```

### Step 4: Run Full Organization
Run the organization process:

```powershell
python -m imgur_downloader
```

### Step 5: View Your Results
Once complete, open the visual catalog in your browser:

```powershell
Start-Process imgur_archive/catalog.html
```

---

## 5. Output Directory Structure

The resulting directory structure:

```text
imgur_archive/
├── catalog.html                           <-- Interactive offline visual catalog (with links to galleries)
├── README.md                              <-- Summary index of all albums and dates
├── manifest.json                          <-- Complete archive JSON manifest
│
├── Summer Vacation [abc123]/
│   ├── gallery.html                       <-- Full-featured offline photo gallery with Lightbox
│   ├── album_metadata.json                <-- Full album and image metadata from Imgur
│   ├── README.md                          <-- Human-readable album documentation
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
└── Non-Album Images [_uncategorized]/     <-- First-class album for standalone images (omitted if leave_out_non_album_images: true)
    ├── gallery.html                       <-- Standalone media gallery with lightbox
    ├── album_metadata.json                <-- Sidecar metadata for non-album media
    ├── README.md                          <-- Album documentation
    ├── 15 - iIvS8sg.jpg
    └── 19 - rkJAxKs.jpg
```

When `leave_out_non_album_images: true` (or `--leave-out-non-album-images`), the `Non-Album Images [_uncategorized]/` folder is omitted entirely and only true album folders are created and cataloged. Otherwise, all media is preserved, organized, and enriched with maximal metadata.
