"""Imgur API and Web Client for retrieving account albums, images, and metadata."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
import requests

from .models import ImgurAlbum, ImgurImage

logger = logging.getLogger(__name__)

# Default public client ID used by the official Imgur web application
DEFAULT_CLIENT_ID = "546c25a59c58ad7"
API_BASE_URL = "https://api.imgur.com"


class ImgurRateLimitError(Exception):
    """Raised when Imgur API rate limit is exceeded."""


class ImgurAuthError(Exception):
    """Raised when authentication fails (401 / 403)."""


class ImgurClient:
    """Handles communication with Imgur REST API and internal web endpoints."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        access_token: Optional[str] = None,
        cookie: Optional[str] = None,
        cookies_file: Optional[str | Path] = None,
        max_retries: int = 5,
        timeout: int = 30,
    ):
        self.client_id = client_id or DEFAULT_CLIENT_ID
        self.access_token = access_token
        self.cookie = cookie
        self.max_retries = max_retries
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://imgur.com",
                "Referer": "https://imgur.com/",
            }
        )

        self._configure_auth(cookie, cookies_file)

        self.rate_limit_user_remaining: Optional[int] = None
        self.rate_limit_client_remaining: Optional[int] = None
        self.rate_limit_user_reset: Optional[int] = None

    def _configure_auth(
        self,
        cookie: Optional[str],
        cookies_file: Optional[str | Path],
    ) -> None:
        """Set up headers and cookies based on provided auth credentials."""
        # 1. Bearer access token
        if self.access_token:
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        else:
            self.session.headers["Authorization"] = f"Client-ID {self.client_id}"

        # 2. Cookies string
        if cookie:
            # If cookie string is just the token value (e.g. 64-char hex or alphanumeric)
            if "=" not in cookie:
                self.session.cookies.set("accesstoken", cookie, domain=".imgur.com")
            else:
                for part in cookie.split(";"):
                    part = part.strip()
                    if "=" in part:
                        k, v = part.split("=", 1)
                        self.session.cookies.set(k.strip(), v.strip(), domain=".imgur.com")

        # 3. Cookies file (Netscape format)
        if cookies_file:
            cpath = Path(cookies_file)
            if cpath.exists():
                self._load_netscape_cookies(cpath)

        # If we have an accesstoken cookie but no Bearer header, add Bearer header too
        at_cookie = self.session.cookies.get("accesstoken", domain=".imgur.com")
        if at_cookie and not self.access_token:
            self.access_token = at_cookie
            self.session.headers["Authorization"] = f"Bearer {at_cookie}"

    def _load_netscape_cookies(self, path: Path) -> None:
        """Load Netscape format cookies.txt."""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                fields = line.split("\t")
                if len(fields) >= 7:
                    domain, _, c_path, secure, _, name, value = fields[:7]
                    self.session.cookies.set(
                        name, value, domain=domain, path=c_path, secure=(secure == "TRUE")
                    )

    def _update_rate_limits(self, resp: requests.Response) -> None:
        """Parse rate limit response headers."""
        headers = resp.headers
        try:
            if "X-RateLimit-UserRemaining" in headers:
                self.rate_limit_user_remaining = int(headers["X-RateLimit-UserRemaining"])
            if "X-RateLimit-ClientRemaining" in headers:
                self.rate_limit_client_remaining = int(headers["X-RateLimit-ClientRemaining"])
            if "X-RateLimit-UserReset" in headers:
                self.rate_limit_user_reset = int(headers["X-RateLimit-UserReset"])
        except (ValueError, TypeError):
            pass

    def request(
        self,
        method: str,
        endpoint_or_url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated request to Imgur API with automatic retry and rate-limit handling."""
        if endpoint_or_url.startswith("http://") or endpoint_or_url.startswith("https://"):
            url = endpoint_or_url
        else:
            url = f"{API_BASE_URL}{endpoint_or_url}"

        retry_count = 0
        backoff = 2.0

        while True:
            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                )
                self._update_rate_limits(resp)

                if resp.status_code in (429, 503):
                    retry_count += 1
                    if retry_count > self.max_retries:
                        raise ImgurRateLimitError(
                            f"Rate limit exceeded (HTTP {resp.status_code}) after {self.max_retries} retries."
                        )
                    wait_time = backoff
                    if self.rate_limit_user_remaining == 0 and self.rate_limit_user_reset:
                        wait_time = max(wait_time, min(self.rate_limit_user_reset + 1, 60))
                    logger.warning(
                        "Received HTTP %d, backing off for %.1f seconds...",
                        resp.status_code,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    backoff *= 2.0
                    continue

                if resp.status_code in (401, 403):
                    err_msg = ""
                    try:
                        err_msg = resp.json().get("data", {}).get("error", resp.text)
                    except Exception:
                        err_msg = resp.text
                    raise ImgurAuthError(
                        f"Authentication failed (HTTP {resp.status_code}): {err_msg}"
                    )

                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.RequestException as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    raise
                logger.warning("Request error (%s), retrying in %.1fs...", e, backoff)
                time.sleep(backoff)
                backoff *= 2.0

    # -------------------------------------------------------------------------
    # High-level API calls
    # -------------------------------------------------------------------------

    def get_album(self, album_id: str) -> ImgurAlbum:
        """Fetch full details and all images for an album ID."""
        # Clean album hash (strip any URL prefixes)
        clean_id = album_id.strip().split("/")[-1].split("#")[0].split("?")[0]

        # 1. Try API v3 album endpoint
        try:
            res = self.request("GET", f"/3/album/{clean_id}")
            if res.get("success") and "data" in res:
                return ImgurAlbum.from_api_dict(res["data"])
        except Exception as e:
            logger.debug("API v3 /3/album/%s failed: %s", clean_id, e)

        # 2. Try web post v1 albums endpoint
        params = {
            "client_id": self.client_id,
            "include": "media,tags,account",
        }
        res = self.request("GET", f"/post/v1/albums/{clean_id}", params=params)
        data = res.get("data", res)
        return ImgurAlbum.from_api_dict(data)

    def get_image(self, image_id: str) -> ImgurImage:
        """Fetch metadata for a single image."""
        clean_id = image_id.strip().split("/")[-1].split(".")[0]
        res = self.request("GET", f"/3/image/{clean_id}")
        data = res.get("data", {})
        return ImgurImage.from_api_dict(data)

    def get_account_albums(self, username: str = "me") -> Generator[ImgurAlbum, None, None]:
        """Fetch all albums belonging to the authenticated account or specified user."""
        seen_ids = set()

        # Method 1: API v3 /3/account/{username}/albums/{page}
        page = 0
        try:
            while True:
                res = self.request("GET", f"/3/account/{username}/albums/{page}")
                albums_data = res.get("data", [])
                if not albums_data:
                    break

                for a_dict in albums_data:
                    a_id = a_dict.get("id")
                    if a_id and a_id not in seen_ids:
                        seen_ids.add(a_id)
                        # Fetch full album details to ensure all images are populated
                        try:
                            full_album = self.get_album(a_id)
                            yield full_album
                        except Exception:
                            yield ImgurAlbum.from_api_dict(a_dict)

                page += 1
                if len(albums_data) < 50:
                    break
        except ImgurAuthError:
            # If not authorized for /3/account/me/albums, fallback to web endpoints
            logger.debug("Account albums endpoint requires higher authorization or cookies.")
        except Exception as e:
            logger.debug("API v3 account albums error: %s", e)

        # Method 2: Internal web endpoints /post/v1/accounts/me/all_posts and /post/v1/accounts/me/hidden_albums
        for endpoint in ["/post/v1/accounts/me/all_posts", "/post/v1/accounts/me/hidden_albums"]:
            web_page = 1
            while True:
                params = {
                    "client_id": self.client_id,
                    "include": "media,tags,account",
                    "page": web_page,
                    "sort": "-created_at",
                }
                try:
                    res = self.request("GET", endpoint, params=params)
                    items = res.get("data", res)
                    if not isinstance(items, list) or not items:
                        break

                    for item in items:
                        if isinstance(item, dict):
                            is_album = item.get("is_album", False) or "media" in item
                            a_id = item.get("id")
                            if is_album and a_id and a_id not in seen_ids:
                                seen_ids.add(a_id)
                                yield ImgurAlbum.from_api_dict(item)

                    web_page += 1
                except Exception as e:
                    logger.debug("Web endpoint %s error: %s", endpoint, e)
                    break

    def get_account_images(self, username: str = "me") -> Generator[ImgurImage, None, None]:
        """Fetch all images uploaded to the account."""
        page = 0
        try:
            while True:
                res = self.request("GET", f"/3/account/{username}/images/{page}")
                images_data = res.get("data", [])
                if not images_data:
                    break
                for img_dict in images_data:
                    yield ImgurImage.from_api_dict(img_dict)
                page += 1
                if len(images_data) < 50:
                    break
        except Exception as e:
            logger.debug("Failed fetching account images: %s", e)

    def download_image(
        self,
        url_or_id: str,
        dest_path: str | Path,
        buffer_size: int = 1024 * 1024,
    ) -> Path:
        """Download an image from Imgur to dest_path."""
        if url_or_id.startswith("http://") or url_or_id.startswith("https://"):
            url = url_or_id
        else:
            url = f"https://i.imgur.com/{url_or_id}.jpg"

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        resp = self.session.get(url, stream=True, timeout=self.timeout)
        resp.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=buffer_size):
                if chunk:
                    f.write(chunk)

        return dest
