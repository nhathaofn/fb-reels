import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ui.desktop_app import DesktopApp
from src.config import OUTPUT_DIR, VIDEOS_DIR, EXCEL_DIR, CAPTIONS_DIR


@pytest.fixture(scope="module")
def app():
    """Tạo duy nhất 1 phiên DesktopApp cho toàn bộ module test để tránh lỗi Tcl teardown trên Windows."""
    with patch("src.ui.desktop_app.load_profile_last_results", return_value=[]), \
         patch("src.ui.desktop_app.load_profile_settings", return_value={}), \
         patch("src.ui.components.sidebar.load_profile_settings", return_value={}), \
         patch("src.ui.components.sidebar.list_available_profiles", return_value=["default"]), \
         patch("src.ui.components.sidebar.has_logged_in_session", return_value=True):
        instance = DesktopApp()
        yield instance
        try:
            instance.destroy()
        except Exception:
            pass


def test_desktop_app_initialization(app):
    """Kiểm tra khởi tạo ứng dụng DesktopApp thành công."""
    assert app.sidebar is not None
    assert app.crawler_view is not None
    assert app.result_table is not None
    assert app.sidebar.get_selected_profile() == "default"
    assert app.stop_event is not None
    assert app.stop_event.is_set() is False


def test_desktop_app_stop_crawling(app):
    """Kiểm tra kích hoạt sự kiện dừng cào."""
    app.stop_crawling()
    assert app.stop_event.is_set() is True
    app.stop_event.clear()
    assert app.stop_event.is_set() is False


def test_desktop_app_clear_results(app):
    """Kiểm tra chức năng dọn dẹp kết quả cào trên UI."""
    with patch("src.ui.desktop_app.save_profile_last_results") as mock_save:
        app._on_clear_results()
        mock_save.assert_called_with("default", [])
        assert len(app.result_table.get_records()) == 0


def test_desktop_app_folder_settings(app):
    """Kiểm tra tải và lưu cấu hình thư mục dự án."""
    app.sidebar.project_dir_var.set("D:/custom/my_project")

    assert app.sidebar.project_dir_var.get() == "D:/custom/my_project"
    assert app.sidebar.get_project_dir() == Path("D:/custom/my_project")

    # Test reset to default
    app.sidebar._reset_project_folder()
    assert app.sidebar.project_dir_var.get() == str(OUTPUT_DIR)

    # Test get_settings includes the updated project_output_dir
    cfg = app.sidebar.get_settings()
    assert cfg["project_output_dir"] == str(OUTPUT_DIR)
    assert cfg["auto_save_captions"] is True


def test_desktop_app_crawler_worker_passes_caption_settings(tmp_path):
    """Kiểm tra worker tự động sinh cấu trúc {stt}_{id_profile} với 3 folder: video, caption, final."""
    with patch("src.ui.desktop_app.run_crawler_pipeline") as mock_pipeline:
        mock_pipeline.return_value = [{"stt": 1, "caption": "Cap 1", "caption_path": "caption_1.txt"}]
        mock_self = MagicMock()
        mock_self.stop_event.is_set.return_value = False

        settings = {
            "project_output_dir": str(tmp_path),
            "auto_save_captions": True,
            "max_reels": 5,
            "check_comments": True,
            "delay_min": 1.0,
            "delay_max": 2.0,
            "headless": True,
            "download_video": False,
            "crawl_order": "oldest"
        }
        channel_url = "https://www.facebook.com/profile.php?id=61593384835679"
        DesktopApp._run_crawler_worker(mock_self, "channel", channel_url, settings, "default")

        mock_pipeline.assert_called_once()
        _, kwargs = mock_pipeline.call_args

        expected_channel_dir = tmp_path / "1_61593384835679"
        assert expected_channel_dir.exists()
        assert Path(kwargs["video_output_dir"]) == expected_channel_dir / "video"
        assert Path(kwargs["caption_output_dir"]) == expected_channel_dir / "caption"
        assert (expected_channel_dir / "final").is_dir()
        assert kwargs["auto_save_captions"] is True


def test_desktop_app_capcut_render_options(app):
    """Kiểm tra cấu hình render CapCut Studio trên UI."""
    opts = app.crawler_view.get_render_options()
    assert "template_name" in opts
    assert "video_dir" in opts
    assert "zoom_ratio" in opts
    assert opts["zoom_ratio"] >= 1.0
    assert opts["filter_screams"] is True
    assert opts["enable_effects"] is True
    assert opts["enable_karaoke"] is True

    # Test set_rendering_state
    app.crawler_view.set_rendering_state(True)
    assert app.crawler_view.btn_start.cget("state") == "disabled"
    app.crawler_view.set_rendering_state(False)
    assert app.crawler_view.btn_start.cget("state") == "normal"


def test_desktop_app_sidebar_auto_render_template(app):
    """Kiểm tra cấu hình auto_render_template và template_name trên Sidebar."""
    app.sidebar.template_name_var.set("my_tpl")
    app.sidebar.auto_render_template_var.set(True)
    app.sidebar._on_auto_render_toggled()
    assert app.sidebar.download_video_var.get() is True

    cfg = app.sidebar.get_settings()
    assert cfg["auto_render_template"] is True
    assert cfg["render_template_name"] == "my_tpl"


def test_desktop_app_crawler_worker_triggers_auto_render(tmp_path):
    """Kiểm tra worker tự động kích hoạt render_reels_from_template qua luồng consumer khi auto_render_template=True."""
    dummy_vid = tmp_path / "1_test.mp4"
    dummy_vid.write_bytes(b"dummy")

    with patch("src.ui.desktop_app.run_crawler_pipeline") as mock_pipeline, \
         patch("src.ui.desktop_app.render_reels_from_template") as mock_render, \
         patch("src.ui.desktop_app.find_capcut_exe", return_value=None):
        
        def fake_pipeline(*args, **kwargs):
            on_item_ready = kwargs.get("on_item_ready")
            item = {"stt": 1, "video_path": str(dummy_vid), "caption": "Test Reel"}
            if on_item_ready:
                on_item_ready(item)
            return [item]

        mock_pipeline.side_effect = fake_pipeline
        mock_render.return_value = {
            "status": "success", "output_video": "Reel_1_test.mp4", "elapsed_sec": 1.0
        }

        mock_self = MagicMock()
        mock_self.stop_event.is_set.return_value = False
        mock_self.crawler_view.get_render_options.return_value = {
            "zoom_ratio": 1.15,
            "layout_mode": "crop_fill",
            "whisper_model": "tiny",
            "filter_screams": True,
            "enable_effects": True
        }

        settings = {
            "project_output_dir": str(tmp_path),
            "video_output_dir": str(tmp_path),
            "excel_output_dir": str(tmp_path),
            "caption_output_dir": str(tmp_path),
            "auto_save_captions": True,
            "auto_render_template": True,
            "render_template_name": "template-fb",
            "max_reels": 1,
            "check_comments": False,
            "delay_min": 1.0,
            "delay_max": 2.0,
            "headless": True,
            "download_video": True,
            "crawl_order": "oldest"
        }

        DesktopApp._run_crawler_worker(mock_self, "list", ["https://fb.com/reel/1"], settings, "default")

        mock_pipeline.assert_called_once()
        mock_render.assert_called_once()
        _, b_kwargs = mock_render.call_args
        assert b_kwargs["template_name"] == "template-fb"
        assert b_kwargs["zoom_ratio"] == 1.15
        assert b_kwargs["filter_screams"] is True
        assert b_kwargs["enable_noise"] is True


def test_result_table_in_place_update(app):
    """Kiểm tra add_or_update_record cập nhật dữ liệu hàng có sẵn thay vì nhân đôi hàng."""
    table = app.result_table
    table.clear_table()

    # Thêm lần đầu
    rec1 = {"stt": 1, "reel_url": "https://fb.com/reel/100", "caption": "Cap 1", "status": "Đang tải"}
    table.add_or_update_record(rec1)
    assert len(table.get_records()) == 1
    assert len(table.tree.get_children()) == 1

    # Cập nhật lần 2 khi render xong
    rec1_updated = {"stt": 1, "reel_url": "https://fb.com/reel/100", "caption": "Cap 1", "status": "Hoàn tất final", "video_path": "final.mp4"}
    table.add_or_update_record(rec1_updated)
    # Số hàng vẫn là 1, nhưng giá trị được cập nhật
    assert len(table.get_records()) == 1
    assert len(table.tree.get_children()) == 1
    item_id = table.tree.get_children()[0]
    vals = table.tree.item(item_id, "values")
    assert vals[7] == "Hoàn tất final"
    assert vals[6] == "final.mp4"


def test_desktop_app_producer_consumer_parallel_render(tmp_path):
    """Kiểm tra worker khởi chạy luồng render consumer song song, xử lý video ngay khi cào xong từng item."""
    dummy_vid = tmp_path / "1_test.mp4"
    dummy_vid.write_bytes(b"dummy")

    with patch("src.ui.desktop_app.run_crawler_pipeline") as mock_pipeline, \
         patch("src.ui.desktop_app.render_reels_from_template") as mock_render, \
         patch("src.ui.desktop_app.find_capcut_exe", return_value=Path("C:/dummy/CapCut.exe")), \
         patch("src.ui.desktop_app.CapCutExportSession") as mock_session_cls:

        mock_session_inst = MagicMock()
        mock_session_cls.return_value = mock_session_inst

        # Giả lập pipeline cào gọi callback on_item_ready ngay khi có video
        def fake_pipeline(*args, **kwargs):
            on_item_ready = kwargs.get("on_item_ready")
            item = {"stt": 1, "reel_id": "123", "reel_url": "https://fb.com/reel/123", "video_path": str(dummy_vid)}
            if on_item_ready:
                on_item_ready(item)
            return [item]

        mock_pipeline.side_effect = fake_pipeline
        mock_render.return_value = {
            "output_video": str(tmp_path / "final" / "out1.mp4"),
            "elapsed_sec": 1.5,
            "status": "success"
        }

        mock_self = MagicMock()
        mock_self.stop_event.is_set.return_value = False
        mock_self.crawler_view.get_render_options.return_value = {
            "zoom_ratio": 1.0,
            "layout_mode": "crop_fill",
            "whisper_model": "tiny",
            "filter_screams": True,
            "enable_effects": True
        }

        settings = {
            "project_output_dir": str(tmp_path),
            "auto_render_template": True,
            "render_template_name": "template-fb",
            "download_video": True,
            "max_reels": 1,
            "check_comments": False,
            "delay_min": 0.1,
            "delay_max": 0.2,
            "headless": True,
            "crawl_order": "oldest"
        }

        DesktopApp._run_crawler_worker(mock_self, "list", ["https://fb.com/reel/123"], settings, "default")

        # Xác nhận mock_render được gọi trực tiếp thông qua luồng consumer
        mock_render.assert_called_once()
        _, render_kwargs = mock_render.call_args
        assert render_kwargs["session"] == mock_session_inst


