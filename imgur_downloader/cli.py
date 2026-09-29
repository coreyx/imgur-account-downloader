"""Command-line interface for Imgur Account Downloader."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .archive import LocalArchive, find_local_archive
from .catalog import generate_html_catalog, generate_manifest, generate_readme
from .client import ImgurAuthError, ImgurClient
from .models import ImgurAlbum, ImgurImage
from .organizer import ArchiveOrganizer

console = Console()
logger = logging.getLogger("imgur_downloader")


def setup_logging(verbose: bool) -> None:
    """Configure console logging level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def print_banner() -> None:
    """Display CLI welcome banner."""
    console.print(
        Panel.fit(
            "[bold green]Imgur Account Downloader & Organizer[/bold green]\n"
            "[dim]Maximal Metadata Preservation & Local Archive Extractor[/dim]",
            border_style="green",
        )
    )


def print_auth_help() -> None:
    """Print step-by-step instructions on obtaining an access token or cookie."""
    console.print(
        Panel(
            "[bold yellow]How to authenticate with Imgur:[/bold yellow]\n\n"
            "1. Open [cyan]https://imgur.com[/cyan] in Chrome, Edge, or Firefox (logged in).\n"
            "2. Press [bold]F12[/bold] (DevTools) and switch to the [bold]Application[/bold] tab (or [bold]Storage[/bold] in Firefox).\n"
            "3. In the left sidebar, expand [bold]Cookies[/bold] -> click [cyan]https://imgur.com[/cyan].\n"
            "4. Find the cookie named [bold green]accesstoken[/bold green] and copy its Value.\n"
            "5. Re-run this command with:\n"
            "   [bold]--token <COPIED_TOKEN>[/bold] or set [bold]IMGUR_ACCESS_TOKEN=<COPIED_TOKEN>[/bold]\n\n"
            "[dim]Alternatively, you can provide an album list file with [bold]--albums-file albums.txt[/bold][/dim]",
            title="Authentication Guide",
            border_style="yellow",
        )
    )


def load_cached_albums(cache_path: Path) -> Optional[List[ImgurAlbum]]:
    """Load cached albums list if available."""
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [ImgurAlbum.from_api_dict(item) for item in data]
        if isinstance(data, dict) and "albums" in data:
            return [ImgurAlbum.from_api_dict(item) for item in data["albums"]]
    except Exception as e:
        console.print(f"[yellow]Warning: Could not read cache {cache_path}: {e}[/yellow]")
    return None


def save_cached_albums(cache_path: Path, albums: List[ImgurAlbum]) -> None:
    """Save albums to cache file."""
    try:
        data = [a.to_dict() for a in albums]
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        console.print(f"[dim]Saved metadata cache to {cache_path}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not save cache {cache_path}: {e}[/yellow]")


def load_config_file(config_path: Optional[str] = None) -> dict:
    """Load configuration from config.yml or specified path."""
    target: Optional[Path] = None
    if config_path:
        target = Path(config_path)
        if not target.exists():
            console.print(f"[bold red]Config file not found:[/bold red] {config_path}")
            sys.exit(1)
    else:
        for fname in ["config.yml", "config.yaml"]:
            p = Path(fname)
            if p.exists():
                target = p
                break

    if not target:
        return {}

    try:
        import yaml
        with open(target, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                return {}
            console.print(f"[dim]Loaded configuration from {target.name}[/dim]")
            return data
    except Exception as e:
        console.print(f"[yellow]Warning: Could not read config file {target}: {e}[/yellow]")
        return {}


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--config",
    type=click.Path(),
    default=None,
    help="Path to YAML configuration file (default: looks for config.yml or config.yaml).",
)
@click.option(
    "--local-archive",
    "-a",
    "--archive",
    type=click.Path(),
    envvar="IMGUR_LOCAL_ARCHIVE",
    default=None,
    help="Path to Imgur account images zip file or extracted directory. Auto-detects in current directory or ~/Downloads if omitted.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="imgur_archive",
    help="Output directory for organized albums. Default: ./imgur_archive",
)
@click.option(
    "--token",
    "-t",
    envvar="IMGUR_ACCESS_TOKEN",
    default=None,
    help="Imgur access token or Bearer token (or set IMGUR_ACCESS_TOKEN env var).",
)
@click.option(
    "--cookie",
    "-c",
    envvar="IMGUR_COOKIE",
    default=None,
    help="Imgur cookie string (e.g. accesstoken=...) or set IMGUR_COOKIE env var.",
)
@click.option(
    "--cookies-file",
    type=click.Path(exists=True),
    default=None,
    help="Path to cookies.txt in Netscape format.",
)
@click.option(
    "--albums-file",
    type=click.Path(exists=True),
    default=None,
    help="Text file with album URLs or IDs (one per line).",
)
@click.option(
    "--album",
    multiple=True,
    help="Single album ID/URL or multiple (can be repeated).",
)
@click.option(
    "--client-id",
    default=None,
    help="Custom Imgur API Client ID.",
)
@click.option(
    "--cache-file",
    type=click.Path(),
    default="imgur_metadata_cache.json",
    help="Path to store or load metadata cache. Default: imgur_metadata_cache.json",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Bypass existing metadata cache and re-fetch from API.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate the organization process without writing or downloading files.",
)
@click.option(
    "--embed-exif/--no-embed-exif",
    default=True,
    help="Embed EXIF metadata losslessly into JPEG images (default: True).",
)
@click.option(
    "--set-timestamps/--no-timestamps",
    default=True,
    help="Set file modification and creation timestamps to Imgur upload date (default: True).",
)
@click.option(
    "--sidecar-json",
    is_flag=True,
    help="Generate individual .json sidecar files for every image.",
)
@click.option(
    "--preserve-filenames",
    is_flag=True,
    help="Preserve original dump filenames (e.g. '1 - TzIN9Qm.png') instead of ordering by album.",
)
@click.option(
    "--folder-template",
    default="{title} [{id}]",
    help="Folder naming template for albums. Default: '{title} [{id}]'.",
)
@click.option(
    "--ignore-album",
    multiple=True,
    help="Album ID or title (or wildcard pattern, e.g. 'Memes*') to ignore/skip (can be repeated).",
)
@click.option(
    "--ignore-albums-file",
    type=click.Path(exists=True),
    default=None,
    help="Text file with album IDs or titles to ignore (one per line).",
)
@click.option(
    "--exclude-ignored-images/--include-ignored-images",
    default=True,
    help="Exclude images belonging to ignored albums from catch-all album (default: True).",
)
@click.option(
    "--enable-catch-all/--no-catch-all",
    default=None,
    help="Create a dedicated catch-all album for images without an album association (default: True).",
)
@click.option(
    "--leave-out-non-album-images/--include-non-album-images",
    default=None,
    help="Leave out images that are not in an album (do not create catch-all folder or extract non-album media). Default: False.",
)
@click.option(
    "--catch-all-title",
    default="Non-Album Images",
    help="Display title for the catch-all album. Default: 'Non-Album Images'.",
)
@click.option(
    "--catch-all-folder",
    default="Non-Album Images [_uncategorized]",
    help="Folder name for the catch-all album. Default: 'Non-Album Images [_uncategorized]'.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose debug logging.",
)
def cli(
    ctx: click.Context,
    config: Optional[str],
    local_archive: Optional[str],
    output_dir: str,
    token: Optional[str],
    cookie: Optional[str],
    cookies_file: Optional[str],
    albums_file: Optional[str],
    album: tuple,
    client_id: Optional[str],
    cache_file: str,
    no_cache: bool,
    dry_run: bool,
    embed_exif: bool,
    set_timestamps: bool,
    sidecar_json: bool,
    preserve_filenames: bool,
    folder_template: str,
    ignore_album: tuple,
    ignore_albums_file: Optional[str],
    exclude_ignored_images: bool,
    enable_catch_all: Optional[bool],
    leave_out_non_album_images: Optional[bool],
    catch_all_title: str,
    catch_all_folder: str,
    verbose: bool,
) -> None:
    """Retrieve and organize all images from an Imgur account by album with maximal metadata."""
    setup_logging(verbose)

    # If subcommands like 'inspect-archive' are invoked, let Click route to them
    if ctx.invoked_subcommand is not None:
        return

    print_banner()

    # Load configuration from config.yml or specified path
    cfg = load_config_file(config)
    token = token or cfg.get("token") or cfg.get("access_token")
    cookie = cookie or cfg.get("cookie")
    cookies_file = cookies_file or cfg.get("cookies_file")
    client_id = client_id or cfg.get("client_id")
    local_archive = (
        local_archive
        or cfg.get("local_archive")
        or cfg.get("archive_path")
        or cfg.get("archive")
        or cfg.get("zip_path")
        or cfg.get("zip_file")
        or os.environ.get("IMGUR_LOCAL_ARCHIVE")
        or os.environ.get("IMGUR_ARCHIVE")
    )
    if output_dir == "imgur_archive" and "output_dir" in cfg:
        output_dir = str(cfg["output_dir"])
    if cache_file == "imgur_metadata_cache.json" and "cache_file" in cfg:
        cache_file = str(cfg["cache_file"])
    albums_file = albums_file or cfg.get("albums_file")
    if not album and "albums" in cfg and isinstance(cfg["albums"], list):
        album = tuple(cfg["albums"])
    if "embed_exif" in cfg:
        embed_exif = bool(cfg["embed_exif"])
    if "set_timestamps" in cfg:
        set_timestamps = bool(cfg["set_timestamps"])
    if "sidecar_json" in cfg:
        sidecar_json = bool(cfg["sidecar_json"])
    if "preserve_filenames" in cfg:
        preserve_filenames = bool(cfg["preserve_filenames"])
    if folder_template == "{title} [{id}]" and "folder_template" in cfg:
        folder_template = str(cfg["folder_template"])

    # Merge ignore_albums from CLI and config
    combined_ignore = list(ignore_album)
    if "ignore_albums" in cfg and isinstance(cfg["ignore_albums"], list):
        combined_ignore.extend(cfg["ignore_albums"])

    ignore_file_target = ignore_albums_file or cfg.get("ignore_albums_file")
    if ignore_file_target:
        p = Path(ignore_file_target)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        combined_ignore.append(line)
        else:
            console.print(f"[yellow]Warning: ignore_albums_file '{p}' not found.[/yellow]")

    if "exclude_ignored_images" in cfg:
        exclude_ignored_images = bool(cfg["exclude_ignored_images"])

    if leave_out_non_album_images is None:
        if "leave_out_non_album_images" in cfg:
            leave_out_non_album_images = bool(cfg["leave_out_non_album_images"])
        elif "exclude_non_album_images" in cfg:
            leave_out_non_album_images = bool(cfg["exclude_non_album_images"])
        elif "omit_non_album_images" in cfg:
            leave_out_non_album_images = bool(cfg["omit_non_album_images"])
        elif "skip_non_album_images" in cfg:
            leave_out_non_album_images = bool(cfg["skip_non_album_images"])
        elif "include_non_album_images" in cfg:
            leave_out_non_album_images = not bool(cfg["include_non_album_images"])
        else:
            leave_out_non_album_images = False

    if enable_catch_all is None:
        if "enable_catch_all" in cfg:
            enable_catch_all = bool(cfg["enable_catch_all"])
        else:
            enable_catch_all = True

    if catch_all_title == "Non-Album Images" and "catch_all_title" in cfg:
        catch_all_title = str(cfg["catch_all_title"])
    if catch_all_folder == "Non-Album Images [_uncategorized]" and "catch_all_folder" in cfg:
        catch_all_folder = str(cfg["catch_all_folder"])

    # 1. Locate local archive
    archive_path = None
    if local_archive and str(local_archive).strip():
        raw_archive = str(local_archive).strip()
        candidate = Path(raw_archive).expanduser()
        if not candidate.is_absolute() and not candidate.exists() and config:
            cfg_dir_candidate = Path(config).parent.joinpath(candidate)
            if cfg_dir_candidate.exists():
                candidate = cfg_dir_candidate
        if not candidate.exists():
            console.print(f"[bold red]Configured local archive not found:[/bold red] {raw_archive}")
            console.print("[dim]Please check the path in config.yml or command-line options.[/dim]")
            sys.exit(1)
        archive_path = candidate.resolve()
        console.print(f"[bold green]Using local archive:[/bold green] [cyan]{archive_path}[/cyan]")
    else:
        detected = find_local_archive()
        if detected:
            archive_path = detected
            console.print(f"[bold green]Auto-detected local archive:[/bold green] [cyan]{archive_path.name}[/cyan]")
        else:
            console.print("[dim]No local archive specified or auto-detected. Images will be downloaded from Imgur.[/dim]")

    # 2. Check for cached metadata
    cache_path = Path(cache_file)
    albums: List[ImgurAlbum] = []
    if not no_cache and cache_path.exists():
        console.print(f"[bold cyan]Found metadata cache:[/bold cyan] {cache_path}")
        loaded = load_cached_albums(cache_path)
        if loaded:
            albums = loaded
            console.print(f"[green]Loaded {len(albums)} albums from cache.[/green]")

    # 3. If no albums loaded from cache, fetch from Imgur API
    client = ImgurClient(
        client_id=client_id,
        access_token=token,
        cookie=cookie,
        cookies_file=cookies_file,
    )

    if not albums:
        album_ids_to_fetch = list(album)

        if albums_file:
            with open(albums_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        album_ids_to_fetch.append(line)

        if album_ids_to_fetch:
            console.print(f"[cyan]Fetching {len(album_ids_to_fetch)} specified albums from Imgur...[/cyan]")
            for aid in album_ids_to_fetch:
                try:
                    alb = client.get_album(aid)
                    albums.append(alb)
                    console.print(f"  [green]OK[/green] [bold]{alb.display_title}[/bold] ({len(alb.images)} images)")
                except Exception as e:
                    console.print(f"  [red]Failed to fetch album {aid}:[/red] {e}")
        else:
            # Attempt to fetch account albums
            has_auth = bool(token or cookie or cookies_file)
            if not has_auth:
                console.print(
                    "[yellow]No access token or cookie provided.[/yellow]"
                )
                print_auth_help()
                token_input = click.prompt(
                    "\nPaste your Imgur accesstoken / cookie (or press Enter to skip)",
                    default="",
                    show_default=False,
                )
                if token_input.strip():
                    token = token_input.strip()
                    client._configure_auth(cookie=token, cookies_file=None)
                    has_auth = True

            if has_auth:
                console.print("[cyan]Fetching account albums from Imgur API...[/cyan]")
                try:
                    for alb in client.get_account_albums():
                        albums.append(alb)
                        console.print(f"  Found album: [bold]{alb.display_title}[/bold] ({len(alb.images)} images)")
                    console.print(f"[bold green]Retrieved {len(albums)} account albums![/bold green]")
                except ImgurAuthError as e:
                    console.print(f"[bold red]Authentication Error:[/bold red] {e}")
                    print_auth_help()
                    sys.exit(1)
                except Exception as e:
                    console.print(f"[bold red]Error fetching account albums:[/bold red] {e}")
            else:
                console.print(
                    "[bold red]Cannot retrieve albums without authentication or an album list.[/bold red]"
                )
                console.print(
                    "You can still inspect the local archive using: [bold]python -m imgur_downloader inspect-archive[/bold]"
                )
                sys.exit(1)

        # Save to cache
        if albums and not dry_run:
            save_cached_albums(cache_path, albums)

    if not albums:
        console.print("[bold red]No albums found to organize.[/bold red]")
        sys.exit(1)

    # 4. Run Organization
    archive_obj = LocalArchive(archive_path) if archive_path else None
    organizer = ArchiveOrganizer(
        output_dir=output_dir,
        archive=archive_obj,
        client=client,
        console=console,
        embed_exif=embed_exif,
        set_timestamps=set_timestamps,
        write_sidecars=sidecar_json,
        preserve_archive_filenames=preserve_filenames,
        folder_template=folder_template,
        ignore_albums=combined_ignore,
        exclude_ignored_images=exclude_ignored_images,
        enable_catch_all=enable_catch_all,
        leave_out_non_album_images=leave_out_non_album_images,
        catch_all_title=catch_all_title,
        catch_all_folder=catch_all_folder,
        dry_run=dry_run,
    )

    try:
        stats = organizer.organize(albums)
    finally:
        if archive_obj:
            archive_obj.close()

    # 5. Display Summary
    summary_table = Table(title="Organization Summary", border_style="green")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="bold green", justify="right")

    summary_table.add_row("Albums Processed", str(stats["albums_processed"]))
    if stats.get("albums_ignored", 0) > 0:
        summary_table.add_row("Albums Ignored (Skipped)", str(stats["albums_ignored"]))
    summary_table.add_row("Images from Local Archive", str(stats["images_extracted_from_archive"]))
    summary_table.add_row("Images Downloaded", str(stats["images_downloaded"]))
    if stats.get("catch_all_images", 0) > 0:
        summary_table.add_row("Catch-All Images", str(stats["catch_all_images"]))
    if stats.get("non_album_images_omitted", 0) > 0:
        summary_table.add_row("Non-Album Images Omitted", str(stats["non_album_images_omitted"]))
    summary_table.add_row("Errors Encountered", str(stats["errors"]))

    console.print("\n", summary_table)

    if not dry_run:
        out_p = Path(output_dir).resolve()
        console.print(f"\n[bold green]Success![/bold green] Your archive is organized at:")
        console.print(f"  [cyan]{out_p}[/cyan]")
        console.print(f"  Open [bold cyan]{out_p / 'catalog.html'}[/bold cyan] in your browser to view your visual gallery!")


@cli.command("inspect-archive")
@click.argument("archive_path", required=False, type=click.Path())
@click.option("--config", type=click.Path(), default=None, help="Path to YAML configuration file.")
def inspect_archive_cmd(archive_path: Optional[str], config: Optional[str]) -> None:
    """Inspect local Imgur zip dump or directory and show summary statistics."""
    print_banner()

    cfg = load_config_file(config)
    archive_val = (
        archive_path
        or cfg.get("local_archive")
        or cfg.get("archive_path")
        or cfg.get("archive")
        or cfg.get("zip_path")
        or cfg.get("zip_file")
        or os.environ.get("IMGUR_LOCAL_ARCHIVE")
        or os.environ.get("IMGUR_ARCHIVE")
    )

    target = None
    if archive_val and str(archive_val).strip():
        raw_val = str(archive_val).strip()
        p = Path(raw_val).expanduser()
        if not p.is_absolute() and not p.exists() and config:
            cfg_dir_candidate = Path(config).parent.joinpath(p)
            if cfg_dir_candidate.exists():
                p = cfg_dir_candidate
        if not p.exists():
            console.print(f"[bold red]Archive not found at:[/bold red] {raw_val}")
            sys.exit(1)
        target = p.resolve()
    else:
        target = find_local_archive()

    if not target:
        console.print("[bold red]No local archive specified or auto-detected.[/bold red]")
        console.print("[dim]Specify a path: python -m imgur_downloader inspect-archive <path_to_zip>[/dim]")
        console.print("[dim]Or configure 'local_archive' in config.yml[/dim]")
        sys.exit(1)

    console.print(f"[bold cyan]Inspecting archive:[/bold cyan] {target.resolve()}\n")

    with LocalArchive(target) as archive:
        items = archive.all_items()
        ext_counts: dict = {}
        indexed_count = 0
        total_bytes = 0

        for it in items:
            ext_counts[it.extension] = ext_counts.get(it.extension, 0) + 1
            if it.index is not None:
                indexed_count += 1
            if it.size:
                total_bytes += it.size

        table = Table(title=f"Archive Contents: {target.name}", border_style="cyan")
        table.add_column("Property", style="bold")
        table.add_column("Value", style="green")

        table.add_row("Total Files", f"{len(items):,}")
        table.add_row("Unique Imgur IDs", f"{len(archive.all_ids()):,}")
        table.add_row("Numbered Prefixes", f"{indexed_count:,}")
        table.add_row("Total Archive Size", f"{total_bytes / (1024*1024*1024):.2f} GB")

        for ext, cnt in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True):
            table.add_row(f"  Format .{ext}", f"{cnt:,}")

        console.print(table)

        # Show samples
        sample_table = Table(title="Sample Parsed Items", border_style="dim")
        sample_table.add_column("Index", justify="right")
        sample_table.add_column("Imgur ID", style="bold cyan")
        sample_table.add_column("Original Filename", style="dim")

        for it in items[:10]:
            sample_table.add_row(
                str(it.index) if it.index is not None else "-",
                it.id,
                it.filename,
            )

        console.print("\n", sample_table)


@cli.command("fetch-metadata")
@click.option("--config", type=click.Path(), default=None, help="Path to YAML configuration file.")
@click.option("--token", "-t", envvar="IMGUR_ACCESS_TOKEN", help="Imgur access token.")
@click.option("--cookie", "-c", envvar="IMGUR_COOKIE", help="Imgur cookie string.")
@click.option("--cookies-file", type=click.Path(exists=True), help="Netscape cookies file.")
@click.option("--albums-file", type=click.Path(exists=True), help="Text file with album URLs/IDs.")
@click.option("--album", multiple=True, help="Album ID or URL.")
@click.option("--client-id", help="Custom Imgur Client ID.")
@click.option("--output", "-o", default="imgur_metadata_cache.json", help="Output JSON path.")
def fetch_metadata_cmd(
    config: Optional[str],
    token: Optional[str],
    cookie: Optional[str],
    cookies_file: Optional[str],
    albums_file: Optional[str],
    album: tuple,
    client_id: Optional[str],
    output: str,
) -> None:
    """Fetch album and image metadata from Imgur and save to JSON cache."""
    print_banner()

    cfg = load_config_file(config)
    token = token or cfg.get("token") or cfg.get("access_token")
    cookie = cookie or cfg.get("cookie")
    cookies_file = cookies_file or cfg.get("cookies_file")
    client_id = client_id or cfg.get("client_id")
    albums_file = albums_file or cfg.get("albums_file")
    if not album and "albums" in cfg and isinstance(cfg["albums"], list):
        album = tuple(cfg["albums"])
    if output == "imgur_metadata_cache.json" and "cache_file" in cfg:
        output = str(cfg["cache_file"])

    client = ImgurClient(
        client_id=client_id,
        access_token=token,
        cookie=cookie,
        cookies_file=cookies_file,
    )

    albums: List[ImgurAlbum] = []
    album_ids = list(album)

    if albums_file:
        with open(albums_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    album_ids.append(line)

    if album_ids:
        console.print(f"[cyan]Fetching {len(album_ids)} albums...[/cyan]")
        for aid in album_ids:
            try:
                a = client.get_album(aid)
                albums.append(a)
                console.print(f"  [green]OK[/green] {a.display_title}")
            except Exception as e:
                console.print(f"  [red]Failed {aid}:[/red] {e}")
    else:
        if not (token or cookie or cookies_file):
            print_auth_help()
            sys.exit(1)
        console.print("[cyan]Fetching account albums...[/cyan]")
        for a in client.get_account_albums():
            albums.append(a)
            console.print(f"  [green]OK[/green] {a.display_title}")

    save_cached_albums(Path(output), albums)
    console.print(f"[bold green]Successfully saved {len(albums)} albums to {output}[/bold green]")
