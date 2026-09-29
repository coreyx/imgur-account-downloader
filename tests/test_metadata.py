"""Tests for metadata preservation, EXIF injection, and timestamps."""

import os
import tempfile
import unittest
from pathlib import Path
from PIL import Image

import piexif
from imgur_downloader.metadata import (
    apply_image_metadata,
    embed_jpeg_exif,
    format_exif_datetime,
    set_file_timestamps,
    write_album_metadata,
)
from imgur_downloader.models import ImgurAlbum, ImgurImage


class TestMetadata(unittest.TestCase):
    def test_format_exif_datetime(self):
        ts = 1379552694
        self.assertEqual(format_exif_datetime(ts), "2013:09:19 01:04:54")
        self.assertIsNone(format_exif_datetime(None))

    def test_set_file_timestamps(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            path = Path(tf.name)
        try:
            ts = 1379552694
            set_file_timestamps(path, ts)
            stat = os.stat(path)
            self.assertEqual(int(stat.st_mtime), ts)
        finally:
            if path.exists():
                path.unlink()

    def test_embed_jpeg_exif(self):
        img = Image.new("RGB", (100, 100), color="blue")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            img_path = Path(tf.name)
        try:
            img.save(img_path, "JPEG")

            meta = ImgurImage(
                id="test1234",
                title="Sample Title",
                description="Sample Description",
                datetime=1379552694,
                link="https://i.imgur.com/test1234.jpg",
                views=42,
                tags=["fun", "sample"],
            )

            ok = embed_jpeg_exif(img_path, meta)
            self.assertTrue(ok)

            exif_dict = piexif.load(str(img_path))
            desc = exif_dict["0th"].get(piexif.ImageIFD.ImageDescription)
            self.assertIn(b"Sample Title", desc)
            dt = exif_dict["Exif"].get(piexif.ExifIFD.DateTimeOriginal)
            self.assertEqual(dt, b"2013:09:19 01:04:54")
        finally:
            if img_path.exists():
                img_path.unlink()

    def test_write_album_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            alb_dir = Path(td)
            alb = ImgurAlbum(
                id="alb123",
                title="My Great Vacation",
                description="Trip photos",
                datetime=1379552694,
                views=1000,
                images=[
                    ImgurImage(
                        id="img001",
                        title="Beach Sunset",
                        datetime=1379552694,
                    )
                ],
            )

            meta_file = write_album_metadata(alb_dir, alb)
            self.assertTrue(meta_file.exists())

            readme_file = alb_dir / "README.md"
            self.assertTrue(readme_file.exists())
            content = readme_file.read_text(encoding="utf-8")
            self.assertIn("My Great Vacation", content)
            self.assertIn("Beach Sunset", content)


if __name__ == "__main__":
    unittest.main()
