import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image

from imgur_downloader.archive import LocalArchive
from imgur_downloader.models import ImgurAlbum, ImgurImage
from imgur_downloader.organizer import ArchiveOrganizer, sanitize_filename


def _make_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (50, 50), color="blue")
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


class TestOrganizer(unittest.TestCase):
    def test_sanitize_filename(self):
        self.assertEqual(
            sanitize_filename('Invalid: <File> "Name"?'),
            "Invalid_ _File_ _Name__",
        )
        self.assertEqual(sanitize_filename("CON"), "_CON")
        self.assertEqual(sanitize_filename("PRN.txt"), "_PRN.txt")
        self.assertEqual(sanitize_filename("  test  "), "test")
        self.assertEqual(sanitize_filename("a" * 300), "a" * 180)

    def test_is_album_ignored(self):
        organizer = ArchiveOrganizer(
            output_dir="dummy",
            ignore_albums=["secret_id", "Memes*", "*Trip*", "exact title"],
        )

        # Match by ID
        self.assertTrue(organizer.is_album_ignored(ImgurAlbum(id="secret_id", title="Public")))
        self.assertTrue(organizer.is_album_ignored(ImgurAlbum(id="SECRET_ID", title="Public")))

        # Match by wildcard title
        self.assertTrue(organizer.is_album_ignored(ImgurAlbum(id="abc1", title="Memes 2024")))
        self.assertTrue(organizer.is_album_ignored(ImgurAlbum(id="abc2", title="memes galore")))
        self.assertTrue(organizer.is_album_ignored(ImgurAlbum(id="abc3", title="Our Summer Trip")))

        # Match by exact title
        self.assertTrue(organizer.is_album_ignored(ImgurAlbum(id="abc4", title="exact title")))
        self.assertTrue(organizer.is_album_ignored(ImgurAlbum(id="abc5", title="EXACT TITLE")))

        # Match untitled albums by ID, display title, wildcard, or bracket format
        untitled_album = ImgurAlbum(id="unt1234", title=None)
        self.assertEqual(untitled_album.display_title, "Untitled Album (unt1234)")

        org_by_id = ArchiveOrganizer(output_dir="dummy", ignore_albums=["unt1234"])
        self.assertTrue(org_by_id.is_album_ignored(untitled_album))

        org_by_display = ArchiveOrganizer(output_dir="dummy", ignore_albums=["Untitled Album (unt1234)"])
        self.assertTrue(org_by_display.is_album_ignored(untitled_album))

        org_by_wildcard = ArchiveOrganizer(output_dir="dummy", ignore_albums=["Untitled Album*"])
        self.assertTrue(org_by_wildcard.is_album_ignored(untitled_album))

        org_by_bracket = ArchiveOrganizer(output_dir="dummy", ignore_albums=["[unt1234]"])
        self.assertTrue(org_by_bracket.is_album_ignored(untitled_album))

        # Negative matches
        self.assertFalse(organizer.is_album_ignored(ImgurAlbum(id="other_id", title="Vacation")))
        self.assertFalse(organizer.is_album_ignored(ImgurAlbum(id="xyz", title=None)))

    def test_organizer_workflow_with_catch_all(self):
        with tempfile.TemporaryDirectory() as td:
            base_path = Path(td)
            zip_path = base_path / "test_account.zip"
            output_dir = base_path / "organized_output"
            img_bytes = _make_jpeg_bytes()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("1 - inAlbum01.jpg", img_bytes)
                zf.writestr("2 - notInAlbum.jpg", img_bytes)

            album = ImgurAlbum(
                id="testAlbum1",
                title="Summer Trip",
                datetime=1379552694,
                images=[
                    ImgurImage(
                        id="inAlbum01",
                        title="At The Lake",
                        datetime=1379552694,
                    )
                ],
            )

            with LocalArchive(zip_path) as archive:
                organizer = ArchiveOrganizer(
                    output_dir=output_dir,
                    archive=archive,
                    embed_exif=True,
                    set_timestamps=True,
                    enable_catch_all=True,
                )
                stats = organizer.organize([album])

            self.assertEqual(stats["albums_processed"], 1)
            self.assertEqual(stats["images_extracted_from_archive"], 2)
            self.assertEqual(stats["catch_all_images"], 1)
            self.assertEqual(stats["uncategorized_images"], 1)

            # Check album directory and gallery exist
            album_folder = output_dir / "Summer Trip [testAlbum1]"
            self.assertTrue(album_folder.exists())
            self.assertTrue((album_folder / "album_metadata.json").exists())
            self.assertTrue((album_folder / "gallery.html").exists())
            self.assertTrue((album_folder / "001 - inAlbum01 - At The Lake.jpg").exists())

            album_gallery_html = (album_folder / "gallery.html").read_text(encoding="utf-8")
            self.assertIn("Summer Trip", album_gallery_html)
            self.assertIn("001 - inAlbum01 - At The Lake.jpg", album_gallery_html)
            self.assertIn('onclick="openLightbox(0)"', album_gallery_html)
            self.assertIn('class="media-thumb-wrap', album_gallery_html)

            # Check catch-all album directory, metadata, and gallery exist
            catch_all_folder = output_dir / "Non-Album Images [_uncategorized]"
            self.assertTrue(catch_all_folder.exists())
            self.assertTrue((catch_all_folder / "album_metadata.json").exists())
            self.assertTrue((catch_all_folder / "README.md").exists())
            self.assertTrue((catch_all_folder / "gallery.html").exists())
            self.assertTrue((catch_all_folder / "2 - notInAlbum.jpg").exists())

            catch_all_html = (catch_all_folder / "gallery.html").read_text(encoding="utf-8")
            self.assertIn("Non-Album Images", catch_all_html)
            self.assertIn("2 - notInAlbum.jpg", catch_all_html)

            # Check root catalog files
            self.assertTrue((output_dir / "catalog.html").exists())
            root_catalog = (output_dir / "catalog.html").read_text(encoding="utf-8")
            self.assertIn("Gallery", root_catalog)
            self.assertIn("Open Folder", root_catalog)
            self.assertIn("Non-Album Images", root_catalog)
            self.assertTrue((output_dir / "README.md").exists())
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_organizer_ignore_albums_with_exclude(self):
        with tempfile.TemporaryDirectory() as td:
            base_path = Path(td)
            zip_path = base_path / "test_account.zip"
            output_dir = base_path / "curated_output"
            img_bytes = _make_jpeg_bytes()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("1 - keep01.jpg", img_bytes)
                zf.writestr("2 - skip01.jpg", img_bytes)
                zf.writestr("3 - uncat01.jpg", img_bytes)

            album_keep = ImgurAlbum(
                id="albKeep",
                title="Portfolio",
                images=[ImgurImage(id="keep01")],
            )
            album_skip = ImgurAlbum(
                id="albSkip",
                title="Random Memes",
                images=[ImgurImage(id="skip01")],
            )

            with LocalArchive(zip_path) as archive:
                organizer = ArchiveOrganizer(
                    output_dir=output_dir,
                    archive=archive,
                    ignore_albums=["Random Memes"],
                    exclude_ignored_images=True,
                    enable_catch_all=True,
                )
                stats = organizer.organize([album_keep, album_skip])

            self.assertEqual(stats["albums_processed"], 1)
            self.assertEqual(stats["albums_ignored"], 1)
            self.assertEqual(stats["images_extracted_from_archive"], 2)  # keep01 and uncat01
            self.assertEqual(stats["catch_all_images"], 1)

            # Portfolio album exists
            self.assertTrue((output_dir / "Portfolio [albKeep]").exists())

            # Skipped album does NOT exist
            self.assertFalse((output_dir / "Random Memes [albSkip]").exists())

            # Catch-all exists and contains ONLY uncat01, NOT skip01
            catch_all = output_dir / "Non-Album Images [_uncategorized]"
            self.assertTrue(catch_all.exists())
            self.assertTrue((catch_all / "3 - uncat01.jpg").exists())
            self.assertFalse((catch_all / "2 - skip01.jpg").exists())

    def test_organizer_ignore_albums_without_exclude(self):
        with tempfile.TemporaryDirectory() as td:
            base_path = Path(td)
            zip_path = base_path / "test_account.zip"
            output_dir = base_path / "curated_output"
            img_bytes = _make_jpeg_bytes()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("1 - keep01.jpg", img_bytes)
                zf.writestr("2 - skip01.jpg", img_bytes)
                zf.writestr("3 - uncat01.jpg", img_bytes)

            album_keep = ImgurAlbum(
                id="albKeep",
                title="Portfolio",
                images=[ImgurImage(id="keep01")],
            )
            album_skip = ImgurAlbum(
                id="albSkip",
                title="Random Memes",
                images=[ImgurImage(id="skip01")],
            )

            with LocalArchive(zip_path) as archive:
                organizer = ArchiveOrganizer(
                    output_dir=output_dir,
                    archive=archive,
                    ignore_albums=["albSkip"],  # Match by ID
                    exclude_ignored_images=False,  # Skipped images fall into catch-all
                    enable_catch_all=True,
                )
                stats = organizer.organize([album_keep, album_skip])

            self.assertEqual(stats["albums_processed"], 1)
            self.assertEqual(stats["albums_ignored"], 1)
            self.assertEqual(stats["catch_all_images"], 2)  # skip01 + uncat01

            # Catch-all contains both skip01 and uncat01
            catch_all = output_dir / "Non-Album Images [_uncategorized]"
            self.assertTrue(catch_all.exists())
            self.assertTrue((catch_all / "2 - skip01.jpg").exists())
            self.assertTrue((catch_all / "3 - uncat01.jpg").exists())

    def test_organizer_disable_catch_all(self):
        with tempfile.TemporaryDirectory() as td:
            base_path = Path(td)
            zip_path = base_path / "test_account.zip"
            output_dir = base_path / "output_no_catch_all"
            img_bytes = _make_jpeg_bytes()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("1 - inAlbum01.jpg", img_bytes)
                zf.writestr("2 - notInAlbum.jpg", img_bytes)

            album = ImgurAlbum(
                id="testAlbum1",
                title="Work",
                images=[ImgurImage(id="inAlbum01")],
            )

            with LocalArchive(zip_path) as archive:
                organizer = ArchiveOrganizer(
                    output_dir=output_dir,
                    archive=archive,
                    enable_catch_all=False,
                )
                stats = organizer.organize([album])

            self.assertEqual(stats["albums_processed"], 1)
            self.assertEqual(stats["catch_all_images"], 0)
            self.assertFalse((output_dir / "Non-Album Images [_uncategorized]").exists())

    def test_organizer_leave_out_non_album_images(self):
        with tempfile.TemporaryDirectory() as td:
            base_path = Path(td)
            zip_path = base_path / "test_account.zip"
            output_dir = base_path / "output_omitted_non_album"
            img_bytes = _make_jpeg_bytes()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("1 - inAlbum01.jpg", img_bytes)
                zf.writestr("2 - notInAlbum.jpg", img_bytes)

            album = ImgurAlbum(
                id="testAlbum1",
                title="Work",
                images=[ImgurImage(id="inAlbum01")],
            )

            with LocalArchive(zip_path) as archive:
                organizer = ArchiveOrganizer(
                    output_dir=output_dir,
                    archive=archive,
                    enable_catch_all=True,  # Even if enable_catch_all is True...
                    leave_out_non_album_images=True,  # ...this omits non-album images
                )
                stats = organizer.organize([album])

            self.assertEqual(stats["albums_processed"], 1)
            self.assertEqual(stats["catch_all_images"], 0)
            self.assertEqual(stats["non_album_images_omitted"], 1)
            self.assertEqual(stats["images_extracted_from_archive"], 1)

            # Album directory exists
            self.assertTrue((output_dir / "Work [testAlbum1]").exists())
            self.assertTrue((output_dir / "Work [testAlbum1]" / "001 - inAlbum01.jpg").exists())

            # Catch-all directory does NOT exist
            self.assertFalse((output_dir / "Non-Album Images [_uncategorized]").exists())

            # Catalog does not list non-album images
            catalog_html = (output_dir / "catalog.html").read_text(encoding="utf-8")
            self.assertNotIn("Non-Album Images", catalog_html)
            self.assertIn("Work", catalog_html)


if __name__ == "__main__":
    unittest.main()

