"""Data models for Imgur albums, images, and archive structures."""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def timestamp_to_iso(ts: Optional[int]) -> Optional[str]:
    """Convert a Unix epoch timestamp to an ISO 8601 string in UTC."""
    if ts is None:
        return None
    try:
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        return dt.isoformat()
    except (ValueError, OSError, OverflowError):
        return None


@dataclass
class ImgurImage:
    """Represents an Imgur image or video item with full metadata."""

    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    datetime: Optional[int] = None
    datetime_iso: Optional[str] = None
    type: Optional[str] = None
    animated: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    size: Optional[int] = None
    views: Optional[int] = None
    bandwidth: Optional[int] = None
    link: Optional[str] = None
    mp4: Optional[str] = None
    gifv: Optional[str] = None
    hls: Optional[str] = None
    deletehash: Optional[str] = None
    favorite: bool = False
    nsfw: Optional[bool] = None
    section: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    order: Optional[int] = None
    original_archive_name: Optional[str] = None
    original_archive_index: Optional[int] = None
    album_ids: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_dict(
        cls,
        data: Dict[str, Any],
        order: Optional[int] = None,
        album_id: Optional[str] = None,
    ) -> ImgurImage:
        """Create an ImgurImage instance from Imgur API v3 or web JSON dict."""
        img_id = data.get("id") or ""
        ts = data.get("datetime")
        # Handle string or float timestamps or created_at string
        if isinstance(ts, (int, float)):
            ts = int(ts)
        elif isinstance(data.get("created_at"), str):
            try:
                # ISO format like "2021-04-01T12:00:00Z"
                dt = datetime.datetime.fromisoformat(
                    data["created_at"].replace("Z", "+00:00")
                )
                ts = int(dt.timestamp())
            except Exception:
                ts = None

        tags_raw = data.get("tags") or []
        tags = [
            t.get("name") if isinstance(t, dict) else str(t)
            for t in tags_raw
            if t
        ]

        albums = [album_id] if album_id else []

        return cls(
            id=img_id,
            title=data.get("title") or None,
            description=data.get("description") or None,
            datetime=ts,
            datetime_iso=timestamp_to_iso(ts),
            type=data.get("type") or data.get("mime_type"),
            animated=bool(data.get("animated", False)),
            width=data.get("width"),
            height=data.get("height"),
            size=data.get("size"),
            views=data.get("views"),
            bandwidth=data.get("bandwidth"),
            link=data.get("link") or data.get("url"),
            mp4=data.get("mp4"),
            gifv=data.get("gifv"),
            hls=data.get("hls"),
            deletehash=data.get("deletehash"),
            favorite=bool(data.get("favorite", False)),
            nsfw=data.get("nsfw"),
            section=data.get("section"),
            tags=tags,
            order=order,
            album_ids=albums,
            raw_data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a clean dictionary representation excluding large raw blobs."""
        d = asdict(self)
        d.pop("raw_data", None)
        return d


@dataclass
class ImgurAlbum:
    """Represents an Imgur album with metadata and its list of images."""

    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    datetime: Optional[int] = None
    datetime_iso: Optional[str] = None
    cover: Optional[str] = None
    cover_width: Optional[int] = None
    cover_height: Optional[int] = None
    account_url: Optional[str] = None
    privacy: Optional[str] = None
    layout: Optional[str] = None
    views: Optional[int] = None
    link: Optional[str] = None
    images_count: Optional[int] = None
    deletehash: Optional[str] = None
    favorite: bool = False
    nsfw: Optional[bool] = None
    section: Optional[str] = None
    images: List[ImgurImage] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_title(self) -> str:
        """Return a displayable title, falling back to Untitled Album if empty."""
        title = (self.title or "").strip()
        return title if title else f"Untitled Album ({self.id})"

    @classmethod
    def from_api_dict(cls, data: Dict[str, Any]) -> ImgurAlbum:
        """Create an ImgurAlbum instance from Imgur API v3 or web JSON dict."""
        album_id = data.get("id") or ""
        ts = data.get("datetime")
        if isinstance(ts, (int, float)):
            ts = int(ts)
        elif isinstance(data.get("created_at"), str):
            try:
                dt = datetime.datetime.fromisoformat(
                    data["created_at"].replace("Z", "+00:00")
                )
                ts = int(dt.timestamp())
            except Exception:
                ts = None

        images: List[ImgurImage] = []
        raw_images = data.get("images") or data.get("media") or []
        for idx, img_dict in enumerate(raw_images, start=1):
            if isinstance(img_dict, dict):
                img_obj = ImgurImage.from_api_dict(
                    img_dict, order=idx, album_id=album_id
                )
                images.append(img_obj)

        img_count = data.get("images_count")
        if img_count is None and images:
            img_count = len(images)

        link = data.get("link")
        if not link and album_id:
            link = f"https://imgur.com/a/{album_id}"

        return cls(
            id=album_id,
            title=data.get("title") or None,
            description=data.get("description") or None,
            datetime=ts,
            datetime_iso=timestamp_to_iso(ts),
            cover=data.get("cover"),
            cover_width=data.get("cover_width"),
            cover_height=data.get("cover_height"),
            account_url=data.get("account_url"),
            privacy=data.get("privacy"),
            layout=data.get("layout"),
            views=data.get("views"),
            link=link,
            images_count=img_count,
            deletehash=data.get("deletehash"),
            favorite=bool(data.get("favorite", False)),
            nsfw=data.get("nsfw"),
            section=data.get("section"),
            images=images,
            raw_data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a clean dictionary representation with images."""
        d = asdict(self)
        d.pop("raw_data", None)
        d["images"] = [img.to_dict() for img in self.images]
        return d
