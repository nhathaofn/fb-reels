import os
import threading
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

from src.config import EXCEL_DIR, OUTPUT_DIR, CAPTIONS_DIR
from src.core.exporter import export_to_excel, export_captions_to_txt
from src.core.fb_crawler import (
    load_profile_last_results,
    load_profile_settings,
    run_crawler_pipeline,
    save_profile_last_results,
)
from src.ui.components.crawler_view import CrawlerView
from src.ui.components.result_table import ResultTable
from src.ui.components.sidebar import SidebarFrame
from src.utils.logger import logger

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class DesktopApp(ctk.CTk):
    """Cửa sổ ứng dụng Desktop chính (CustomTkinter)."""

    def __init__(self):
        super().__init__()

        self.title("Facebook Reels & Article Extractor (Desktop Edition)")
        self.geometry("1200x750")
        self.minsize(980, 600)

        # Trạng thái điều khiển luồng
        self.stop_event = threading.Event()
        self.worker_thread = None

        self._build_layout()
        self._load_initial_state()

    def _build_layout(self):
        # 1. Sidebar bên trái
        self.sidebar = SidebarFrame(
            self,
            on_profile_change=self._on_profile_change
        )
        self.sidebar.pack(side="left", fill="y", padx=(10, 5), pady=10)

        # 2. Main content container bên phải
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

        # Header Title
        title_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        title_frame.pack(fill="x", padx=10, pady=(0, 5))

        lbl_app_title = ctk.CTkLabel(
            title_frame,
            text="🎬 Facebook Reels & Article Extractor",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        lbl_app_title.pack(side="left")

        lbl_version = ctk.CTkLabel(
            title_frame,
            text="v2.0 (Desktop Edition)",
            font=ctk.CTkFont(size=12),
            text_color="#1877F2"
        )
        lbl_version.pack(side="left", padx=8, pady=(4, 0))

        # Crawler Inputs (Tabs) & Action Buttons
        self.crawler_view = CrawlerView(
            self.main_container,
            on_start=self.start_crawling,
            on_stop=self.stop_crawling
        )
        self.crawler_view.pack(fill="x", pady=(0, 5))

        # Result Table & Progress Area
        self.result_table = ResultTable(
            self.main_container,
            on_clear=self._on_clear_results
        )
        self.result_table.pack(fill="both", expand=True)

    def _load_initial_state(self):
        """Khôi phục cấu hình và kết quả cào gần nhất của profile."""
        prof = self.sidebar.get_selected_profile()
        s = load_profile_settings(prof)
        if s.get("last_page_url"):
            self.crawler_view.set_page_url(s.get("last_page_url"))

        last_results = load_profile_last_results(prof)
        if last_results:
            for r in last_results:
                self.result_table.add_or_update_record(r)
            self.result_table.lbl_status.configure(
                text=f"Đã khôi phục {len(last_results)} kết quả từ phiên trước của '{prof}'."
            )

    def _on_clear_results(self):
        """Xóa cache kết quả cào của profile hiện tại để phiên sau mở lên sạch sẽ."""
        prof = self.sidebar.get_selected_profile()
        save_profile_last_results(prof, [])

    def _on_profile_change(self, profile_name: str):
        """Khi người dùng đổi profile trên sidebar."""
        self.result_table.clear_table()
        self._load_initial_state()

    def start_crawling(self, target_type: str, target_data: str | list[str]):
        """Bắt đầu chạy luồng cào dữ liệu trong background thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Cảnh báo", "Tiến trình cào đang chạy!")
            return

        settings = self.sidebar.get_settings()
        selected_prof = self.sidebar.get_selected_profile()

        # Lưu lại URL trang nếu là tab page
        if target_type == "page":
            settings["last_page_url"] = str(target_data)
            self.sidebar.save_current_settings()

        self.stop_event.clear()
        self.result_table.clear_table()
        self.crawler_view.set_crawling_state(True)

        self.worker_thread = threading.Thread(
            target=self._run_crawler_worker,
            args=(target_type, target_data, settings, selected_prof),
            daemon=True
        )
        self.worker_thread.start()

    def stop_crawling(self):
        """Gửi tín hiệu dừng tiến trình cào."""
        if self.stop_event:
            self.stop_event.set()
            self.result_table.lbl_status.configure(text="⏹️ Đang gửi tín hiệu dừng cào...")

    def _run_crawler_worker(
        self,
        target_type: str,
        target_data: str | list[str],
        settings: dict,
        profile_name: str
    ):
        """Hàm chạy trên luồng phụ, cập nhật UI an toàn qua self.after."""
        def progress_callback(cur, total, msg, item_data):
            if self.stop_event.is_set():
                return False
            # Chuyển lời gọi cập nhật UI sang luồng chính
            self.after(0, lambda: self._update_ui_progress(cur, total, msg, item_data))
            return True

        def stop_check():
            return self.stop_event.is_set()

        try:
            video_dir = settings.get("video_output_dir")
            caption_dir = settings.get("caption_output_dir")
            auto_save_captions = settings.get("auto_save_captions", True)
            results = run_crawler_pipeline(
                input_type=target_type,
                target_data=target_data,
                max_reels=settings.get("max_reels", 20),
                check_comments=settings.get("check_comments", True),
                delay_range=(settings.get("delay_min", 2.0), settings.get("delay_max", 5.0)),
                headless=settings.get("headless", True),
                progress_callback=progress_callback,
                stop_check_callback=stop_check,
                profile_name=profile_name,
                download_video=settings.get("download_video", False),
                crawl_order=settings.get("crawl_order", "oldest"),
                video_output_dir=video_dir,
                caption_output_dir=caption_dir,
                auto_save_captions=auto_save_captions
            )

            # Xử lý sau khi kết thúc
            self.after(0, lambda: self._on_crawl_finished(results, profile_name, settings))
        except Exception as e:
            logger.error(f"Lỗi worker cào: {e}", exc_info=True)
            self.after(0, lambda: self._on_crawl_error(str(e)))

    def _update_ui_progress(self, current: int, total: int, message: str, item_data: dict | None):
        self.result_table.update_progress(current, total, message)
        if item_data is not None:
            self.result_table.add_or_update_record(item_data)

    def _on_crawl_finished(self, results: list[dict], profile_name: str, settings: dict | None = None):
        self.crawler_view.set_crawling_state(False)
        was_stopped = self.stop_event.is_set()
        self.stop_event.clear()

        if results:
            cfg = settings or {}
            excel_dir = cfg.get("excel_output_dir")
            saved_path = export_to_excel(results, output_dir=excel_dir)
            save_profile_last_results(profile_name, results)

            caption_info = ""
            if cfg.get("auto_save_captions", True):
                cap_dir = cfg.get("caption_output_dir") or str(CAPTIONS_DIR)
                c_count = sum(1 for r in results if r.get("caption_path") or (Path(cap_dir) / f"caption_{r.get('stt', 0)}.txt").exists())
                if c_count > 0:
                    caption_info = f"\n- Caption: {c_count} file .txt tại '{Path(cap_dir).name}'"

            if was_stopped:
                msg = f"⏹️ Đã dừng cào theo yêu cầu! Đã lưu {len(results)} Reels vào:\n- Excel: {saved_path.name}{caption_info}"
                self.result_table.lbl_status.configure(text=f"⏹️ Đã dừng cào! Đã lưu {len(results)} Reels.")
                messagebox.showinfo("Đã dừng", f"{msg}\n\nThư mục Excel: {saved_path.parent}", parent=self)
            else:
                msg = f"🎉 Hoàn thành cào {len(results)} Reels!\n- Excel: {saved_path.name}{caption_info}"
                self.result_table.lbl_status.configure(text=f"🎉 Hoàn thành cào {len(results)} Reels!")
                messagebox.showinfo("Thành công", f"{msg}\n\nThư mục Excel: {saved_path.parent}", parent=self)
        else:
            if was_stopped:
                self.result_table.lbl_status.configure(text="⏹️ Đã dừng cào. Chưa có video nào được cào.")
            else:
                self.result_table.lbl_status.configure(text="⚠️ Không tìm thấy video Reel nào.")
                messagebox.showwarning("Thông báo", "Không tìm thấy video Reel nào!", parent=self)

    def _on_crawl_error(self, err_msg: str):
        self.crawler_view.set_crawling_state(False)
        self.stop_event.clear()
        self.result_table.lbl_status.configure(text=f"❌ Lỗi: {err_msg}")
        messagebox.showerror("Lỗi cào dữ liệu", f"Có lỗi xảy ra: {err_msg}", parent=self)
