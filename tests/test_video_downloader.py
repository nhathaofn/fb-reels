import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.video_downloader import download_reel_video, cookies_to_netscape_format

def test_cookies_to_netscape_format():
    cookies = [
        {"name": "c_user", "value": "12345", "domain": ".facebook.com", "path": "/"},
        {"name": "xs", "value": "abc999", "domain": ".facebook.com", "path": "/", "secure": True}
    ]
    txt = cookies_to_netscape_format(cookies)
    assert "# Netscape HTTP Cookie File" in txt
    assert "c_user" in txt
    assert "12345" in txt
    assert "xs" in txt

def test_download_reel_video_empty_url(tmp_path):
    success, path_str, msg = download_reel_video("", tmp_path)
    assert success is False
    assert path_str == ""
    assert "không hợp lệ" in msg

def test_download_reel_video_success_mock(tmp_path):
    with patch("src.core.video_downloader.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        dummy_file = tmp_path / "123456789.mp4"
        dummy_file.write_text("fake video data")

        mock_info = {
            "id": "123456789",
            "ext": "mp4",
            "title": "Mẫu Reel Test"
        }
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.prepare_filename.return_value = str(dummy_file)

        success, path_str, msg = download_reel_video(
            "https://www.facebook.com/reel/123456789",
            output_dir=tmp_path
        )

        assert success is True
        assert Path(path_str).exists()
        assert "Thành công" in msg

def test_download_reel_video_failure_mock(tmp_path):
    with patch("src.core.video_downloader.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = RuntimeError("Video private or unavailable")

        success, path_str, msg = download_reel_video(
            "https://www.facebook.com/reel/999999999",
            output_dir=tmp_path
        )

        assert success is False
        assert path_str == ""
        assert "Lỗi tải video" in msg


def test_download_reel_video_custom_filename_template(tmp_path):
    with patch("src.core.video_downloader.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        dummy_file = tmp_path / "1_123456789.mp4"
        dummy_file.write_text("fake video data")

        mock_info = {"id": "123456789", "ext": "mp4"}
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.prepare_filename.return_value = str(dummy_file)

        success, path_str, msg = download_reel_video(
            "https://www.facebook.com/reel/123456789",
            output_dir=tmp_path,
            filename_template="1_%(id)s.%(ext)s"
        )

        assert success is True
        assert Path(path_str).name == "1_123456789.mp4"

