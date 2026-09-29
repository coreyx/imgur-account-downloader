"""Tests for archive parsing and local zip indexing."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from imgur_downloader.archive import FILENAME_PATTERN, LocalArchive, find_local_archive


class TestArchive(unittest.TestCase):
    def test_filename_pattern_matching(self):
        test_cases = [
            ("1 - TzIN9Qm.png", 1, "TzIN9Qm", "png"),
            ("2, - BHY6CTE.png", 2, "BHY6CTE", "png"),
            ("2189 - wXPiGCU.gif", 2189, "wXPiGCU", "gif"),
            ("2195 - xhOLpie.jpg", 2195, "xhOLpie", "jpg"),
            ("005 - abc1234.mp4", 5, "abc1234", "mp4"),
            ("TzIN9Qm.jpg", None, "TzIN9Qm", "jpg"),
        ]

        for name, expected_idx, expected_id, expected_ext in test_cases:
            m = FILENAME_PATTERN.match(name)
            self.assertIsNotNone(m, f"Failed matching: {name}")
            idx = int(m.group("index")) if m.group("index") else None
            self.assertEqual(idx, expected_idx)
            self.assertEqual(m.group("id"), expected_id)
            self.assertEqual(m.group("ext").lower(), expected_ext)

    def test_local_archive_zip(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = Path(tf.name)

        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("1 - TzIN9Qm.png", b"fake_png_data_1")
                zf.writestr("2 - BHY6CTE.jpg", b"fake_jpg_data_2")

            with LocalArchive(zip_path) as archive:
                self.assertEqual(len(archive), 2)
                self.assertTrue(archive.contains("TzIN9Qm"))
                self.assertTrue(archive.contains("BHY6CTE"))
                self.assertFalse(archive.contains("nonexistent"))

                item = archive.get_item("TzIN9Qm")
                self.assertIsNotNone(item)
                self.assertEqual(item.index, 1)
                self.assertEqual(item.extension, "png")

                data = archive.read_bytes("TzIN9Qm")
                self.assertEqual(data, b"fake_png_data_1")

                with tempfile.TemporaryDirectory() as out_dir:
                    dest = Path(out_dir) / "extracted.png"
                    archive.extract_file("TzIN9Qm", dest)
                    self.assertTrue(dest.exists())
                    self.assertEqual(dest.read_bytes(), b"fake_png_data_1")
        finally:
            if zip_path.exists():
                zip_path.unlink()

    def test_find_local_archive(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            target_zip = tmp_path / "Imgur Account Download.zip"
            with zipfile.ZipFile(target_zip, "w") as zf:
                zf.writestr("1 - TzIN9Qm.png", b"test")

            found = find_local_archive(tmp_dir)
            self.assertIsNotNone(found)
            self.assertEqual(found.resolve(), target_zip.resolve())

    def test_find_local_archive_multiple_search_dirs(self):
        with tempfile.TemporaryDirectory() as empty_dir, tempfile.TemporaryDirectory() as target_dir:
            empty_path = Path(empty_dir)
            target_path = Path(target_dir)

            # Zip file with generic name containing valid Imgur pattern image
            target_zip = target_path / "custom_backup.zip"
            with zipfile.ZipFile(target_zip, "w") as zf:
                zf.writestr("1 - TzIN9Qm.png", b"test")

            # Searching list of directories
            found = find_local_archive([empty_path, target_path])
            self.assertIsNotNone(found)
            self.assertEqual(found.resolve(), target_zip.resolve())

    def test_local_archive_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            (dir_path / "1 - TzIN9Qm.png").write_bytes(b"data1")
            (dir_path / "2 - BHY6CTE.jpg").write_bytes(b"data2")

            with LocalArchive(dir_path) as archive:
                self.assertEqual(len(archive), 2)
                self.assertTrue(archive.contains("TzIN9Qm"))
                self.assertTrue(archive.contains("BHY6CTE"))
                self.assertEqual(archive.read_bytes("TzIN9Qm"), b"data1")


if __name__ == "__main__":
    unittest.main()
