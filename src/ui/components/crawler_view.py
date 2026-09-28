from tkinter import filedialog, messagebox
import customtkinter as ctk


class CrawlerView(ctk.CTkFrame):
    """Khu vực nhập nguồn dữ liệu (Tab Page / Tab Danh sách link Reels) và nút điều khiển."""

    def __init__(self, master, on_start=None, on_stop=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_start = on_start
        self.on_stop = on_stop

        self._build_tabs()
        self._build_action_buttons()

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(self, height=220)
        self.tabview.pack(fill="x", padx=10, pady=(5, 5))

        # Tab 1: Fanpage / Profile
        self.tab1 = self.tabview.add("🏢 Cào theo Fanpage / Profile")
        lbl_tab1 = ctk.CTkLabel(
            self.tab1,
            text="Nhập link Fanpage hoặc Profile Facebook chứa các video Reels:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_tab1.pack(anchor="w", padx=10, pady=(10, 5))

        self.entry_page_url = ctk.CTkEntry(
            self.tab1,
            placeholder_text="https://www.facebook.com/username hoặc https://www.facebook.com/profile.php?id=...",
            height=38
        )
        self.entry_page_url.pack(fill="x", padx=10, pady=5)

        lbl_tab1_note = ctk.CTkLabel(
            self.tab1,
            text="💡 Hệ thống sẽ tự động quét tab Reels của trang và cào số lượng video tương ứng.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        lbl_tab1_note.pack(anchor="w", padx=10, pady=(5, 10))

        # Tab 2: Danh sách Reels lẻ
        self.tab2 = self.tabview.add("🔗 Cào theo danh sách Reels lẻ")
        lbl_tab2 = ctk.CTkLabel(
            self.tab2,
            text="Dán danh sách link Reels (mỗi dòng 1 link) hoặc tải lên file .txt:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_tab2.pack(anchor="w", padx=10, pady=(5, 2))

        txt_frame = ctk.CTkFrame(self.tab2, fg_color="transparent")
        txt_frame.pack(fill="x", padx=10, pady=2)

        self.txt_reels_list = ctk.CTkTextbox(txt_frame, height=95)
        self.txt_reels_list.pack(side="left", fill="both", expand=True, padx=(0, 8))

        btn_txt_col = ctk.CTkFrame(txt_frame, fg_color="transparent")
        btn_txt_col.pack(side="right", fill="y")

        self.btn_upload_txt = ctk.CTkButton(
            btn_txt_col,
            text="📂 Tải file .txt",
            width=110,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._on_upload_txt
        )
        self.btn_upload_txt.pack(pady=(0, 4))

        self.btn_clear_txt = ctk.CTkButton(
            btn_txt_col,
            text="🧹 Xóa trắng",
            width=110,
            fg_color="#4b5563",
            hover_color="#6b7280",
            command=lambda: self.txt_reels_list.delete("1.0", "end")
        )
        self.btn_clear_txt.pack(pady=4)

    def _build_action_buttons(self):
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(5, 10))

        self.btn_start = ctk.CTkButton(
            btn_row,
            text="🚀 BẮT ĐẦU CÀO DỮ LIỆU",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            fg_color="#1877F2",
            hover_color="#166fe5",
            command=self._on_start_clicked
        )
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 8))

        self.btn_stop = ctk.CTkButton(
            btn_row,
            text="⏹️ DỪNG CÀO",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            width=140,
            fg_color="#e03131",
            hover_color="#c92a2a",
            state="disabled",
            command=self._on_stop_clicked
        )
        self.btn_stop.pack(side="right", padx=(8, 0))

    def _on_upload_txt(self):
        path = filedialog.askopenfilename(
            title="Chọn file chứa danh sách link Reels",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                    content = f.read()
                self.txt_reels_list.delete("1.0", "end")
                self.txt_reels_list.insert("1.0", content)
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                messagebox.showinfo("Đã nạp file", f"Đã nạp thành công {len(lines)} link từ file!")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")

    def _on_start_clicked(self):
        target_type, target_data = self.get_target_data()
        if not target_data:
            if target_type == "page":
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập link Fanpage hoặc Profile Facebook!")
            else:
                messagebox.showwarning("Cảnh báo", "Vui lòng dán danh sách link Reels hoặc tải lên file .txt!")
            return

        if self.on_start:
            self.on_start(target_type, target_data)

    def _on_stop_clicked(self):
        if self.on_stop:
            self.on_stop()

    def set_crawling_state(self, is_crawling: bool):
        """Cập nhật trạng thái hiển thị của các nút bấm khi đang cào."""
        if is_crawling:
            self.btn_start.configure(state="disabled", text="⏳ ĐANG XỬ LÝ CÀO...")
            self.btn_stop.configure(state="normal")
        else:
            self.btn_start.configure(state="normal", text="🚀 BẮT ĐẦU CÀO DỮ LIỆU")
            self.btn_stop.configure(state="disabled")

    def get_target_data(self) -> tuple[str, str | list[str]]:
        """Trả về (loại mục tiêu 'page'|'list', dữ liệu mục tiêu)."""
        cur_tab = self.tabview.get()
        if "Fanpage" in cur_tab:
            url = self.entry_page_url.get().strip()
            return "page", url
        else:
            text = self.txt_reels_list.get("1.0", "end-1c").strip()
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            return "list", lines

    def set_page_url(self, url: str):
        self.entry_page_url.delete(0, "end")
        self.entry_page_url.insert(0, url)
