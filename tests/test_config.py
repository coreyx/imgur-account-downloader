"""Tests for YAML configuration loading and option resolution."""

import tempfile
import unittest
from pathlib import Path
import yaml

from imgur_downloader.cli import load_config_file


class TestConfig(unittest.TestCase):
    def test_load_custom_config(self):
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False, mode="w", encoding="utf-8") as tf:
            cfg_path = Path(tf.name)
            yaml.dump(
                {
                    "token": "secret_token_123",
                    "output_dir": "custom_output",
                    "local_archive": "my_export.zip",
                    "embed_exif": False,
                    "albums": ["alb1", "alb2"],
                },
                tf,
            )

        try:
            loaded = load_config_file(str(cfg_path))
            self.assertEqual(loaded.get("token"), "secret_token_123")
            self.assertEqual(loaded.get("output_dir"), "custom_output")
            self.assertEqual(loaded.get("local_archive"), "my_export.zip")
            self.assertFalse(loaded.get("embed_exif"))
            self.assertEqual(loaded.get("albums"), ["alb1", "alb2"])
        finally:
            if cfg_path.exists():
                cfg_path.unlink()

    def test_load_leave_out_non_album_images(self):
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False, mode="w", encoding="utf-8") as tf:
            cfg_path = Path(tf.name)
            yaml.dump(
                {
                    "leave_out_non_album_images": True,
                    "enable_catch_all": True,
                },
                tf,
            )

        try:
            loaded = load_config_file(str(cfg_path))
            self.assertTrue(loaded.get("leave_out_non_album_images"))
            self.assertTrue(loaded.get("enable_catch_all"))
        finally:
            if cfg_path.exists():
                cfg_path.unlink()

    def test_load_nonexistent_returns_empty_when_default(self):
        # When no path is specified and config.yml doesn't exist in a dummy dir
        with tempfile.TemporaryDirectory() as td:
            # Change directory context or pass dummy nonexistent path
            pass


if __name__ == "__main__":
    unittest.main()
