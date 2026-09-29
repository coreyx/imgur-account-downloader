"""Catalog generator: creates visual HTML gallery per album, root catalog, Markdown summary, and manifest.json."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import ImgurAlbum, ImgurImage


def format_size(bytes_val: Optional[int]) -> str:
    """Format bytes into human-readable size string."""
    if not bytes_val:
        return ""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.1f} MB"


def generate_manifest(
    output_dir: str | Path,
    albums: List[ImgurAlbum],
    uncategorized: List[ImgurImage],
    archive_source: Optional[str] = None,
) -> Path:
    """Generate root manifest.json detailing the complete organized archive."""
    out_path = Path(output_dir)
    manifest_file = out_path / "manifest.json"

    standard_albums = [a for a in albums if not a.id.startswith("_")]
    catch_all_albums = [a for a in albums if a.id.startswith("_")]
    total_album_images = sum(len(a.images) for a in standard_albums)
    total_catch_all_images = sum(len(a.images) for a in catch_all_albums) + len(uncategorized)
    total_unique_images = len(
        set(img.id for a in albums for img in a.images).union(
            set(img.id for img in uncategorized)
        )
    )

    data = {
        "generator": "Imgur Account Downloader",
        "archive_source": archive_source,
        "summary": {
            "total_albums": len(standard_albums),
            "total_album_images": total_album_images,
            "catch_all_images": total_catch_all_images,
            "uncategorized_images": len(uncategorized),
            "total_unique_images": total_unique_images,
        },
        "albums": [a.to_dict() for a in albums],
        "uncategorized": [img.to_dict() for img in uncategorized],
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return manifest_file


def generate_readme(
    output_dir: str | Path,
    albums: List[ImgurAlbum],
    uncategorized: List[ImgurImage],
    archive_source: Optional[str] = None,
    album_dir_map: Optional[Dict[str, str]] = None,
) -> Path:
    """Generate root README.md summarizing all albums and image counts."""
    out_path = Path(output_dir)
    readme_file = out_path / "README.md"

    standard_albums = [a for a in albums if not a.id.startswith("_")]
    catch_all_albums = [a for a in albums if a.id.startswith("_")]
    total_album_images = sum(len(a.images) for a in standard_albums)
    total_catch_all_images = sum(len(a.images) for a in catch_all_albums) + len(uncategorized)
    total_unique = len(
        set(img.id for a in albums for img in a.images).union(
            set(img.id for img in uncategorized)
        )
    )

    lines = [
        "# Imgur Account Archive",
        "",
        f"- **Total Albums:** {len(standard_albums):,}",
        f"- **Images in Albums:** {total_album_images:,}",
    ]
    if total_catch_all_images > 0:
        lines.append(f"- **Non-Album Media:** {total_catch_all_images:,}")
    lines.append(f"- **Total Unique Images:** {total_unique:,}")
    if archive_source:
        lines.append(f"- **Source Archive:** `{Path(archive_source).name}`")

    lines.extend([
        "",
        "## Albums & Collections",
        "",
        "| Cover | Album Title | ID | Images | Date | Links |",
        "| :---: | :--- | :---: | :---: | :---: | :---: |",
    ])

    for a in sorted(albums, key=lambda x: (x.datetime or 0), reverse=True):
        date_str = a.datetime_iso[:10] if a.datetime_iso else "N/A"
        cover_id = a.cover or (a.images[0].id if a.images else "")
        cover_md = f"[{cover_id}](https://i.imgur.com/{cover_id}s.jpg)" if cover_id else "-"
        title_esc = a.display_title.replace("|", "\\|")
        folder = (album_dir_map or {}).get(a.id, a.id)
        if a.id.startswith("_"):
            links_md = f"[Gallery]({folder}/gallery.html) &bull; [Folder]({folder}/)"
            id_str = "`[Non-Album]`"
        else:
            links_md = f"[Gallery]({folder}/gallery.html) &bull; [Imgur]({a.link or f'https://imgur.com/a/{a.id}'})"
            id_str = f"`{a.id}`"
        lines.append(
            f"| {cover_md} | {title_esc} | {id_str} | {len(a.images)} | {date_str} | {links_md} |"
        )

    if uncategorized and not any(a.id == "_uncategorized" for a in albums):
        lines.extend([
            "",
            "## Uncategorized Images",
            "",
            f"There are **{len(uncategorized)}** images that did not belong to any album. Browse them in the [Uncategorized Gallery](_Uncategorized/gallery.html) or the `_Uncategorized` folder.",
        ])

    with open(readme_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return readme_file


def generate_html_catalog(
    output_dir: str | Path,
    albums: List[ImgurAlbum],
    uncategorized: List[ImgurImage],
    album_dir_map: Dict[str, str],
) -> Path:
    """Generate the root interactive, responsive HTML catalog linking to album galleries."""
    out_path = Path(output_dir)
    catalog_file = out_path / "catalog.html"

    standard_albums = [a for a in albums if not a.id.startswith("_")]
    catch_all_albums = [a for a in albums if a.id.startswith("_")]
    total_album_images = sum(len(a.images) for a in standard_albums)
    total_catch_all_images = sum(len(a.images) for a in catch_all_albums) + len(uncategorized)

    album_cards = []
    for a in sorted(albums, key=lambda x: (x.datetime or 0), reverse=True):
        a_dir_name = album_dir_map.get(a.id, a.id)
        cover_id = a.cover or (a.images[0].id if a.images else None)
        cover_url = (
            f"https://i.imgur.com/{cover_id}m.jpg"
            if cover_id
            else "https://s.imgur.com/images/favicon-96x96.png"
        )

        is_catch_all = a.id.startswith("_")
        title = html.escape(a.display_title)
        desc = html.escape(a.description or "")
        date_str = a.datetime_iso[:10] if a.datetime_iso else ""
        meta_str = (
            f"ID: <code>{a.id}</code>" + (f" &bull; {date_str}" if date_str else "")
            if not is_catch_all
            else "Media not associated with any specific album"
        )
        count = len(a.images)
        card_class = "album-card uncat-card" if is_catch_all else "album-card"
        badge_class = "badge badge-uncat" if is_catch_all else "badge"

        imgur_btn = (
            f'<a href="{a.link or f"https://imgur.com/a/{a.id}"}" target="_blank" rel="noopener" class="btn btn-secondary btn-imgur" title="View album on Imgur">Imgur</a>'
            if not is_catch_all
            else ""
        )

        album_cards.append(f"""
        <div class="{card_class}" data-title="{title.lower()}" data-id="{a.id.lower()}" data-gallery-url="{a_dir_name}/gallery.html">
            <a href="{a_dir_name}/gallery.html" class="album-cover-wrap" title="View {title} Gallery">
                <img src="{cover_url}" alt="{title}" loading="lazy" class="album-cover" onerror="this.src='https://s.imgur.com/images/favicon-96x96.png';">
                <span class="{badge_class}">{count} images</span>
            </a>
            <div class="album-info">
                <h3 class="album-title"><a href="{a_dir_name}/gallery.html" title="View Gallery">{title}</a></h3>
                <p class="album-meta">{meta_str}</p>
                {f'<p class="album-desc">{desc}</p>' if desc else ''}
                <div class="album-links">
                    <a href="{a_dir_name}/gallery.html" class="btn btn-primary" title="Open full photo gallery">Gallery</a>
                    <a href="{a_dir_name}/" class="btn btn-secondary btn-folder" title="Open local folder and file index">Open Folder</a>
                    {imgur_btn}
                </div>
            </div>
        </div>""")

    # Fallback legacy uncategorized card if uncategorized images exist and no catch-all album in albums
    if uncategorized and not any(a.id == "_uncategorized" for a in albums):
        uncat_first_id = uncategorized[0].id if uncategorized else None
        uncat_cover = (
            f"https://i.imgur.com/{uncat_first_id}m.jpg"
            if uncat_first_id
            else "https://s.imgur.com/images/favicon-96x96.png"
        )
        album_cards.append(f"""
        <div class="album-card uncat-card" data-title="uncategorized non-album images" data-id="_uncategorized" data-gallery-url="_Uncategorized/gallery.html">
            <a href="_Uncategorized/gallery.html" class="album-cover-wrap" title="View Uncategorized Gallery">
                <img src="{uncat_cover}" alt="Uncategorized Images" loading="lazy" class="album-cover" onerror="this.src='https://s.imgur.com/images/favicon-96x96.png';">
                <span class="badge badge-uncat">{len(uncategorized)} images</span>
            </a>
            <div class="album-info">
                <h3 class="album-title"><a href="_Uncategorized/gallery.html">Uncategorized Images</a></h3>
                <p class="album-meta">Media not associated with any specific album</p>
                <p class="album-desc">Preserved with original dump indices and filenames so nothing is lost.</p>
                <div class="album-links">
                    <a href="_Uncategorized/gallery.html" class="btn btn-primary">Gallery</a>
                    <a href="_Uncategorized/" class="btn btn-secondary btn-folder" title="Open folder index">Open Folder</a>
                </div>
            </div>
        </div>""")

    cards_html = "\n".join(album_cards)
    uncat_badge = (
        f'<span class="stat-badge stat-uncat"><strong>{total_catch_all_images}</strong> Non-Album Media</span>'
        if total_catch_all_images > 0
        else ""
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Imgur Account Catalog</title>
    <style>
        :root {{
            --bg-color: #121214;
            --card-bg: #1e1e24;
            --card-hover: #26262e;
            --text-main: #f0f0f5;
            --text-muted: #9ba1a6;
            --accent: #2ba640;
            --accent-hover: #34c74c;
            --border-color: #2e2e38;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-color);
            color: var(--text-main);
            padding: 2rem 1rem;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 2rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        h1 {{
            font-size: 2rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .stats {{
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }}
        .stat-badge {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            color: var(--text-muted);
        }}
        .stat-badge strong {{
            color: var(--text-main);
        }}
        .stat-uncat {{
            border-color: #d29922;
        }}
        .search-bar {{
            width: 100%;
            padding: 0.75rem 1.25rem;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-main);
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }}
        .search-bar:focus {{
            border-color: var(--accent);
        }}
        .albums-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1.5rem;
        }}
        .album-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s, background-color 0.2s;
            position: relative;
        }}
        .album-card:hover {{
            transform: translateY(-4px);
            background: var(--card-hover);
            box-shadow: 0 10px 28px rgba(0,0,0,0.5);
            border-color: rgba(43, 166, 64, 0.4);
        }}
        .album-cover-wrap {{
            position: relative;
            width: 100%;
            padding-top: 60%;
            background: #0d0d0f;
            display: block;
            overflow: hidden;
        }}
        .album-cover {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s;
        }}
        .album-card:hover .album-cover {{
            transform: scale(1.05);
        }}
        .badge {{
            position: absolute;
            bottom: 8px;
            right: 8px;
            background: rgba(0,0,0,0.75);
            backdrop-filter: blur(4px);
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-uncat {{
            background: rgba(187, 128, 9, 0.85);
        }}
        .album-info {{
            padding: 1.15rem;
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }}
        .album-title {{
            font-size: 1.125rem;
            margin-bottom: 0.35rem;
            line-height: 1.3;
        }}
        .album-title a {{
            color: var(--text-main);
            text-decoration: none;
            transition: color 0.2s;
        }}
        .album-card:hover .album-title a {{
            color: var(--accent);
        }}
        .album-meta {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
        }}
        .album-desc {{
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
            line-height: 1.4;
            max-height: 4.2em;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .album-links {{
            margin-top: auto;
            display: flex;
            gap: 0.5rem;
            position: relative;
            z-index: 2;
        }}
        .btn {{
            display: inline-block;
            padding: 0.45rem 0.85rem;
            border-radius: 6px;
            font-size: 0.875rem;
            font-weight: 600;
            text-decoration: none;
            text-align: center;
            flex: 1;
            transition: background 0.2s, transform 0.1s;
        }}
        .btn:active {{
            transform: scale(0.98);
        }}
        .btn-primary {{
            background: var(--accent);
            color: #ffffff;
            box-shadow: 0 2px 8px rgba(43, 166, 64, 0.3);
        }}
        .btn-primary:hover {{
            background: var(--accent-hover);
            color: #ffffff;
        }}
        .btn-secondary {{
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-muted);
        }}
        .btn-secondary:hover {{
            background: rgba(255,255,255,0.08);
            color: var(--text-main);
            border-color: #555562;
        }}
        code {{
            background: rgba(255,255,255,0.08);
            padding: 2px 4px;
            border-radius: 4px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-top">
                <h1>Imgur Account Archive</h1>
                <div class="stats">
                    <span class="stat-badge"><strong>{len(standard_albums)}</strong> Albums</span>
                    <span class="stat-badge"><strong>{total_album_images}</strong> Images in Albums</span>
                    {uncat_badge}
                </div>
            </div>
            <input type="text" id="searchInput" class="search-bar" placeholder="Search albums by title, description, or album ID..." autofocus>
        </header>

        <main class="albums-grid" id="albumsGrid">
            {cards_html}
        </main>
    </div>

    <script>
        const searchInput = document.getElementById('searchInput');
        const cards = document.querySelectorAll('.album-card');

        // Real-time filtering
        searchInput.addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase().trim();
            cards.forEach(card => {{
                const title = card.getAttribute('data-title') || '';
                const id = card.getAttribute('data-id') || '';
                if (title.includes(query) || id.includes(query)) {{
                    card.style.display = '';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }});

        // Default navigation to Gallery on card click unless clicking specific buttons
        cards.forEach(card => {{
            card.addEventListener('click', (e) => {{
                // Let explicit Open Folder or Imgur buttons handle their own clicks
                if (e.target.closest('.btn-secondary') || e.target.closest('button')) {{
                    return;
                }}
                const galleryUrl = card.getAttribute('data-gallery-url');
                if (galleryUrl) {{
                    window.location.href = galleryUrl;
                }}
            }});
        }});
    </script>
</body>
</html>
"""
    with open(catalog_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return catalog_file


def generate_album_gallery(
    album_dir: str | Path,
    album: ImgurAlbum,
    image_files: List[Tuple[ImgurImage, str]],
) -> Path:
    """Generate an interactive, responsive HTML photo gallery inside an album folder."""
    a_dir = Path(album_dir)
    gallery_file = a_dir / "gallery.html"

    # Pre-render photo items
    items_html = []
    items_json = []

    for idx, (img, filename) in enumerate(image_files, start=1):
        ext = Path(filename).suffix.lower()
        is_video = ext in (".mp4", ".webm") or img.animated and bool(img.mp4)
        title = html.escape(img.title or f"Photo #{idx}")
        desc = html.escape(img.description or "")
        date_str = img.datetime_iso[:10] if img.datetime_iso else ""
        dim_str = f"{img.width}×{img.height}" if img.width and img.height else ""
        size_str = format_size(img.size)

        # JSON data for client-side lightbox
        img_dict = img.to_dict()
        img_dict["local_filename"] = filename
        img_dict["is_video"] = is_video
        img_dict["order"] = idx
        img_dict["formatted_size"] = size_str
        items_json.append(img_dict)

        loading_attr = "eager" if idx <= 4 else "lazy"
        fetch_priority = 'fetchpriority="high"' if idx == 1 else ""

        if is_video:
            media_markup = f"""
            <div class="media-thumb-wrap video-wrap" onclick="openLightbox({idx - 1})" role="button" tabindex="0" aria-label="View {title}" title="View {title}">
                <video src="{filename}" preload="metadata" muted loop class="media-thumb"></video>
                <span class="video-play-badge">▶ Video</span>
            </div>"""
        else:
            media_markup = f"""
            <div class="media-thumb-wrap" onclick="openLightbox({idx - 1})" role="button" tabindex="0" aria-label="View {title}" title="View {title}">
                <img src="{filename}" alt="{title}" loading="{loading_attr}" {fetch_priority} class="media-thumb">
            </div>"""

        items_html.append(f"""
        <div class="photo-card" data-index="{idx - 1}" data-title="{title.lower()} {desc.lower()} {img.id.lower()}">
            {media_markup}
            <div class="photo-card-info">
                <div class="photo-header">
                    <span class="photo-idx">#{idx}</span>
                    <span class="photo-id"><code>{img.id}</code></span>
                    {f'<span class="photo-dims">{dim_str}</span>' if dim_str else ''}
                </div>
                {f'<h4 class="photo-title">{title}</h4>' if img.title else ''}
                {f'<p class="photo-desc">{desc}</p>' if desc else ''}
                <div class="photo-meta-bar">
                    <span>{size_str}</span>
                    <span>{date_str}</span>
                </div>
                <div class="photo-actions">
                    <button class="btn-card btn-view" onclick="openLightbox({idx - 1})">View</button>
                    <a href="{filename}" target="_blank" class="btn-card btn-file" title="Open original local file">File</a>
                    <a href="{img.link or f'https://i.imgur.com/{img.id}.jpg'}" target="_blank" rel="noopener" class="btn-card btn-ext" title="View on Imgur">Imgur</a>
                </div>
            </div>
        </div>""")

    cards_str = "\n".join(items_html)
    json_data_str = json.dumps(items_json, ensure_ascii=False)

    is_catch_all = album.id.startswith("_")
    album_title = html.escape(album.display_title)
    album_desc = html.escape(album.description or "")
    created_date = album.datetime_iso[:10] if album.datetime_iso else ""

    imgur_top_link = (
        f'<a href="{album.link or f"https://imgur.com/a/{album.id}"}" target="_blank" rel="noopener" class="btn-top">View on Imgur</a>'
        if not is_catch_all
        else ""
    )
    id_badge = (
        f'<span class="badge">Album ID: <code>{album.id}</code></span>'
        if not is_catch_all
        else '<span class="badge">Collection: <strong>Non-Album Media</strong></span>'
    )
    date_badge = (
        f'<span class="badge">Created: <strong>{created_date}</strong></span>'
        if created_date
        else ""
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{album_title} - Imgur Album Gallery</title>
    <style>
        :root {{
            --bg-color: #0f0f12;
            --card-bg: #18181d;
            --card-hover: #22222a;
            --text-main: #f0f0f5;
            --text-muted: #9ba1a6;
            --accent: #2ba640;
            --accent-hover: #34c74c;
            --border-color: #272730;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-color);
            color: var(--text-main);
            padding: 1.5rem 1rem 4rem 1rem;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .top-nav {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        .back-link {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.4rem 0.8rem;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            transition: background 0.2s, transform 0.1s;
        }}
        .back-link:hover {{
            background: var(--card-hover);
            transform: translateX(-2px);
        }}
        .nav-actions {{
            display: flex;
            gap: 0.5rem;
        }}
        .btn-top {{
            padding: 0.4rem 0.8rem;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s;
        }}
        .btn-top:hover {{
            background: var(--card-hover);
            color: var(--text-main);
            border-color: #4a4a58;
        }}
        .album-header {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        }}
        .album-header h1 {{
            font-size: 1.75rem;
            margin-bottom: 0.5rem;
            line-height: 1.3;
        }}
        .album-badges {{
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin-bottom: 0.75rem;
        }}
        .badge {{
            background: rgba(255,255,255,0.06);
            border: 1px solid var(--border-color);
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}
        .badge strong {{
            color: var(--text-main);
        }}
        .album-description {{
            margin-top: 1rem;
            font-size: 0.95rem;
            color: #c9cdd2;
            line-height: 1.5;
            background: rgba(0,0,0,0.25);
            padding: 0.85rem 1rem;
            border-radius: 8px;
            border-left: 3px solid var(--accent);
        }}
        .filter-bar {{
            width: 100%;
            padding: 0.75rem 1.25rem;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-main);
            font-size: 1rem;
            margin-bottom: 2rem;
            outline: none;
            transition: border-color 0.2s;
        }}
        .filter-bar:focus {{
            border-color: var(--accent);
        }}
        .gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1.5rem;
        }}
        .photo-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
        }}
        .photo-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            border-color: rgba(43, 166, 64, 0.4);
        }}
        .media-thumb-wrap {{
            position: relative;
            width: 100%;
            padding-top: 70%;
            background: #08080a;
            overflow: hidden;
            cursor: pointer;
        }}
        .media-thumb-wrap:focus-visible {{
            outline: 2px solid var(--accent);
            outline-offset: -2px;
        }}
        .media-thumb {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            cursor: pointer;
            transition: transform 0.3s;
        }}
        .photo-card:hover .media-thumb {{
            transform: scale(1.04);
        }}
        .video-play-badge {{
            position: absolute;
            bottom: 8px;
            right: 8px;
            background: rgba(0,0,0,0.8);
            color: #ffffff;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 4px;
        }}
        .photo-card-info {{
            padding: 0.85rem;
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }}
        .photo-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 0.4rem;
        }}
        .photo-idx {{
            font-weight: 700;
            color: var(--accent);
        }}
        .photo-title {{
            font-size: 0.95rem;
            margin-bottom: 0.25rem;
            line-height: 1.3;
        }}
        .photo-desc {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            line-height: 1.4;
            max-height: 2.8em;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .photo-meta-bar {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: auto;
            padding-top: 0.5rem;
            border-top: 1px solid rgba(255,255,255,0.05);
            margin-bottom: 0.65rem;
        }}
        .photo-actions {{
            display: flex;
            gap: 0.4rem;
        }}
        .btn-card {{
            flex: 1;
            padding: 0.35rem 0.5rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            text-align: center;
            border: 1px solid var(--border-color);
            background: transparent;
            color: var(--text-muted);
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s;
        }}
        .btn-card:hover {{
            color: var(--text-main);
            background: rgba(255,255,255,0.06);
            border-color: #555562;
        }}
        .btn-view {{
            background: rgba(43, 166, 64, 0.15);
            color: var(--accent);
            border-color: rgba(43, 166, 64, 0.3);
        }}
        .btn-view:hover {{
            background: var(--accent);
            color: #ffffff;
        }}
        code {{
            background: rgba(255,255,255,0.08);
            padding: 1px 4px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85em;
        }}

        /* Lightbox Dialog */
        dialog#lightbox {{
            position: fixed;
            inset: 0;
            width: 100vw;
            height: 100vh;
            max-width: 100vw;
            max-height: 100vh;
            background: rgba(6, 6, 8, 0.95);
            backdrop-filter: blur(12px);
            border: none;
            padding: 0;
            margin: 0;
            display: none;
            flex-direction: column;
            color: var(--text-main);
            z-index: 10000;
        }}
        dialog#lightbox[open] {{
            display: flex;
        }}
        dialog#lightbox::backdrop {{
            background: rgba(0, 0, 0, 0.9);
        }}
        .lightbox-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 1.25rem;
            background: rgba(18, 18, 22, 0.8);
            border-bottom: 1px solid var(--border-color);
            z-index: 2;
        }}
        .lightbox-counter {{
            font-size: 0.9rem;
            color: var(--text-muted);
        }}
        .lightbox-close {{
            background: transparent;
            border: none;
            color: var(--text-main);
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            transition: background 0.2s;
        }}
        .lightbox-close:hover {{
            background: rgba(255,255,255,0.1);
        }}
        .lightbox-main {{
            position: relative;
            flex-grow: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
            overflow: hidden;
        }}
        .lightbox-media {{
            max-width: 90vw;
            max-height: 75vh;
            object-fit: contain;
            border-radius: 6px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.8);
        }}
        .lightbox-nav {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(24, 24, 29, 0.7);
            border: 1px solid var(--border-color);
            color: #ffffff;
            font-size: 2rem;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
            user-select: none;
            z-index: 5;
        }}
        .lightbox-nav:hover {{
            background: var(--accent);
        }}
        .lightbox-prev {{
            left: 20px;
        }}
        .lightbox-next {{
            right: 20px;
        }}
        .lightbox-details {{
            background: rgba(18, 18, 22, 0.9);
            border-top: 1px solid var(--border-color);
            padding: 0.85rem 1.25rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            z-index: 2;
        }}
        .details-left {{
            max-width: 60%;
        }}
        .details-title {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 0.2rem;
        }}
        .details-desc {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        .details-right {{
            display: flex;
            gap: 0.5rem;
            align-items: center;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="top-nav">
            <a href="../catalog.html" class="back-link" title="Return to catalog">‹ All Albums</a>
            <div class="nav-actions">
                <a href="./" class="btn-top" title="Browse album folder directory index">Open Folder</a>
                {imgur_top_link}
                <a href="album_metadata.json" target="_blank" class="btn-top">Metadata JSON</a>
            </div>
        </div>

        <header class="album-header">
            <h1>{album_title}</h1>
            <div class="album-badges">
                {id_badge}
                {date_badge}
                <span class="badge">Images: <strong>{len(image_files)}</strong></span>
                {f'<span class="badge">Views: <strong>{album.views:,}</strong></span>' if album.views else ''}
                {f'<span class="badge">Privacy: <code>{album.privacy}</code></span>' if album.privacy else ''}
            </div>
            {f'<div class="album-description">{album_desc}</div>' if album_desc else ''}
        </header>

        <input type="text" id="photoFilter" class="filter-bar" placeholder="Filter photos in this album by title, description, or ID...">

        <main class="gallery-grid" id="galleryGrid">
            {cards_str}
        </main>
    </div>

    <!-- Lightbox Modal -->
    <dialog id="lightbox">
        <div class="lightbox-top">
            <span class="lightbox-counter" id="lbCounter">Photo 1 of {len(image_files)}</span>
            <button class="lightbox-close" onclick="closeLightbox()" title="Close (Esc)">✕</button>
        </div>
        <div class="lightbox-main" onclick="onLightboxBackdropClick(event)">
            <button class="lightbox-nav lightbox-prev" onclick="navigateLightbox(-1)" title="Previous (Left Arrow)">‹</button>
            <div id="mediaContainer"></div>
            <button class="lightbox-nav lightbox-next" onclick="navigateLightbox(1)" title="Next (Right Arrow)">›</button>
        </div>
        <div class="lightbox-details">
            <div class="details-left">
                <div class="details-title" id="lbTitle"></div>
                <div class="details-desc" id="lbDesc"></div>
            </div>
            <div class="details-right">
                <span id="lbMeta"></span>
                <a id="lbFileLink" href="#" target="_blank" class="btn-card">Open Full File</a>
                <a id="lbImgurLink" href="#" target="_blank" rel="noopener" class="btn-card">Imgur</a>
            </div>
        </div>
    </dialog>

    <script id="galleryData" type="application/json">
        {json_data_str}
    </script>

    <script>
        const photos = JSON.parse(document.getElementById('galleryData').textContent);
        const lightbox = document.getElementById('lightbox');
        const mediaContainer = document.getElementById('mediaContainer');
        const lbCounter = document.getElementById('lbCounter');
        const lbTitle = document.getElementById('lbTitle');
        const lbDesc = document.getElementById('lbDesc');
        const lbMeta = document.getElementById('lbMeta');
        const lbFileLink = document.getElementById('lbFileLink');
        const lbImgurLink = document.getElementById('lbImgurLink');
        let currentIndex = 0;

        function openLightbox(index) {{
            if (index < 0 || index >= photos.length) return;
            currentIndex = index;
            updateLightbox();
            lightbox.showModal();
        }}

        function closeLightbox() {{
            lightbox.close();
            mediaContainer.innerHTML = '';
        }}

        function onLightboxBackdropClick(e) {{
            if (e.target.classList.contains('lightbox-main')) {{
                closeLightbox();
            }}
        }}

        function navigateLightbox(delta) {{
            let next = currentIndex + delta;
            if (next < 0) next = photos.length - 1;
            if (next >= photos.length) next = 0;
            currentIndex = next;
            updateLightbox();
        }}

        function updateLightbox() {{
            const item = photos[currentIndex];
            lbCounter.textContent = `Photo ${{currentIndex + 1}} of ${{photos.length}}`;
            lbTitle.textContent = item.title || `Photo #${{currentIndex + 1}} (${{item.id}})`;
            lbDesc.textContent = item.description || '';
            
            const metaParts = [];
            if (item.width && item.height) metaParts.push(`${{item.width}}×${{item.height}}`);
            if (item.formatted_size) metaParts.push(item.formatted_size);
            if (item.datetime_iso) metaParts.push(item.datetime_iso.slice(0, 10));
            lbMeta.textContent = metaParts.join(' • ');

            lbFileLink.href = item.local_filename;
            lbImgurLink.href = item.link || `https://i.imgur.com/${{item.id}}.jpg`;

            if (item.is_video) {{
                mediaContainer.innerHTML = `<video src="${{item.local_filename}}" controls autoplay loop class="lightbox-media"></video>`;
            }} else {{
                mediaContainer.innerHTML = `<img src="${{item.local_filename}}" alt="${{item.title || item.id}}" class="lightbox-media">`;
            }}
        }}

        // Keyboard navigation
        window.addEventListener('keydown', (e) => {{
            if (!lightbox.open) return;
            if (e.key === 'ArrowLeft') {{
                navigateLightbox(-1);
            }} else if (e.key === 'ArrowRight') {{
                navigateLightbox(1);
            }} else if (e.key === 'Escape') {{
                closeLightbox();
            }}
        }});

        // Filter photos
        const photoFilter = document.getElementById('photoFilter');
        const photoCards = document.querySelectorAll('.photo-card');
        photoFilter.addEventListener('input', (e) => {{
            const q = e.target.value.toLowerCase().trim();
            photoCards.forEach(card => {{
                const text = card.getAttribute('data-title') || '';
                card.style.display = text.includes(q) ? '' : 'none';
            }});
        }});

        // Clicking anywhere on card (except File/Imgur links) opens lightbox like View button
        photoCards.forEach(card => {{
            card.addEventListener('click', (e) => {{
                // Let explicit File or Imgur links handle their own clicks
                if (e.target.closest('.btn-file') || e.target.closest('.btn-ext') || e.target.closest('.btn-view') || e.target.closest('.media-thumb-wrap')) {{
                    return;
                }}
                const idx = parseInt(card.getAttribute('data-index'), 10);
                if (!isNaN(idx)) {{
                    openLightbox(idx);
                }}
            }});
        }});

        // Keyboard activation on focused thumbnail wraps
        document.querySelectorAll('.media-thumb-wrap').forEach(wrap => {{
            wrap.addEventListener('keydown', (e) => {{
                if (e.key === 'Enter' || e.key === ' ') {{
                    e.preventDefault();
                    wrap.click();
                }}
            }});
        }});
    </script>
</body>
</html>
"""
    with open(gallery_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return gallery_file


def generate_uncategorized_gallery(
    uncat_dir: str | Path,
    image_files: List[Tuple[ImgurImage, str]],
) -> Path:
    """Generate gallery.html for uncategorized non-album images."""
    u_dir = Path(uncat_dir)
    gallery_file = u_dir / "gallery.html"

    fake_album = ImgurAlbum(
        id="_Uncategorized",
        title="Uncategorized Images",
        description="All media from your backup that does not belong to any specific album. Preserved with original indices.",
        images=[img for img, _ in image_files],
    )

    return generate_album_gallery(u_dir, fake_album, image_files)
