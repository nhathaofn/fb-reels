"""Module tự động hóa xuất video CapCut PC (CapCut Auto-Exporter).

Cơ chế hoạt động:
1. Mở CapCut PC và tự động thu nhỏ cửa sổ xuống góc dưới bên phải màn hình (không choán màn hình).
2. Tự động kích hoạt mở dự án vừa clone và gửi phím tắt (Ctrl + E, Enter) để xuất video.
3. KHÔNG chiếm chuột: Tự động lưu và khôi phục vị trí chuột trong mili-giây hoặc gửi tín hiệu ngầm.
4. Giám sát tiến trình render của CapCut (thường từ 8 - 15 giây).
5. Khi render xong, tự động di chuyển file thành phẩm vào thư mục final/ và đóng CapCut PC ngay lập tức.
"""

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import win32api
import win32con
import win32gui
import win32process

from src.utils.logger import logger

KNOWN_CAPCUT_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "Apps" / "CapCut.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "CapCut" / "CapCut.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "CapCut" / "CapCut.exe",
]


def find_capcut_exe() -> Optional[Path]:
    """Tìm đường dẫn file thực thi CapCut.exe trên hệ thống (ưu tiên bản cài mới nhất)."""
    # 1. Quét trong thư mục con Apps theo phiên bản mới nhất trước
    apps_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "Apps"
    if apps_dir.exists():
        version_dirs = []
        for sub in apps_dir.iterdir():
            if sub.is_dir() and (sub / "CapCut.exe").exists():
                version_dirs.append(sub)
        if version_dirs:
            version_dirs.sort(key=lambda d: d.name, reverse=True)
            return version_dirs[0] / "CapCut.exe"

    # 2. Tìm trong các đường dẫn mặc định
    for p in KNOWN_CAPCUT_PATHS:
        if p.exists() and p.is_file():
            return p

    return None


def force_foreground_window(hwnd: int) -> bool:
    """Đưa cửa sổ lên tiền cảnh (foreground) an toàn tuyệt đối, vượt qua giới hạn của Windows."""
    try:
        if not win32gui.IsWindow(hwnd):
            return False
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        cur_thread = win32api.GetCurrentThreadId()
        tgt_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
        if cur_thread != tgt_thread:
            try:
                win32process.AttachThreadInput(cur_thread, tgt_thread, True)
            except Exception:
                pass
        win32gui.SetForegroundWindow(hwnd)
        if cur_thread != tgt_thread:
            try:
                win32process.AttachThreadInput(cur_thread, tgt_thread, False)
            except Exception:
                pass
        return True
    except Exception:
        try:
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False


def get_capcut_window(
    timeout_sec: float = 12.0,
    require_editor: bool = False,
    draft_name: Optional[str] = None
) -> Optional[int]:
    """Tìm HWND của cửa sổ CapCut (Home hoặc Editor) an toàn tuyệt đối."""
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        found_hwnd = None

        def enum_cb(h, _):
            nonlocal found_hwnd
            try:
                if not win32gui.IsWindow(h) or not win32gui.IsWindowVisible(h):
                    return True
                txt = win32gui.GetWindowText(h)
                cls = win32gui.GetClassName(h)
                
                # Bỏ qua tooltip/cửa sổ con kích thước quá nhỏ
                rect = win32gui.GetWindowRect(h)
                w = rect[2] - rect[0]
                h_sz = rect[3] - rect[1]
                if w < 400 or h_sz < 250:
                    return True

                is_capcut = ("capcut" in txt.lower() or "jianying" in txt.lower() or 
                             "homepage" in cls.lower() or "mainwindow" in cls.lower() or "qt" in cls.lower())

                if not is_capcut:
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(h)
                        import psutil
                        proc = psutil.Process(pid)
                        if "capcut" in proc.name().lower() or "jianying" in proc.name().lower():
                            is_capcut = True
                    except Exception:
                        pass

                if is_capcut:
                    if require_editor:
                        # Editor: tiêu đề chứa tên dự án hoặc khác "CapCut"
                        if draft_name and draft_name.lower() in txt.lower():
                            found_hwnd = h
                            return False
                        if " - " in txt or (txt.strip() != "CapCut" and len(txt.strip()) > 4):
                            found_hwnd = h
                            return False
                        if "mainwindow" in cls.lower():
                            found_hwnd = h
                            return False
                    else:
                        # Home: tiêu đề chính xác là "CapCut" hoặc class chứa HomePage
                        if txt.strip() == "CapCut" or "homepage" in cls.lower():
                            found_hwnd = h
                            return False
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass

        if found_hwnd:
            return found_hwnd
        time.sleep(0.5)

    return None


def reposition_window_bottom_right(hwnd: int, width: int = 1168, height: int = 648) -> bool:
    """Định vị cửa sổ về kích thước tiêu chuẩn để giao diện CapCut không bị co cụm vỡ layout thẻ dự án."""
    try:
        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        
        target_x = max(0, screen_w - width - 20)
        target_y = max(0, screen_h - height - 60)

        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_NOTOPMOST,
            target_x,
            target_y,
            width,
            height,
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
        )
        return True
    except Exception as e:
        logger.warning(f"Không thể định vị cửa sổ CapCut: {e}")
        return False


def make_window_invisible_and_offscreen(hwnd: int) -> bool:
    """Đưa cửa sổ CapCut về vị trí chuẩn an toàn (giữ kích thước hợp lệ trên desktop)."""
    return reposition_window_bottom_right(hwnd, width=1168, height=648)


def micro_click_card(
    hwnd: int,
    rel_x: Optional[int] = None,
    rel_y: Optional[int] = None,
    double_click: bool = True
) -> bool:
    """Thực hiện click vào thẻ dự án trong vài mili-giây và khôi phục chuột + focus cửa sổ cũ ngay lập tức.
    
    Tự động tính tọa độ động theo kích thước cửa sổ CapCut nếu rel_x, rel_y không được chỉ định.
    """
    orig_cursor = None
    orig_fg = None
    try:
        orig_cursor = win32api.GetCursorPos()
    except Exception:
        pass
    try:
        orig_fg = win32gui.GetForegroundWindow()
    except Exception:
        pass

    try:
        force_foreground_window(hwnd)
        time.sleep(0.2)

        rect = win32gui.GetWindowRect(hwnd)
        win_w = max(1, rect[2] - rect[0])
        win_h = max(1, rect[3] - rect[1])

        # Tọa độ thẻ dự án đầu tiên theo tỉ lệ kích thước cửa sổ thực tế
        if rel_x is None:
            rel_x = int(win_w * 0.28) if win_w >= 700 else min(456, int(win_w * 0.5))
        if rel_y is None:
            rel_y = int(win_h * 0.55) if win_h >= 500 else min(807, int(win_h * 0.75))

        abs_x = rect[0] + rel_x
        abs_y = rect[1] + rel_y

        try:
            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            if 0 <= abs_x < screen_w and 0 <= abs_y < screen_h:
                win32api.SetCursorPos((abs_x, abs_y))
                time.sleep(0.04)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.04)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                time.sleep(0.12)
                if double_click:
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.04)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                # Gửi thêm phím Enter để đảm bảo kích hoạt mở dự án đã chọn
                time.sleep(0.15)
                win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
                time.sleep(0.04)
                win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception as ce:
            logger.debug(f"Click chuột trực tiếp gặp lỗi: {ce}")

        return True
    except Exception as e:
        logger.warning(f"Lỗi khi gửi micro-click: {e}")
        return False
    finally:
        time.sleep(0.08)
        if orig_cursor:
            try:
                win32api.SetCursorPos(orig_cursor)
            except Exception:
                pass
        if orig_fg and orig_fg != hwnd:
            try:
                win32gui.SetForegroundWindow(orig_fg)
            except Exception:
                pass


def send_export_shortcut(hwnd: int) -> bool:
    """Gửi phím tắt Ctrl + E để mở hộp thoại Export của CapCut và trả lại focus ngay."""
    force_foreground_window(hwnd)
    time.sleep(0.2)

    try:
        # Nhấn phím Ctrl + E
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(ord('E'), 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(ord('E'), 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        logger.warning(f"Lỗi khi gửi phím tắt Ctrl+E: {e}")
        return False


def confirm_export(hwnd: int) -> bool:
    """Gửi phím Enter để bắt đầu xuất video trong hộp thoại Export."""
    force_foreground_window(hwnd)
    time.sleep(0.2)

    try:
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.8)
        # Gửi thêm 1 lần Enter đề phòng hộp thoại xác nhận ghi đè file hoặc thông báo độ phân giải
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        logger.warning(f"Lỗi khi gửi phím Enter: {e}")
        return False


def kill_capcut_process(pid: Optional[int] = None) -> None:
    """Đóng tiến trình CapCut (bao gồm toàn bộ tiến trình con /T để tránh zombie)."""
    try:
        if pid:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/IM", "CapCut.exe"], capture_output=True)
    except Exception:
        pass


def scan_for_new_mp4(
    start_time: float,
    project_name: str,
    search_dirs: Optional[List[Path]] = None
) -> Optional[Path]:
    """Tìm file video .mp4 mới được CapCut xuất ra sau thời điểm start_time."""
    if not search_dirs:
        draft_base = Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
        proj_dir = draft_base / project_name
        user_videos = Path(os.environ.get("USERPROFILE", "")) / "Videos"
        user_desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        user_downloads = Path(os.environ.get("USERPROFILE", "")) / "Downloads"
        search_dirs = [
            proj_dir,
            draft_base,
            user_videos,
            user_videos / "CapCut",
            user_desktop,
            user_downloads
        ]

    candidates = []
    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        try:
            for pat in ["*.mp4", "*/*.mp4"]:
                for f in s_dir.glob(pat):
                    try:
                        mtime = f.stat().st_mtime
                        if mtime >= start_time - 2.0 and f.stat().st_size > 1024:
                            candidates.append((mtime, f))
                    except Exception:
                        pass
        except Exception:
            pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return None


class CapCutExportSession:
    """Phiên làm việc liên tục với CapCut PC, cho phép xuất hàng loạt dự án mà không cần tắt/mở ứng dụng lặp đi lặp lại.
    
    Quy trình hoạt động:
    1. Khởi động CapCut PC một lần duy nhất lúc bắt đầu.
    2. Đưa cửa sổ ra ngoài màn hình (-4000, -4000) và làm trong suốt.
    3. Với mỗi video: mở project -> xuất file -> đóng cửa sổ Editor (WM_CLOSE) để trở về Home.
    4. Chỉ đóng tiến trình CapCut khi hoàn thành toàn bộ danh sách hoặc khi người dùng yêu cầu dừng.
    """

    def __init__(self, capcut_exe: Optional[Path] = None):
        self.capcut_exe = capcut_exe or find_capcut_exe()
        self.proc: Optional[subprocess.Popen] = None
        self.home_hwnd: Optional[int] = None
        self.current_editor_hwnd: Optional[int] = None

    def start(self, timeout_sec: float = 12.0) -> bool:
        """Khởi động CapCut PC 1 lần duy nhất và đưa vào trạng thái ẩn/off-screen."""
        if not self.capcut_exe or not self.capcut_exe.exists():
            raise FileNotFoundError("Không tìm thấy file CapCut.exe trên hệ thống!")

        if self.is_alive():
            if self.home_hwnd and win32gui.IsWindow(self.home_hwnd):
                make_window_invisible_and_offscreen(self.home_hwnd)
            return True

        self.proc = subprocess.Popen([str(self.capcut_exe)])
        logger.info(f"Đã mở phiên CapCut PC (PID: {self.proc.pid}) ở chế độ ngầm...")

        self.home_hwnd = get_capcut_window(timeout_sec=timeout_sec, require_editor=False)
        if not self.home_hwnd:
            self.close()
            raise RuntimeError("Không phát hiện được cửa sổ CapCut PC sau thời gian chờ!")

        make_window_invisible_and_offscreen(self.home_hwnd)
        return True

    def is_alive(self) -> bool:
        """Kiểm tra tiến trình CapCut PC còn đang chạy hay không."""
        # 1. Kiểm tra qua handle cửa sổ hiện tại đã được gán
        if self.home_hwnd:
            try:
                if win32gui.IsWindow(self.home_hwnd):
                    return True
            except Exception:
                pass
        if self.current_editor_hwnd:
            try:
                if win32gui.IsWindow(self.current_editor_hwnd):
                    return True
            except Exception:
                pass

        # 2. Kiểm tra tiến trình proc launcher
        if self.proc is not None and self.proc.poll() is None:
            return True

        # 3. Kiểm tra bất kỳ tiến trình CapCut nào đang chạy trên máy
        try:
            import psutil
            for p in psutil.process_iter(["name"]):
                if "capcut" in p.info["name"].lower():
                    return True
        except Exception:
            pass

        return False

    def close_current_editor(self, timeout_sec: float = 5.0) -> bool:
        """Đóng cửa sổ Editor hiện tại để CapCut tự lưu và trở về màn hình Home."""
        if self.current_editor_hwnd and win32gui.IsWindow(self.current_editor_hwnd):
            try:
                force_foreground_window(self.current_editor_hwnd)
                time.sleep(0.1)
                # Lưu dự án Ctrl + S
                win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                win32api.keybd_event(ord('S'), 0, 0, 0)
                time.sleep(0.04)
                win32api.keybd_event(ord('S'), 0, win32con.KEYEVENTF_KEYUP, 0)
                win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.15)

                win32gui.PostMessage(self.current_editor_hwnd, win32con.WM_CLOSE, 0, 0)
                t0 = time.time()
                while time.time() - t0 < timeout_sec:
                    if not win32gui.IsWindow(self.current_editor_hwnd):
                        break
                    time.sleep(0.3)
            except Exception as e:
                logger.warning(f"Lỗi khi gửi WM_CLOSE đến Editor: {e}")
        self.current_editor_hwnd = None

        # Làm mới lại home_hwnd sau khi đóng Editor
        if self.is_alive():
            time.sleep(0.5)
            new_home = get_capcut_window(timeout_sec=4.0, require_editor=False)
            if new_home:
                self.home_hwnd = new_home
                make_window_invisible_and_offscreen(self.home_hwnd)
                return True
        return False

    def export_project(
        self,
        draft_name: str,
        target_output_path: str,
        timeout_sec: int = 60,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """Xuất một dự án cụ thể, sau khi xuất xong sẽ thoát project về màn hình Home."""
        if not self.is_alive():
            self.start()

        # Đảm bảo đã đóng editor trước đó nếu còn tồn tại
        if self.current_editor_hwnd:
            self.close_current_editor()

        target_path = Path(target_output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        start_timestamp = time.time()
        user_fg = None
        try:
            user_fg = win32gui.GetForegroundWindow()
        except Exception:
            pass

        if progress_callback:
            progress_callback(20.0, f"Đang mở dự án '{draft_name}' trong CapCut...")

        # 1. Click mở thẻ dự án đầu tiên
        if not self.home_hwnd or not win32gui.IsWindow(self.home_hwnd):
            self.home_hwnd = get_capcut_window(timeout_sec=6.0, require_editor=False)
            if not self.home_hwnd:
                raise RuntimeError("Không tìm thấy cửa sổ CapCut Home để mở dự án!")

        micro_click_card(self.home_hwnd, double_click=True)

        # 2. Đợi editor xuất hiện
        editor_hwnd = get_capcut_window(timeout_sec=12.0, require_editor=True, draft_name=draft_name)
        if not editor_hwnd:
            # Thử click lại thẻ dự án một lần nữa nếu lần đầu chưa mở kịp
            micro_click_card(self.home_hwnd, double_click=True)
            editor_hwnd = get_capcut_window(timeout_sec=8.0, require_editor=True, draft_name=draft_name)

        if not editor_hwnd:
            raise RuntimeError(f"Không thể mở dự án '{draft_name}' trong CapCut PC!")

        self.current_editor_hwnd = editor_hwnd
        make_window_invisible_and_offscreen(self.current_editor_hwnd)
        time.sleep(2.0)

        # 3. Gửi phím tắt Xuất
        if progress_callback:
            progress_callback(40.0, "Đang kích hoạt lệnh Xuất video (Ctrl+E)...")

        send_export_shortcut(self.current_editor_hwnd)
        time.sleep(1.5)
        confirm_export(self.current_editor_hwnd)

        # Trả lại tiêu điểm (focus) cho cửa sổ của người dùng ngay lập tức để tiếp tục làm việc
        if user_fg and win32gui.IsWindow(user_fg) and user_fg != self.current_editor_hwnd:
            try:
                force_foreground_window(user_fg)
            except Exception:
                pass

        # 4. Chờ CapCut render video
        if progress_callback:
            progress_callback(65.0, "CapCut đang render video với hiệu ứng template (8 - 15s)...")

        exported_file = None
        t_wait_start = time.time()
        while time.time() - t_wait_start < timeout_sec:
            time.sleep(1.0)
            candidate = scan_for_new_mp4(start_timestamp, draft_name)
            if candidate:
                sz1 = candidate.stat().st_size
                time.sleep(1.5)
                sz2 = candidate.stat().st_size
                if sz1 == sz2 and sz1 > 5000:
                    exported_file = candidate
                    break

        if not exported_file:
            raise TimeoutError(f"Hết thời gian chờ ({timeout_sec}s) mà CapCut chưa hoàn thành xuất file!")

        # 5. Lưu video thành phẩm
        if progress_callback:
            progress_callback(90.0, "Đang lưu video final vào thư mục dự án...")

        shutil.copy2(exported_file, target_path)
        logger.info(f"Đã xuất video chuẩn CapCut thành công: {target_path.resolve()}")

        # 6. Thoát project về màn hình Home để sẵn sàng cho project tiếp theo
        if progress_callback:
            progress_callback(95.0, "Đang đóng project về màn hình chính...")
        self.close_current_editor()

        if progress_callback:
            progress_callback(100.0, "Hoàn tất xuất video!")
        return str(target_path)

    def close(self) -> None:
        """Đóng tiến trình CapCut PC hoàn toàn khi kết thúc toàn bộ batch."""
        if self.proc:
            kill_capcut_process(pid=self.proc.pid)
            self.proc = None
            self.home_hwnd = None
            self.current_editor_hwnd = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def export_capcut_draft_to_video(
    draft_name: str,
    target_output_path: str,
    timeout_sec: int = 45,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    session: Optional[CapCutExportSession] = None
) -> str:
    """Tự động hóa việc mở CapCut PC và xuất video chuẩn 100% template.
    
    Hỗ trợ tái sử dụng CapCutExportSession nếu được cung cấp để không phải mở/đóng CapCut liên tục.
    """
    if session is not None:
        return session.export_project(
            draft_name=draft_name,
            target_output_path=target_output_path,
            timeout_sec=timeout_sec,
            progress_callback=progress_callback
        )

    # Nếu không có session truyền vào, tạo session tạm và tự đóng khi hoàn tất
    with CapCutExportSession() as temp_session:
        return temp_session.export_project(
            draft_name=draft_name,
            target_output_path=target_output_path,
            timeout_sec=timeout_sec,
            progress_callback=progress_callback
        )

