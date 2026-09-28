import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import EXCEL_DIR, VIDEOS_DIR, CAPTIONS_DIR, DEFAULT_MAX_REELS, MIN_DELAY, MAX_DELAY
from src.core.fb_crawler import (
    delete_profile,
    has_logged_in_session,
    launch_login_browser,
    list_available_profiles,
    load_profile_settings,
    save_cookies_to_profile,
    save_profile_settings,
    get_profile_dir
)


class SidebarFrame(ctk.CTkScrollableFrame):
    """Thanh điều khiển bên trái quản lý Profile Facebook và cấu hình cào."""

    def __init__(self, master, on_profile_change=None, on_settings_change=None, **kwargs):
        super().__init__(master, width=280, **kwargs)
        self.on_profile_change = on_profile_change
        self.on_settings_change = on_settings_change

        self._build_profile_section()
        self._build_settings_section()
        self._build_folder_shortcuts()
        self.refresh_profiles()

    def _build_profile_section(self):
        # Section Header
        self.lbl_profile_title = ctk.CTkLabel(
            self, text="👤 Tài khoản Facebook", font=ctk.CTkFont(size=16, weight="bold")
        )
        self.lbl_profile_title.pack(padx=10, pady=(10, 5), anchor="w")

        # Profile Select OptionMenu
        self.profile_var = ctk.StringVar(value="default")
        self.opt_profiles = ctk.CTkOptionMenu(
            self,
            variable=self.profile_var,
            values=["default"],
            command=self._on_profile_selected
        )
        self.opt_profiles.pack(padx=10, pady=5, fill="x")

        # Status badge
        self.lbl_status = ctk.CTkLabel(
            self, text="🟡 Đang kiểm tra...", font=ctk.CTkFont(size=12)
        )
        self.lbl_status.pack(padx=10, pady=2, anchor="w")

        # Profile Action Buttons
        self.btn_cookie = ctk.CTkButton(
            self, text="🔑 Nạp Cookie", fg_color="#343a40", hover_color="#495057", command=self._show_cookie_dialog
        )
        self.btn_cookie.pack(padx=10, pady=4, fill="x")

        self.btn_browser_login = ctk.CTkButton(
            self, text="🖥️ Mở trình duyệt đăng nhập", fg_color="#4b5563", hover_color="#6b7280", command=self._launch_browser_login
        )
        self.btn_browser_login.pack(padx=10, pady=4, fill="x")

        # Sub-buttons row (Add / Delete)
        row_btn = ctk.CTkFrame(self, fg_color="transparent")
        row_btn.pack(padx=10, pady=4, fill="x")

        self.btn_add_profile = ctk.CTkButton(
            row_btn, text="➕ Thêm", width=80, fg_color="#2b8a3e", hover_color="#2f9e44", command=self._show_add_profile_dialog
        )
        self.btn_add_profile.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_del_profile = ctk.CTkButton(
            row_btn, text="🗑️ Xóa", width=80, fg_color="#c92a2a", hover_color="#e03131", command=self._delete_current_profile
        )
        self.btn_del_profile.pack(side="right", expand=True, fill="x", padx=(4, 0))

    def _build_settings_section(self):
        # Divider
        ctk.CTkLabel(self, text="—" * 25, text_color="gray").pack(pady=8)

        # Section Header
        lbl_cfg_title = ctk.CTkLabel(
            self, text="⚙️ Cấu hình cào", font=ctk.CTkFont(size=16, weight="bold")
        )
        lbl_cfg_title.pack(padx=10, pady=(5, 5), anchor="w")

        # Max Reels
        lbl_max = ctk.CTkLabel(self, text="Số lượng Reels tối đa:", font=ctk.CTkFont(size=12))
        lbl_max.pack(padx=10, pady=(4, 0), anchor="w")

        self.max_reels_var = ctk.IntVar(value=DEFAULT_MAX_REELS)
        self.entry_max_reels = ctk.CTkEntry(self, textvariable=self.max_reels_var)
        self.entry_max_reels.pack(padx=10, pady=(2, 6), fill="x")

        # Thứ tự video Reels
        lbl_order = ctk.CTkLabel(self, text="Thứ tự lấy video Reels:", font=ctk.CTkFont(size=12))
        lbl_order.pack(padx=10, pady=(4, 0), anchor="w")

        self.crawl_order_var = ctk.StringVar(value="Cũ nhất trước (Từ video đầu tiên)")
        self.opt_crawl_order = ctk.CTkOptionMenu(
            self,
            variable=self.crawl_order_var,
            values=["Cũ nhất trước (Từ video đầu tiên)", "Mới nhất trước (Từ video gần đây)"]
        )
        self.opt_crawl_order.pack(padx=10, pady=(2, 6), fill="x")

        # Delay
        lbl_delay = ctk.CTkLabel(self, text="Delay ngẫu nhiên (giây):", font=ctk.CTkFont(size=12))
        lbl_delay.pack(padx=10, pady=(4, 0), anchor="w")

        self.delay_min_var = ctk.DoubleVar(value=MIN_DELAY)
        self.delay_max_var = ctk.DoubleVar(value=MAX_DELAY)
        delay_row = ctk.CTkFrame(self, fg_color="transparent")
        delay_row.pack(padx=10, pady=(2, 6), fill="x")
        self.entry_delay_min = ctk.CTkEntry(delay_row, textvariable=self.delay_min_var, width=80)
        self.entry_delay_min.pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkLabel(delay_row, text="-").pack(side="left")
        self.entry_delay_max = ctk.CTkEntry(delay_row, textvariable=self.delay_max_var, width=80)
        self.entry_delay_max.pack(side="right", expand=True, fill="x", padx=(4, 0))

        # Checkboxes
        self.check_comments_var = ctk.BooleanVar(value=True)
        self.chk_comments = ctk.CTkCheckBox(
            self, text="Quét link trong bình luận", variable=self.check_comments_var
        )
        self.chk_comments.pack(padx=10, pady=5, anchor="w")

        self.headless_var = ctk.BooleanVar(value=True)
        self.chk_headless = ctk.CTkCheckBox(
            self, text="Chạy ẩn trình duyệt (Headless)", variable=self.headless_var
        )
        self.chk_headless.pack(padx=10, pady=5, anchor="w")

        # Download Video Checkbox
        self.download_video_var = ctk.BooleanVar(value=False)
        self.chk_download_video = ctk.CTkCheckBox(
            self, text="🎬 Tải video Reels (.mp4)", variable=self.download_video_var,
            text_color="#38d9a9"
        )
        self.chk_download_video.pack(padx=10, pady=5, anchor="w")

        # Auto-save Caption Checkbox
        self.auto_save_captions_var = ctk.BooleanVar(value=True)
        self.chk_auto_save_captions = ctk.CTkCheckBox(
            self, text="📝 Tự động lưu Caption (.txt)", variable=self.auto_save_captions_var,
            text_color="#ffd43b"
        )
        self.chk_auto_save_captions.pack(padx=10, pady=5, anchor="w")

    def _build_folder_shortcuts(self):
        # Divider
        ctk.CTkLabel(self, text="—" * 25, text_color="gray").pack(pady=8)

        lbl_folder = ctk.CTkLabel(
            self, text="📁 Thư mục kết quả", font=ctk.CTkFont(size=15, weight="bold")
        )
        lbl_folder.pack(padx=10, pady=(2, 6), anchor="w")

        # 1. Thư mục lưu Video
        lbl_v_title = ctk.CTkLabel(self, text="🎬 Thư mục lưu Video (.mp4):", font=ctk.CTkFont(size=12))
        lbl_v_title.pack(padx=10, pady=(2, 0), anchor="w")

        self.video_dir_var = ctk.StringVar(value=str(VIDEOS_DIR))
        self.entry_video_dir = ctk.CTkEntry(
            self, textvariable=self.video_dir_var, font=ctk.CTkFont(size=11)
        )
        self.entry_video_dir.pack(padx=10, pady=(2, 4), fill="x")
        self.entry_video_dir.bind("<FocusOut>", lambda e: self.save_current_settings())

        row_v_btn = ctk.CTkFrame(self, fg_color="transparent")
        row_v_btn.pack(padx=10, pady=(0, 8), fill="x")

        self.btn_choose_videos = ctk.CTkButton(
            row_v_btn,
            text="📂 Chọn...",
            width=70,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._choose_videos_folder
        )
        self.btn_choose_videos.pack(side="left", expand=True, fill="x", padx=(0, 2))

        self.btn_open_videos = ctk.CTkButton(
            row_v_btn,
            text="↗️ Mở",
            width=55,
            fg_color="#1971c2",
            hover_color="#1c7ed6",
            command=self._open_videos_folder
        )
        self.btn_open_videos.pack(side="left", expand=True, fill="x", padx=2)

        self.btn_reset_videos = ctk.CTkButton(
            row_v_btn,
            text="↺",
            width=30,
            fg_color="#495057",
            hover_color="#6c757d",
            command=self._reset_videos_folder
        )
        self.btn_reset_videos.pack(side="right", padx=(2, 0))

        # 2. Thư mục lưu Excel
        lbl_e_title = ctk.CTkLabel(self, text="📊 Thư mục lưu Excel (.xlsx):", font=ctk.CTkFont(size=12))
        lbl_e_title.pack(padx=10, pady=(2, 0), anchor="w")

        self.excel_dir_var = ctk.StringVar(value=str(EXCEL_DIR))
        self.entry_excel_dir = ctk.CTkEntry(
            self, textvariable=self.excel_dir_var, font=ctk.CTkFont(size=11)
        )
        self.entry_excel_dir.pack(padx=10, pady=(2, 4), fill="x")
        self.entry_excel_dir.bind("<FocusOut>", lambda e: self.save_current_settings())

        row_e_btn = ctk.CTkFrame(self, fg_color="transparent")
        row_e_btn.pack(padx=10, pady=(0, 6), fill="x")

        self.btn_choose_excel = ctk.CTkButton(
            row_e_btn,
            text="📂 Chọn...",
            width=70,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._choose_excel_folder
        )
        self.btn_choose_excel.pack(side="left", expand=True, fill="x", padx=(0, 2))

        self.btn_open_excel = ctk.CTkButton(
            row_e_btn,
            text="↗️ Mở",
            width=55,
            fg_color="#099268",
            hover_color="#0ca678",
            command=self._open_excel_folder
        )
        self.btn_open_excel.pack(side="left", expand=True, fill="x", padx=2)

        self.btn_reset_excel = ctk.CTkButton(
            row_e_btn,
            text="↺",
            width=30,
            fg_color="#495057",
            hover_color="#6c757d",
            command=self._reset_excel_folder
        )
        self.btn_reset_excel.pack(side="right", padx=(2, 0))

        # 3. Thư mục lưu Caption
        lbl_c_title = ctk.CTkLabel(self, text="📝 Thư mục lưu Caption (.txt):", font=ctk.CTkFont(size=12))
        lbl_c_title.pack(padx=10, pady=(2, 0), anchor="w")

        self.caption_dir_var = ctk.StringVar(value=str(CAPTIONS_DIR))
        self.entry_caption_dir = ctk.CTkEntry(
            self, textvariable=self.caption_dir_var, font=ctk.CTkFont(size=11)
        )
        self.entry_caption_dir.pack(padx=10, pady=(2, 4), fill="x")
        self.entry_caption_dir.bind("<FocusOut>", lambda e: self.save_current_settings())

        row_c_btn = ctk.CTkFrame(self, fg_color="transparent")
        row_c_btn.pack(padx=10, pady=(0, 6), fill="x")

        self.btn_choose_caption = ctk.CTkButton(
            row_c_btn,
            text="📂 Chọn...",
            width=70,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._choose_caption_folder
        )
        self.btn_choose_caption.pack(side="left", expand=True, fill="x", padx=(0, 2))

        self.btn_open_caption = ctk.CTkButton(
            row_c_btn,
            text="↗️ Mở",
            width=55,
            fg_color="#e67700",
            hover_color="#f59f00",
            command=self._open_caption_folder
        )
        self.btn_open_caption.pack(side="left", expand=True, fill="x", padx=2)

        self.btn_reset_caption = ctk.CTkButton(
            row_c_btn,
            text="↺",
            width=30,
            fg_color="#495057",
            hover_color="#6c757d",
            command=self._reset_caption_folder
        )
        self.btn_reset_caption.pack(side="right", padx=(2, 0))

    def refresh_profiles(self):
        """Cập nhật lại danh sách profile."""
        profiles = list_available_profiles()
        self.opt_profiles.configure(values=profiles)
        cur = self.profile_var.get()
        if cur not in profiles:
            cur = profiles[0] if profiles else "default"
            self.profile_var.set(cur)
        self._update_login_badge()
        self._load_settings_into_ui()

    def _update_login_badge(self):
        prof = self.profile_var.get()
        is_logged = has_logged_in_session(prof)
        if is_logged:
            self.lbl_status.configure(text=f"🟢 Đã đăng nhập ({prof})", text_color="#20c997")
        else:
            self.lbl_status.configure(text=f"🟡 Chưa đăng nhập ({prof})", text_color="#fcc419")

    def _on_profile_selected(self, choice):
        self._update_login_badge()
        self._load_settings_into_ui()
        if self.on_profile_change:
            self.on_profile_change(choice)

    def _load_settings_into_ui(self):
        prof = self.profile_var.get()
        s = load_profile_settings(prof)
        self.max_reels_var.set(int(s.get("max_reels", DEFAULT_MAX_REELS)))
        self.delay_min_var.set(float(s.get("delay_min", MIN_DELAY)))
        self.delay_max_var.set(float(s.get("delay_max", MAX_DELAY)))
        self.check_comments_var.set(bool(s.get("check_comments", True)))
        self.headless_var.set(bool(s.get("headless", True)))
        self.download_video_var.set(bool(s.get("download_video", False)))
        order_val = s.get("crawl_order", "oldest")
        self.crawl_order_var.set(
            "Cũ nhất trước (Từ video đầu tiên)" if order_val == "oldest" else "Mới nhất trước (Từ video gần đây)"
        )
        self.video_dir_var.set(s.get("video_output_dir", str(VIDEOS_DIR)))
        self.excel_dir_var.set(s.get("excel_output_dir", str(EXCEL_DIR)))
        self.caption_dir_var.set(s.get("caption_output_dir", str(CAPTIONS_DIR)))
        self.auto_save_captions_var.set(bool(s.get("auto_save_captions", True)))

    def save_current_settings(self):
        """Lưu lại cấu hình hiện tại vào settings.json của profile."""
        prof = self.profile_var.get()
        try:
            max_r = int(self.max_reels_var.get())
        except Exception:
            max_r = DEFAULT_MAX_REELS
        try:
            d_min = float(self.delay_min_var.get())
            d_max = float(self.delay_max_var.get())
        except Exception:
            d_min, d_max = MIN_DELAY, MAX_DELAY

        order_choice = "oldest" if "Cũ nhất" in self.crawl_order_var.get() else "newest"

        v_dir = self.video_dir_var.get().strip() or str(VIDEOS_DIR)
        e_dir = self.excel_dir_var.get().strip() or str(EXCEL_DIR)
        c_dir = self.caption_dir_var.get().strip() or str(CAPTIONS_DIR)

        cfg = {
            "max_reels": max_r,
            "delay_min": d_min,
            "delay_max": d_max,
            "check_comments": bool(self.check_comments_var.get()),
            "headless": bool(self.headless_var.get()),
            "download_video": bool(self.download_video_var.get()),
            "auto_save_captions": bool(self.auto_save_captions_var.get()),
            "crawl_order": order_choice,
            "video_output_dir": v_dir,
            "excel_output_dir": e_dir,
            "caption_output_dir": c_dir,
        }
        save_profile_settings(prof, cfg)
        return cfg

    def get_settings(self) -> dict:
        return self.save_current_settings()

    def get_selected_profile(self) -> str:
        return self.profile_var.get()

    def _show_cookie_dialog(self):
        prof = self.profile_var.get()
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Nạp Cookie cho Profile: {prof}")
        dialog.geometry("520x360")
        dialog.attributes("-topmost", True)

        lbl = ctk.CTkLabel(
            dialog,
            text=f"Dán Cookie (JSON hoặc chuỗi c_user=...; xs=...) vào đây:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl.pack(padx=15, pady=(15, 5), anchor="w")

        txt = ctk.CTkTextbox(dialog, height=180)
        txt.pack(padx=15, pady=5, fill="both", expand=True)

        def save_cookie_action():
            content = txt.get("1.0", "end-1c").strip()
            if not content:
                messagebox.showwarning("Cảnh báo", "Vui lòng dán cookie trước khi lưu!", parent=dialog)
                return
            ok, msg = save_cookies_to_profile(prof, content)
            if ok:
                messagebox.showinfo("Thành công", msg, parent=dialog)
                dialog.destroy()
                self._update_login_badge()
            else:
                messagebox.showerror("Thất bại", msg, parent=dialog)

        btn_save = ctk.CTkButton(
            dialog, text="💾 Lưu Cookie vào Profile", fg_color="#1877F2", command=save_cookie_action
        )
        btn_save.pack(padx=15, pady=(5, 15), fill="x")

    def _show_add_profile_dialog(self):
        dialog = ctk.CTkInputDialog(text="Nhập tên Profile mới (không dấu, vd: May_2, Hao):", title="Thêm Profile")
        name = dialog.get_input()
        if name and name.strip():
            created = get_profile_dir(name.strip())
            self.refresh_profiles()
            self.profile_var.set(created.name)
            self._on_profile_selected(created.name)
            messagebox.showinfo("Thành công", f"Đã tạo profile '{created.name}'!")

    def _delete_current_profile(self):
        prof = self.profile_var.get()
        if messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc chắn muốn xóa phiên của profile '{prof}'?"):
            delete_profile(prof)
            self.refresh_profiles()
            self.profile_var.set("default")
            self._on_profile_selected("default")
            messagebox.showinfo("Đã xóa", f"Đã xóa dữ liệu của profile '{prof}'!")

    def _launch_browser_login(self):
        prof = self.profile_var.get()
        messagebox.showinfo(
            "Mở trình duyệt",
            f"Trình duyệt Facebook sẽ mở ra cho Profile '{prof}'.\nĐăng nhập xong, bạn hãy đóng cửa sổ trình duyệt.",
            parent=self
        )
        def run():
            launch_login_browser(prof, headless=False)
            self.after(500, self._update_login_badge)
        threading.Thread(target=run, daemon=True).start()

    def _choose_videos_folder(self):
        cur = self.video_dir_var.get().strip()
        initial = cur if cur and os.path.exists(cur) else str(VIDEOS_DIR)
        selected = filedialog.askdirectory(
            title="Chọn thư mục lưu Video Reels (.mp4)",
            initialdir=initial
        )
        if selected:
            norm_path = str(Path(selected).resolve())
            self.video_dir_var.set(norm_path)
            self.save_current_settings()

    def _reset_videos_folder(self):
        self.video_dir_var.set(str(VIDEOS_DIR))
        self.save_current_settings()

    def _open_videos_folder(self):
        cur = self.video_dir_var.get().strip()
        target = Path(cur) if cur else VIDEOS_DIR
        target.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(target))
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}", parent=self)

    def _choose_excel_folder(self):
        cur = self.excel_dir_var.get().strip()
        initial = cur if cur and os.path.exists(cur) else str(EXCEL_DIR)
        selected = filedialog.askdirectory(
            title="Chọn thư mục lưu file Excel (.xlsx)",
            initialdir=initial
        )
        if selected:
            norm_path = str(Path(selected).resolve())
            self.excel_dir_var.set(norm_path)
            self.save_current_settings()

    def _reset_excel_folder(self):
        self.excel_dir_var.set(str(EXCEL_DIR))
        self.save_current_settings()

    def _open_excel_folder(self):
        cur = self.excel_dir_var.get().strip()
        target = Path(cur) if cur else EXCEL_DIR
        target.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(target))
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}", parent=self)

    def _choose_caption_folder(self):
        cur = self.caption_dir_var.get().strip()
        initial = cur if cur and os.path.exists(cur) else str(CAPTIONS_DIR)
        selected = filedialog.askdirectory(
            title="Chọn thư mục lưu file Caption (.txt)",
            initialdir=initial
        )
        if selected:
            norm_path = str(Path(selected).resolve())
            self.caption_dir_var.set(norm_path)
            self.save_current_settings()

    def _reset_caption_folder(self):
        self.caption_dir_var.set(str(CAPTIONS_DIR))
        self.save_current_settings()

    def _open_caption_folder(self):
        cur = self.caption_dir_var.get().strip()
        target = Path(cur) if cur else CAPTIONS_DIR
        target.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(target))
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}", parent=self)

    def get_video_dir(self) -> Path:
        val = self.video_dir_var.get().strip()
        return Path(val) if val else VIDEOS_DIR

    def get_excel_dir(self) -> Path:
        val = self.excel_dir_var.get().strip()
        return Path(val) if val else EXCEL_DIR

    def get_caption_dir(self) -> Path:
        val = self.caption_dir_var.get().strip()
        return Path(val) if val else CAPTIONS_DIR
