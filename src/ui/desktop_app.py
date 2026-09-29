import os
import queue
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
from src.core.capcut_builder import (
    render_reels_from_template,
    batch_render_reels_from_folder,
    batch_clone_from_folder,
    find_capcut_draft_dir,
)
from src.core.capcut_exporter import CapCutExportSession, find_capcut_exe
from src.core.whisper_manager import get_whisper_manager
from src.ui.components.crawler_view import CrawlerView
from src.ui.components.result_table import ResultTable
from src.ui.components.sidebar import SidebarFrame
from src.utils.logger import logger
from src.utils.url_helper import resolve_channel_project_dirs

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
            on_stop=self.stop_crawling,
            on_render=self.start_rendering,
            on_create_draft=self.start_creating_draft
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
            # 1. Xác định thư mục dự án và cấu trúc folder kênh: {stt}_{id profile}/[video, caption, final]
            proj_root = settings.get("project_output_dir") or str(OUTPUT_DIR)
            channel_target = ""
            if isinstance(target_data, str) and target_data.strip():
                channel_target = target_data.strip()
            elif isinstance(target_data, list) and target_data:
                channel_target = target_data[0].strip()
            else:
                channel_target = profile_name or "reels_batch"

            resolved = resolve_channel_project_dirs(proj_root, channel_target)
            channel_dir = resolved["channel_dir"]
            video_dir = resolved["video_dir"]
            caption_dir = resolved["caption_dir"]
            final_dir = resolved["final_dir"]

            auto_save_captions = settings.get("auto_save_captions", True)
            auto_render = settings.get("auto_render_template", False)
            download_video = settings.get("download_video", False) or auto_render

            # Chuẩn bị Đa luồng Producer - Consumer nếu bật Auto Render
            render_results = []
            render_queue = queue.Queue() if auto_render else None
            capcut_session = None

            if auto_render:
                try:
                    if find_capcut_exe():
                        capcut_session = CapCutExportSession()
                        capcut_session.start()
                except Exception as ce:
                    logger.warning(f"CapCutExportSession không thể khởi tạo ({ce}), sẽ dùng FFmpeg fallback.")
                    capcut_session = None

                tpl_name = settings.get("render_template_name", "template")
                render_opts = self.crawler_view.get_render_options() if hasattr(self, "crawler_view") else {}
                zoom_ratio = render_opts.get("zoom_ratio", 1.1)
                layout_mode = render_opts.get("layout_mode", "crop_fill")
                whisper_model = settings.get("whisper_model") or render_opts.get("whisper_model", "large-v3-turbo")
                whisper_language = settings.get("whisper_language") or render_opts.get("whisper_language", None)
                filter_screams = render_opts.get("filter_screams", True)
                enable_effects = render_opts.get("enable_effects", True)

                # Nạp trước model Whisper trên GPU CUDA 1 lần duy nhất lúc khởi động cào dự án
                self.after(0, lambda wm=whisper_model: self.result_table.lbl_status.configure(
                    text=f"⚡ Đang nạp model Whisper '{wm}' trên GPU (CUDA NVIDIA)..."
                ))
                get_whisper_manager().preload_model(model_name=whisper_model, device="cuda")

                def render_consumer_worker():
                    while True:
                        item = render_queue.get()
                        if item is None:
                            render_queue.task_done()
                            break
                        if stop_check():
                            render_queue.task_done()
                            break

                        v_path = Path(item["video_path"]) if item.get("video_path") else None
                        if not v_path or not v_path.exists():
                            render_queue.task_done()
                            continue

                        # Cập nhật UI: Đang render
                        render_item = dict(item)
                        render_item["status"] = "🎬 Đang render final..."
                        self.after(0, lambda r=render_item: self.result_table.add_or_update_record(r))

                        out_path = final_dir / f"Reel_{v_path.stem}.mp4"
                        try:
                            res = render_reels_from_template(
                                template_name=tpl_name,
                                new_video_path=str(v_path),
                                output_video_path=str(out_path),
                                zoom_ratio=zoom_ratio,
                                layout_mode=layout_mode,
                                enable_noise=enable_effects,
                                enable_color_grade=enable_effects,
                                enable_vignette=False,
                                whisper_model=whisper_model,
                                whisper_language=whisper_language,
                                filter_screams=filter_screams,
                                use_capcut_pc=True,
                                session=capcut_session
                            )
                            render_item["status"] = "✅ Hoàn tất final"
                            render_item["video_path"] = res["output_video"]
                            render_results.append({
                                "video_name": v_path.name,
                                "output_video": res["output_video"],
                                "elapsed_sec": res["elapsed_sec"],
                                "status": "success"
                            })
                        except Exception as re:
                            logger.error(f"Lỗi render video {v_path.name}: {re}")
                            render_item["status"] = "❌ Lỗi render"
                            render_results.append({
                                "video_name": v_path.name,
                                "output_video": "",
                                "status": "failed",
                                "error": str(re)
                            })

                        # Cập nhật lại UI sau khi render xong
                        self.after(0, lambda r=render_item: self.result_table.add_or_update_record(r))
                        render_queue.task_done()

                consumer_thread = threading.Thread(target=render_consumer_worker, daemon=True)
                consumer_thread.start()
            else:
                consumer_thread = None

            def on_item_downloaded(item_data):
                if render_queue is not None:
                    render_queue.put(item_data)

            results = []
            try:
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
                    download_video=download_video,
                    crawl_order=settings.get("crawl_order", "oldest"),
                    video_output_dir=str(video_dir),
                    caption_output_dir=str(caption_dir),
                    auto_save_captions=auto_save_captions,
                    on_item_ready=on_item_downloaded
                )
            finally:
                if render_queue is not None:
                    render_queue.put(None)
                    if consumer_thread and consumer_thread.is_alive():
                        consumer_thread.join(timeout=300.0)
                if capcut_session is not None:
                    try:
                        capcut_session.close()
                    except Exception:
                        pass
                # Khi hoàn thành cào hoặc dừng cào thì giải phóng model Whisper khỏi GPU CUDA
                get_whisper_manager().unload_model()

            # Xử lý sau khi kết thúc
            self.after(0, lambda: self._on_crawl_finished(
                results, profile_name, settings, render_results, channel_dir=channel_dir, final_dir=final_dir
            ))
        except Exception as e:
            logger.error(f"Lỗi worker cào: {e}", exc_info=True)
            self.after(0, lambda: self._on_crawl_error(str(e)))

    def _update_ui_progress(self, current: int, total: int, message: str, item_data: dict | None):
        self.result_table.update_progress(current, total, message)
        if item_data is not None:
            self.result_table.add_or_update_record(item_data)

    def _on_crawl_finished(
        self,
        results: list[dict],
        profile_name: str,
        settings: dict | None = None,
        render_results: list[dict] | None = None,
        channel_dir: Path | None = None,
        final_dir: Path | None = None
    ):
        self.crawler_view.set_crawling_state(False)
        was_stopped = self.stop_event.is_set()
        self.stop_event.clear()

        if results:
            cfg = settings or {}
            excel_dir = channel_dir or cfg.get("excel_output_dir")
            saved_path = export_to_excel(results, output_dir=excel_dir)
            save_profile_last_results(profile_name, results)

            caption_info = ""
            if cfg.get("auto_save_captions", True):
                cap_dir = (channel_dir / "caption") if channel_dir else Path(cfg.get("caption_output_dir") or str(CAPTIONS_DIR))
                c_count = sum(1 for r in results if r.get("caption_path") or (cap_dir / f"caption_{r.get('stt', 0)}.txt").exists())
                if c_count > 0:
                    caption_info = f"\n- Caption: {c_count} file .txt tại folder 'caption'"

            # Nếu có kết quả Render tự động
            if render_results is not None:
                succ_render = sum(1 for r in render_results if r.get("status") == "success")
                out_rendered_dir = final_dir or (Path("output") / "rendered_videos")
                status_txt = f"🎉 Hoàn thành cào và Render {succ_render}/{len(render_results)} video!"
                self.result_table.lbl_status.configure(text=status_txt)

                msg = (
                    f"🎉 Hoàn thành Quy trình Tự động (Cào + Tải + Render Video)!\n\n"
                    f"📁 Thư mục dự án kênh: {channel_dir.name if channel_dir else ''}\n"
                    f"🎬 Video đã Render: {succ_render}/{len(render_results)} video (.mp4) trong final/\n"
                    f"📊 Excel: {saved_path.name}{caption_info}\n\n"
                    f"Thư mục video thành phẩm:\n{out_rendered_dir.resolve()}\n\n"
                    f"Bạn có muốn mở thư mục video thành phẩm ngay không?"
                )
                ans = messagebox.askyesno("Hoàn tất quy trình tự động", msg, parent=self)
                if ans:
                    os.startfile(str(out_rendered_dir.resolve()))
                return

            open_dir = channel_dir if channel_dir else saved_path.parent
            if was_stopped:
                msg = (
                    f"⏹️ Đã dừng cào theo yêu cầu!\n"
                    f"Đã lưu {len(results)} Reels vào thư mục dự án:\n"
                    f"📁 Thư mục kênh: {channel_dir.name if channel_dir else open_dir.name}\n"
                    f"- Excel: {saved_path.name}{caption_info}\n\n"
                    f"Bạn có muốn mở thư mục dự án kênh ngay không?"
                )
                self.result_table.lbl_status.configure(text=f"⏹️ Đã dừng cào! Đã lưu {len(results)} Reels.")
                ans = messagebox.askyesno("Đã dừng", msg, parent=self)
                if ans:
                    os.startfile(str(open_dir.resolve()))
            else:
                msg = (
                    f"🎉 Hoàn thành cào {len(results)} Reels!\n"
                    f"📁 Thư mục kênh: {channel_dir.name if channel_dir else open_dir.name}\n"
                    f"- Excel: {saved_path.name}{caption_info}\n\n"
                    f"Bạn có muốn mở thư mục dự án kênh ngay không?"
                )
                self.result_table.lbl_status.configure(text=f"🎉 Hoàn thành cào {len(results)} Reels!")
                ans = messagebox.askyesno("Thành công", msg, parent=self)
                if ans:
                    os.startfile(str(open_dir.resolve()))
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

    def start_rendering(self, opts: dict):
        """Bắt đầu tiến trình render video hàng loạt bằng FFmpeg."""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Cảnh báo", "Một tiến trình khác đang chạy! Vui lòng chờ hoàn thành.")
            return

        v_path = Path(opts.get("video_dir", "output/videos"))
        if not v_path.exists():
            messagebox.showwarning("Cảnh báo", f"Đường dẫn video không tồn tại:\n{v_path}")
            return
        if v_path.is_dir() and not any(v_path.glob("*.mp4")):
            messagebox.showwarning("Cảnh báo", f"Không tìm thấy file video .mp4 nào trong:\n{v_path}")
            return

        self.crawler_view.set_rendering_state(True)
        self.result_table.lbl_status.configure(text="⏳ Đang khởi động tiến trình Render video...")

        self.worker_thread = threading.Thread(
            target=self._run_render_worker,
            args=(opts,),
            daemon=True
        )
        self.worker_thread.start()

    def _run_render_worker(self, opts: dict):
        def progress_cb(idx, total, msg):
            self.after(0, lambda: self.result_table.update_progress(idx, total, msg))

        whisper_model = opts.get("whisper_model") or (self.sidebar.get_settings().get("whisper_model") if hasattr(self, "sidebar") else "large-v3-turbo")
        try:
            # Nạp trước model Whisper lên GPU CUDA cho toàn bộ đợt render
            get_whisper_manager().preload_model(model_name=whisper_model, device="cuda")

            target_out_dir = Path(opts.get("output_dir")) if opts.get("output_dir") else (Path("output") / "rendered_videos")
            results = batch_render_reels_from_folder(
                template_name=opts.get("template_name", "template"),
                video_folder=opts.get("video_dir", "output/videos"),
                output_folder=str(target_out_dir),
                zoom_ratio=opts.get("zoom_ratio", 1.1),
                layout_mode=opts.get("layout_mode", "crop_fill"),
                enable_noise=opts.get("enable_effects", True),
                enable_color_grade=opts.get("enable_effects", True),
                whisper_model=whisper_model,
                whisper_language=opts.get("whisper_language", None),
                filter_screams=opts.get("filter_screams", True),
                progress_callback=progress_cb
            )

            success_cnt = sum(1 for r in results if r.get("status") == "success")
            self.after(0, lambda: self._on_render_finished(success_cnt, len(results), target_out_dir=target_out_dir))
        except Exception as e:
            logger.error(f"Lỗi worker render: {e}", exc_info=True)
            self.after(0, lambda: self._on_render_error(str(e)))
        finally:
            get_whisper_manager().unload_model()

    def _on_render_finished(self, success_cnt: int, total_cnt: int, target_out_dir: Path | None = None):
        self.crawler_view.set_rendering_state(False)
        out_dir = target_out_dir or (Path("output") / "rendered_videos")
        self.result_table.lbl_status.configure(text=f"🎉 Hoàn thành Render {success_cnt}/{total_cnt} video thành phẩm!")
        ans = messagebox.askyesno(
            "Hoàn thành Render",
            f"🎉 Đã render thành công {success_cnt}/{total_cnt} video!\n\nLưu tại: {out_dir.resolve()}\n\nBạn có muốn mở thư mục chứa video ngay không?",
            parent=self
        )
        if ans:
            os.startfile(str(out_dir.resolve()))

    def _on_render_error(self, err_msg: str):
        self.crawler_view.set_rendering_state(False)
        self.result_table.lbl_status.configure(text=f"❌ Lỗi Render: {err_msg}")
        messagebox.showerror("Lỗi Render Video", f"Có lỗi xảy ra: {err_msg}", parent=self)

    def start_creating_draft(self, opts: dict):
        """Bắt đầu tiến trình tạo dự án CapCut Draft."""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Cảnh báo", "Một tiến trình khác đang chạy! Vui lòng chờ hoàn thành.")
            return

        v_path = Path(opts.get("video_dir", "output/videos"))
        if not v_path.exists():
            messagebox.showwarning("Cảnh báo", f"Đường dẫn video không tồn tại:\n{v_path}")
            return
        if v_path.is_dir() and not any(v_path.glob("*.mp4")):
            messagebox.showwarning("Cảnh báo", f"Không tìm thấy file video .mp4 nào trong:\n{v_path}")
            return

        self.crawler_view.set_rendering_state(True)
        self.result_table.lbl_status.configure(text="⏳ Đang nhân bản dự án CapCut Draft...")

        self.worker_thread = threading.Thread(
            target=self._run_draft_worker,
            args=(opts,),
            daemon=True
        )
        self.worker_thread.start()

    def _run_draft_worker(self, opts: dict):
        def progress_cb(idx, total, msg):
            self.after(0, lambda: self.result_table.update_progress(idx, total, msg))

        whisper_model = opts.get("whisper_model") or (self.sidebar.get_settings().get("whisper_model") if hasattr(self, "sidebar") else "large-v3-turbo")
        try:
            # Nạp trước model Whisper trên GPU CUDA
            get_whisper_manager().preload_model(model_name=whisper_model, device="cuda")

            whisper_language = opts.get("whisper_language", None)
            results = batch_clone_from_folder(
                template_name=opts.get("template_name", "template"),
                video_folder=opts.get("video_dir", "output/videos"),
                use_whisper_subtitles=opts.get("enable_karaoke", True),
                whisper_model=whisper_model,
                whisper_language=whisper_language,
                progress_callback=progress_cb
            )

            success_cnt = sum(1 for r in results if r.get("status") == "success")
            self.after(0, lambda: self._on_draft_finished(success_cnt, len(results)))
        except Exception as e:
            logger.error(f"Lỗi worker draft: {e}", exc_info=True)
            self.after(0, lambda: self._on_render_error(str(e)))
        finally:
            get_whisper_manager().unload_model()

    def _on_draft_finished(self, success_cnt: int, total_cnt: int):
        self.crawler_view.set_rendering_state(False)
        draft_dir = find_capcut_draft_dir()
        self.result_table.lbl_status.configure(text=f"📁 Đã tạo {success_cnt}/{total_cnt} dự án CapCut Draft!")
        ans = messagebox.askyesno(
            "Hoàn thành tạo Draft",
            f"📁 Đã tạo thành công {success_cnt}/{total_cnt} dự án CapCut Draft!\nMở CapCut PC lên bạn sẽ thấy ngay các dự án mới.\n\nBạn có muốn mở thư mục CapCut Draft ngay không?",
            parent=self
        )
        if ans and draft_dir and draft_dir.exists():
            os.startfile(str(draft_dir.resolve()))

