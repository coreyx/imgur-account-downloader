"""Tests for ImgurClient authentication configuration and model parsing."""

import unittest
from unittest.mock import MagicMock, patch

from imgur_downloader.client import DEFAULT_CLIENT_ID, ImgurClient
from imgur_downloader.models import ImgurAlbum, ImgurImage


class TestClient(unittest.TestCase):
    def test_default_client_id(self):
        client = ImgurClient()
        self.assertEqual(client.client_id, DEFAULT_CLIENT_ID)
        self.assertEqual(
            client.session.headers.get("Authorization"),
            f"Client-ID {DEFAULT_CLIENT_ID}",
        )

    def test_bearer_token_auth(self):
        client = ImgurClient(access_token="test_bearer_12345")
        self.assertEqual(
            client.session.headers.get("Authorization"),
            "Bearer test_bearer_12345",
        )

    def test_cookie_auth(self):
        client = ImgurClient(cookie="test_cookie_value_xyz")
        cookie_val = client.session.cookies.get("accesstoken", domain=".imgur.com")
        self.assertEqual(cookie_val, "test_cookie_value_xyz")
        self.assertEqual(
            client.session.headers.get("Authorization"),
            "Bearer test_cookie_value_xyz",
        )

    def test_model_from_api_dict(self):
        sample_api_album = {
            "id": "albTest",
            "title": "Vacation 2023",
            "description": "Family trip",
            "datetime": 1680000000,
            "views": 150,
            "images_count": 1,
            "images": [
                {
                    "id": "img123",
                    "title": "First Picture",
                    "description": "At the airport",
                    "datetime": 1680000050,
                    "type": "image/jpeg",
                    "width": 1920,
                    "height": 1080,
                    "size": 204800,
                    "views": 45,
                    "link": "https://i.imgur.com/img123.jpg",
                }
            ],
        }

        album = ImgurAlbum.from_api_dict(sample_api_album)
        self.assertEqual(album.id, "albTest")
        self.assertEqual(album.title, "Vacation 2023")
        self.assertEqual(album.datetime, 1680000000)
        self.assertEqual(len(album.images), 1)

        img = album.images[0]
        self.assertEqual(img.id, "img123")
        self.assertEqual(img.title, "First Picture")
        self.assertEqual(img.width, 1920)
        self.assertEqual(img.height, 1080)
        self.assertEqual(img.order, 1)
        self.assertEqual(img.album_ids, ["albTest"])


if __name__ == "__main__":
    unittest.main()
