import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch
import pytest

from src.core.capcut_exporter import (
    find_capcut_exe,
    reposition_window_bottom_right,
    scan_for_new_mp4,
)


def test_find_capcut_exe():
    """Kiểm tra tìm kiếm đường dẫn CapCut.exe trên hệ thống thực tế."""
    exe = find_capcut_exe()
    assert exe is not None
    assert exe.exists()
    assert exe.name.lower() == "capcut.exe"


def test_reposition_window_bottom_right_mock():
    """Kiểm tra logic định vị cửa sổ xuống góc dưới màn hình."""
    with patch("win32api.GetSystemMetrics", side_effect=[1920, 1080]):
        with patch("win32gui.SetWindowPos") as mock_set_pos:
            res = reposition_window_bottom_right(12345, width=500, height=350)
            assert res is True
            # Kiểm tra tọa độ tính toán (1920 - 500 - 20 = 1400, 1080 - 350 - 60 = 670)
            mock_set_pos.assert_called_once()
            args = mock_set_pos.call_args[0]
            assert args[0] == 12345
            assert args[2] == 1400  # target_x
            assert args[3] == 670   # target_y
            assert args[4] == 500   # width
            assert args[5] == 350   # height


def test_scan_for_new_mp4(tmp_path):
    """Kiểm tra quét file video mp4 xuất mới."""
    start_t = 1000.0
    f1 = tmp_path / "old.mp4"
    f1.write_bytes(b"0" * 2000)
    os.utime(f1, (900.0, 900.0))

    f2 = tmp_path / "new_video.mp4"
    f2.write_bytes(b"1" * 2000)
    os.utime(f2, (1005.0, 1005.0))

    found = scan_for_new_mp4(start_t, "test_proj", search_dirs=[tmp_path])
    assert found is not None
    assert found.name == "new_video.mp4"


def test_capcut_export_session_lifecycle(tmp_path):
    """Kiểm tra vòng đời của CapCutExportSession: khởi động 1 lần, xuất nhiều project và đóng về Home."""
    from src.core.capcut_exporter import CapCutExportSession

    fake_exe = tmp_path / "CapCut.exe"
    fake_exe.write_bytes(b"dummy_exe")
    
    with patch("src.core.capcut_exporter.find_capcut_exe", return_value=fake_exe), \
         patch("subprocess.Popen") as mock_popen, \
         patch("src.core.capcut_exporter.get_capcut_window") as mock_get_win, \
         patch("src.core.capcut_exporter.make_window_invisible_and_offscreen") as mock_hide, \
         patch("src.core.capcut_exporter.micro_click_card", return_value=True), \
         patch("src.core.capcut_exporter.send_export_shortcut", return_value=True), \
         patch("src.core.capcut_exporter.confirm_export", return_value=True), \
         patch("src.core.capcut_exporter.scan_for_new_mp4") as mock_scan, \
         patch("src.core.capcut_exporter.kill_capcut_process") as mock_kill, \
         patch("win32gui.PostMessage") as mock_post_msg, \
         patch("win32gui.IsWindow", return_value=True):

        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        # Mock windows: home=1001, editor=2002, then home=1001
        mock_get_win.side_effect = [1001, 2002, 1001]

        dummy_exported = tmp_path / "exported.mp4"
        dummy_exported.write_bytes(b"x" * 6000)
        mock_scan.return_value = dummy_exported

        target_out = tmp_path / "final" / "out1.mp4"

        session = CapCutExportSession()
        session.start()
        assert session.is_alive() is True
        assert session.home_hwnd == 1001

        # Xuất project 1
        res1 = session.export_project("Project_1", str(target_out), timeout_sec=5)
        assert Path(res1).exists()
        # Xác nhận đã đóng editor bằng WM_CLOSE để trở về Home, không kill process
        mock_kill.assert_not_called()

        # Đóng session cuối cùng
        session.close()
        mock_kill.assert_called_once_with(pid=9999)

