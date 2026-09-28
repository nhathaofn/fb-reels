import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ui.desktop_app import DesktopApp


@patch("src.ui.desktop_app.load_profile_last_results", return_value=[])
@patch("src.ui.desktop_app.load_profile_settings", return_value={})
@patch("src.ui.components.sidebar.list_available_profiles", return_value=["default"])
@patch("src.ui.components.sidebar.has_logged_in_session", return_value=True)
def test_desktop_app_initialization(mock_has_session, mock_list_prof, mock_load_settings, mock_load_results):
    """Kiểm tra khởi tạo ứng dụng DesktopApp thành công."""
    app = DesktopApp()
    try:
        assert app.sidebar is not None
        assert app.crawler_view is not None
        assert app.result_table is not None
        assert app.sidebar.get_selected_profile() == "default"
        assert app.stop_event is not None
        assert app.stop_event.is_set() is False
    finally:
        app.destroy()


@patch("src.ui.desktop_app.load_profile_last_results", return_value=[])
@patch("src.ui.desktop_app.load_profile_settings", return_value={})
@patch("src.ui.components.sidebar.list_available_profiles", return_value=["default"])
@patch("src.ui.components.sidebar.has_logged_in_session", return_value=True)
def test_desktop_app_stop_crawling(mock_has_session, mock_list_prof, mock_load_settings, mock_load_results):
    """Kiểm tra kích hoạt sự kiện dừng cào."""
    app = DesktopApp()
    try:
        app.stop_crawling()
        assert app.stop_event.is_set() is True
    finally:
        app.destroy()


@patch("src.ui.desktop_app.save_profile_last_results")
@patch("src.ui.desktop_app.load_profile_last_results", return_value=[{"reel_url": "https://fb.com/reel/1"}])
@patch("src.ui.desktop_app.load_profile_settings", return_value={})
@patch("src.ui.components.sidebar.list_available_profiles", return_value=["default"])
@patch("src.ui.components.sidebar.has_logged_in_session", return_value=True)
def test_desktop_app_clear_results(mock_has_session, mock_list_prof, mock_load_settings, mock_load_results, mock_save_results):
    """Kiểm tra chức năng dọn dẹp kết quả cào trên UI."""
    app = DesktopApp()
    try:
        assert len(app.result_table.get_records()) == 1
        app._on_clear_results()
        mock_save_results.assert_called_with("default", [])
        app.result_table.clear_table()
        assert len(app.result_table.get_records()) == 0
    finally:
        app.destroy()


@patch("src.ui.components.sidebar.load_profile_settings", return_value={
    "video_output_dir": "D:/custom/videos",
    "excel_output_dir": "D:/custom/excel",
    "caption_output_dir": "D:/custom/captions"
})
@patch("src.ui.desktop_app.load_profile_last_results", return_value=[])
@patch("src.ui.desktop_app.load_profile_settings", return_value={
    "video_output_dir": "D:/custom/videos",
    "excel_output_dir": "D:/custom/excel",
    "caption_output_dir": "D:/custom/captions"
})
@patch("src.ui.components.sidebar.list_available_profiles", return_value=["default"])
@patch("src.ui.components.sidebar.has_logged_in_session", return_value=True)
def test_desktop_app_folder_settings(mock_has_session, mock_list_prof, mock_load_settings, mock_load_results, mock_sidebar_load_settings):
    """Kiểm tra tải và lưu cấu hình thư mục video, excel và caption."""
    app = DesktopApp()
    try:
        assert app.sidebar.video_dir_var.get() == "D:/custom/videos"
        assert app.sidebar.excel_dir_var.get() == "D:/custom/excel"
        assert app.sidebar.caption_dir_var.get() == "D:/custom/captions"

        # Test reset to default
        from src.config import VIDEOS_DIR, EXCEL_DIR, CAPTIONS_DIR
        app.sidebar._reset_videos_folder()
        assert app.sidebar.video_dir_var.get() == str(VIDEOS_DIR)
        app.sidebar._reset_excel_folder()
        assert app.sidebar.excel_dir_var.get() == str(EXCEL_DIR)
        app.sidebar._reset_caption_folder()
        assert app.sidebar.caption_dir_var.get() == str(CAPTIONS_DIR)

        # Test get_settings includes the updated folders
        cfg = app.sidebar.get_settings()
        assert cfg["video_output_dir"] == str(VIDEOS_DIR)
        assert cfg["excel_output_dir"] == str(EXCEL_DIR)
        assert cfg["caption_output_dir"] == str(CAPTIONS_DIR)
        assert cfg["auto_save_captions"] is True
    finally:
        app.destroy()


def test_desktop_app_crawler_worker_passes_caption_settings():
    """Kiểm tra worker truyền đúng caption_output_dir và auto_save_captions vào pipeline để xuất caption tự động."""
    with patch("src.ui.desktop_app.run_crawler_pipeline") as mock_pipeline:
        mock_pipeline.return_value = [{"stt": 1, "caption": "Cap 1", "caption_path": "D:/captions/caption_1.txt"}]
        mock_self = MagicMock()
        mock_self.stop_event.is_set.return_value = False

        settings = {
            "video_output_dir": "D:/videos",
            "excel_output_dir": "D:/excel",
            "caption_output_dir": "D:/captions",
            "auto_save_captions": True,
            "max_reels": 5,
            "check_comments": True,
            "delay_min": 1.0,
            "delay_max": 2.0,
            "headless": True,
            "download_video": False,
            "crawl_order": "oldest"
        }
        DesktopApp._run_crawler_worker(mock_self, "list", ["https://fb.com/reel/1"], settings, "default")

        mock_pipeline.assert_called_once()
        _, kwargs = mock_pipeline.call_args
        assert kwargs["caption_output_dir"] == "D:/captions"
        assert kwargs["auto_save_captions"] is True





