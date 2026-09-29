import os
import webbrowser
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk

from src.core.exporter import export_to_excel, export_captions_to_txt
from src.config import OUTPUT_DIR, CAPTIONS_DIR


class ResultTable(ctk.CTkFrame):
    """Khu vực hiển thị thống kê, thanh tiến trình và bảng dữ liệu cào trực tiếp."""

    def __init__(self, master, on_clear=None, get_caption_dir=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.records = []
        self.on_clear = on_clear
        self.get_caption_dir = get_caption_dir

        self._build_stats_cards()
        self._build_progress_bar()
        self._build_treeview_table()

    def _build_stats_cards(self):
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=10, pady=(5, 5))

        self.card_total = self._create_card(cards_frame, "Tổng số Reels", "0", "#1877F2")
        self.card_links = self._create_card(cards_frame, "Tìm thấy Link Web", "0", "#2b8a3e")
        self.card_articles = self._create_card(cards_frame, "Bài viết trích xuất", "0", "#e67700")
        self.card_videos = self._create_card(cards_frame, "Video đã tải (.mp4)", "0", "#9c36b5")

        self.card_total.pack(side="left", expand=True, fill="both", padx=(0, 5))
        self.card_links.pack(side="left", expand=True, fill="both", padx=5)
        self.card_articles.pack(side="left", expand=True, fill="both", padx=5)
        self.card_videos.pack(side="left", expand=True, fill="both", padx=(5, 0))

    def _create_card(self, parent, title: str, initial_value: str, color_bar: str):
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color=("#e9ecef", "#212529"))
        bar = ctk.CTkFrame(card, height=4, fg_color=color_bar, corner_radius=2)
        bar.pack(fill="x", side="top")

        lbl_val = ctk.CTkLabel(
            card, text=initial_value, font=ctk.CTkFont(size=20, weight="bold")
        )
        lbl_val.pack(pady=(6, 0))

        lbl_title = ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=11), text_color="gray"
        )
        lbl_title.pack(pady=(0, 6))

        card.val_label = lbl_val
        return card

    def _build_progress_bar(self):
        prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        prog_frame.pack(fill="x", padx=10, pady=5)

        self.progress_bar = ctk.CTkProgressBar(prog_frame, height=14)
        self.progress_bar.pack(fill="x", side="top", pady=(2, 4))
        self.progress_bar.set(0.0)

        status_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        status_row.pack(fill="x", side="bottom")

        self.lbl_status = ctk.CTkLabel(
            status_row,
            text="Sẵn sàng cào dữ liệu.",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.lbl_status.pack(side="left", fill="x", expand=True)

        self.btn_clear = ctk.CTkButton(
            status_row,
            text="🧹 Dọn dẹp kết quả",
            width=135,
            height=28,
            fg_color="#495057",
            hover_color="#343a40",
            command=self._on_clear_clicked
        )
        self.btn_clear.pack(side="right", padx=(6, 0))

        self.btn_view_detail = ctk.CTkButton(
            status_row,
            text="👁️ Xem chi tiết Reel",
            width=145,
            height=28,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._on_view_detail_clicked
        )
        self.btn_view_detail.pack(side="right")

    def _build_treeview_table(self):
        table_container = ctk.CTkFrame(self, corner_radius=8)
        table_container.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Cấu hình Style Dark Mode cho Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Custom.Treeview",
            background="#1e1e1e",
            foreground="#f8f9fa",
            fieldbackground="#1e1e1e",
            rowheight=28,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#2d3748",
            foreground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat"
        )
        style.map("Custom.Treeview", background=[("selected", "#1877F2")])

        cols = ("stt", "reel_url", "caption", "found_in", "target_url", "content", "video_path", "status")
        self.tree = ttk.Treeview(
            table_container,
            columns=cols,
            show="headings",
            style="Custom.Treeview",
            selectmode="browse"
        )

        col_defs = {
            "stt": ("STT", 50, "center"),
            "reel_url": ("Link Reel", 180, "w"),
            "caption": ("Tiêu đề Reels", 200, "w"),
            "found_in": ("Vị trí", 110, "center"),
            "target_url": ("Link Web", 160, "w"),
            "content": ("Nội dung bài viết", 220, "w"),
            "video_path": ("Đường dẫn Video", 160, "w"),
            "status": ("Trạng thái", 120, "center"),
        }

        for col_id, (header, width, align) in col_defs.items():
            self.tree.heading(col_id, text=header)
            self.tree.column(col_id, width=width, minwidth=40, anchor=align)

        # Scrollbars
        scroll_y = ctk.CTkScrollbar(table_container, orientation="vertical", command=self.tree.yview)
        scroll_x = ctk.CTkScrollbar(table_container, orientation="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<Double-1>", self._on_row_double_click)

    def _on_row_double_click(self, event):
        self._on_view_detail_clicked()

    def _on_clear_clicked(self):
        """Xử lý dọn dẹp toàn bộ dữ liệu cào đang hiển thị trên bảng."""
        if not self.records:
            messagebox.showinfo("Thông báo", "Bảng kết quả hiện đang rỗng, không có dữ liệu để dọn dẹp!")
            return
        if messagebox.askyesno(
            "Xác nhận dọn dẹp",
            "Bạn có chắc chắn muốn dọn dẹp toàn bộ kết quả đang hiển thị để bắt đầu cào mới?",
            parent=self
        ):
            self.clear_table()
            self.lbl_status.configure(text="✨ Đã làm sạch toàn bộ kết quả. Sẵn sàng cào mới!")
            if self.on_clear:
                self.on_clear()

    def _on_view_detail_clicked(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một dòng trên bảng để xem chi tiết!")
            return
        item_vals = self.tree.item(selected_item[0], "values")
        if not item_vals:
            return
        stt = int(item_vals[0]) if str(item_vals[0]).isdigit() else 1
        if 1 <= stt <= len(self.records):
            self._show_record_detail(self.records[stt - 1])

    def _show_record_detail(self, record: dict):
        """Mở cửa sổ chi tiết hiển thị 100% đầy đủ nội dung Mô tả gốc và Bài viết web."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Chi tiết nội dung Reel")
        dialog.geometry("820x650")
        dialog.minsize(650, 480)
        dialog.attributes("-topmost", True)

        # Top Bar với Reel URL & Buttons
        top_bar = ctk.CTkFrame(dialog, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(15, 5))

        lbl_r = ctk.CTkLabel(
            top_bar,
            text=f"🎬 Reel: {record.get('reel_url', '')}",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_r.pack(side="left")

        vid_p = record.get("video_path", "")
        if vid_p and os.path.exists(vid_p):
            btn_play = ctk.CTkButton(
                top_bar,
                text="▶️ Mở Video",
                width=100,
                height=28,
                fg_color="#9c36b5",
                hover_color="#ae3ec9",
                command=lambda: os.startfile(vid_p)
            )
            btn_play.pack(side="right", padx=(5, 0))

        tgt_u = record.get("target_url", "")
        if tgt_u and tgt_u.startswith("http"):
            btn_web = ctk.CTkButton(
                top_bar,
                text="🌐 Mở Web Đích",
                width=110,
                height=28,
                fg_color="#1877F2",
                hover_color="#166fe5",
                command=lambda: webbrowser.open(tgt_u)
            )
            btn_web.pack(side="right", padx=5)

        # Full Caption Textbox
        cap = record.get("caption", "")
        lbl_cap = ctk.CTkLabel(
            dialog,
            text=f"📝 Tiêu đề Reels đầy đủ ({len(cap)} ký tự):",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_cap.pack(padx=15, pady=(10, 2), anchor="w")

        txt_cap = ctk.CTkTextbox(dialog, height=220)
        txt_cap.pack(padx=15, pady=(2, 10), fill="both", expand=True)
        txt_cap.insert("1.0", cap)

        # Article Title & Content
        art_title = record.get("title", "")
        art_content = record.get("content", "")
        if tgt_u or art_title or art_content:
            lbl_title_text = f"📰 Nội dung bài viết web đích ({art_title}):" if art_title else "📰 Nội dung bài viết web đích:"
            lbl_art = ctk.CTkLabel(
                dialog,
                text=f"{lbl_title_text} ({len(art_content)} ký tự)",
                font=ctk.CTkFont(size=12, weight="bold")
            )
            lbl_art.pack(padx=15, pady=(5, 2), anchor="w")

            txt_art = ctk.CTkTextbox(dialog, height=180)
            txt_art.pack(padx=15, pady=(2, 15), fill="both", expand=True)
            txt_art.insert("1.0", art_content if art_content else (art_title or "(Không có nội dung bài viết)"))

    def clear_table(self):
        """Xóa toàn bộ dòng hiển thị và đặt lại thống kê."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.records = []
        self._update_stats_display(0, 0, 0, 0)
        self.progress_bar.set(0.0)
        self.lbl_status.configure(text="Sẵn sàng cào dữ liệu.")

    def update_progress(self, current: int, total: int, message: str):
        fraction = (current / total) if total > 0 else 0.0
        self.progress_bar.set(min(max(fraction, 0.0), 1.0))
        if message:
            self.lbl_status.configure(text=message)

    def add_or_update_record(self, record: dict):
        """Thêm bản ghi mới hoặc cập nhật tại chỗ nếu bản ghi (cùng STT hoặc reel_url) đã tồn tại."""
        stt = record.get("stt")
        reel_url = record.get("reel_url", "")

        # Tìm xem bản ghi đã có sẵn trong danh sách chưa
        existing_idx = None
        for i, r in enumerate(self.records):
            if (stt is not None and r.get("stt") == stt) or (reel_url and r.get("reel_url") == reel_url):
                existing_idx = i
                break

        art_content = record.get("content", "") or record.get("title", "")
        content_preview = (art_content or "").replace("\n", " ")[:100]

        vals = (
            record.get("stt", (existing_idx + 1 if existing_idx is not None else len(self.records) + 1)),
            record.get("reel_url", ""),
            (record.get("caption", "") or "").replace("\n", " ")[:80],
            record.get("found_in", ""),
            record.get("target_url", ""),
            content_preview,
            record.get("video_path", ""),
            record.get("status", "")
        )

        tree_items = self.tree.get_children()
        if existing_idx is not None and existing_idx < len(tree_items):
            # Cập nhật tại chỗ
            self.records[existing_idx].update(record)
            self.tree.item(tree_items[existing_idx], values=vals)
        else:
            # Thêm mới
            self.records.append(record)
            self.tree.insert("", "end", values=vals)

        # Cập nhật thống kê
        total = len(self.records)
        links = sum(1 for r in self.records if r.get("target_url"))
        articles = sum(1 for r in self.records if r.get("content") or r.get("title"))
        videos = sum(1 for r in self.records if r.get("video_path"))
        self._update_stats_display(total, links, articles, videos)

    def _update_stats_display(self, total: int, links: int, articles: int, videos: int):
        self.card_total.val_label.configure(text=str(total))
        self.card_links.val_label.configure(text=str(links))
        self.card_articles.val_label.configure(text=str(articles))
        self.card_videos.val_label.configure(text=str(videos))

    def get_records(self) -> list[dict]:
        return self.records
