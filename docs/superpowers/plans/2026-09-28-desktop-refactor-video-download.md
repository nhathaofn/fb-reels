# Tái cấu trúc Kiến trúc Hệ thống, Ứng dụng Desktop & Tải Video Facebook Reels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tái cấu trúc dự án sang kiến trúc phân tầng sạch sẽ (`src/core`, `src/ui`, `src/utils`), xây dựng giao diện ứng dụng Desktop (CustomTkinter) có tính năng tải video Reels (.mp4), tối ưu cào với MS Edge/Chrome và hỗ trợ đóng gói chạy độc lập trên từng máy.

**Architecture:** 
- Tách biệt rõ ràng tệp lõi backend nghiệp vụ (`src/core`), tiện ích (`src/utils`) và giao diện Desktop (`src/ui`).
- `video_downloader` sử dụng `yt-dlp` để tải trực tiếp video chất lượng cao mà không bắt trình duyệt phải phát video.
- Giao diện CustomTkinter chạy trên luồng phụ (`threading.Thread`) để giữ giao diện mượt mà 60fps và cho phép dừng tức thì.
- Kết quả được phân chia rõ ràng: `output/excel/` và `output/videos/`.

**Tech Stack:** Python 3.13, CustomTkinter, Playwright (Chromium/Edge), yt-dlp, Trafilatura, BeautifulSoup4, HTTPX, Openpyxl, Pandas, PyInstaller, Pytest.

**Spec:** [docs/superpowers/specs/2026-09-28-desktop-refactor-video-download-design.md](file:///d:/nhathao/gehihi%202.0/reels_fb/docs/superpowers/specs/2026-09-28-desktop-refactor-video-download-design.md)

## Global Constraints
- Tất cả các bài test kiểm thử phải chạy thành công 100%.
- Không làm gãy logic cào dữ liệu Facebook Reels, xử lý profile và cookie hiện có.
- Trình duyệt Playwright ưu tiên sử dụng `channel="msedge"` để tương thích ngay với Windows 10/11 mà không cần tải Chromium rời.
- Thư mục dữ liệu kết quả: `output/excel/` chứa file Excel và `output/videos/` chứa file video `.mp4`.

---

### Task 1: Cập nhật Dependencies & Cài đặt môi trường
**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Cập nhật file `requirements.txt`**
  Thêm `customtkinter>=5.2.0`, `yt-dlp>=2024.12.0`, `pyinstaller>=6.10.0`.
- [ ] **Step 2: Cài đặt các thư viện mới vào môi trường Python**
  Chạy lệnh `pip install -r requirements.txt`.
- [ ] **Step 3: Kiểm tra import thành công**
  Chạy `python -c "import customtkinter; import yt_dlp; print('OK')"` để xác nhận.

---

### Task 2: Thiết kế `src/config.py` và Cấu trúc Thư mục mới
**Files:**
- Create: `src/__init__.py`
- Create: `src/config.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Produces: `BASE_DIR`, `SRC_DIR`, `PROFILE_DIR`, `PROFILES_DIR`, `OUTPUT_DIR`, `EXCEL_DIR`, `VIDEOS_DIR`, `DEFAULT_MAX_REELS`, `MIN_DELAY`, `MAX_DELAY`, `REQUEST_TIMEOUT`, `USER_AGENT`, `BROWSER_CHANNEL`.

- [ ] **Step 1: Viết test cho `src/config.py` trong `tests/test_config.py`**
  Kiểm tra các đường dẫn `EXCEL_DIR`, `VIDEOS_DIR`, `PROFILE_DIR` được tự động tạo thư mục trên đĩa.
- [ ] **Step 2: Viết mã nguồn cho `src/config.py`**
  Khởi tạo đường dẫn gốc từ `Path(__file__).resolve().parent.parent`, định nghĩa các hằng số.
- [ ] **Step 3: Chạy test kiểm tra**
  Chạy `pytest tests/test_config.py`.

---

### Task 3: Tách Tầng Tiện ích (`src/utils/`)
**Files:**
- Create: `src/utils/__init__.py`
- Create: `src/utils/logger.py`
- Create: `src/utils/url_helper.py`
- Create: `src/utils/cookies.py`
- Create: `tests/test_url_helper.py`
- Create: `tests/test_cookies.py`

**Interfaces:**
- `src/utils/url_helper.py`:
  - `normalize_reels_url(input_url: str) -> str`
  - `extract_urls_from_text(text: str) -> list[str]`
- `src/utils/cookies.py`:
  - `parse_cookie_input(cookie_input: str) -> list[dict]`
  - `has_logged_in_session(profile_name: str) -> bool`
  - `save_cookies_to_profile(profile_name: str, cookie_input: str, channel: str = "msedge") -> tuple[bool, str]`

- [ ] **Step 1: Viết unit tests cho `url_helper.py` và `cookies.py`**
- [ ] **Step 2: Triển khai `logger.py`, `url_helper.py`, `cookies.py`**
- [ ] **Step 3: Chạy pytest kiểm tra**
  Chạy `pytest tests/test_url_helper.py tests/test_cookies.py`.

---

### Task 4: Di chuyển và Cập nhật `src/core/article_extractor.py`
**Files:**
- Create: `src/core/__init__.py`
- Create: `src/core/article_extractor.py`
- Modify: `tests/test_article_extractor.py`

**Interfaces:**
- `resolve_target_url(url: str, timeout: float = REQUEST_TIMEOUT) -> str`
- `extract_article_from_html(html: str, url: str = "") -> dict`
- `extract_article(url: str, timeout: float = REQUEST_TIMEOUT) -> dict`

- [ ] **Step 1: Cập nhật import trong `tests/test_article_extractor.py` trỏ sang `src.core.article_extractor`**
- [ ] **Step 2: Triển khai `src/core/article_extractor.py` sử dụng `src.config`**
- [ ] **Step 3: Chạy pytest kiểm tra**
  Chạy `pytest tests/test_article_extractor.py`.

---

### Task 5: Xây dựng Module Tải Video (`src/core/video_downloader.py`)
**Files:**
- Create: `src/core/video_downloader.py`
- Create: `tests/test_video_downloader.py`

**Interfaces:**
- `download_reel_video(reel_url: str, output_dir: Path | str, cookies_data: list[dict] | None = None) -> tuple[bool, str, str]`
  - Trả về `(success: bool, file_path: str, message: str)`

- [ ] **Step 1: Viết unit test cho `video_downloader.py` (sử dụng mock cho `yt_dlp.YoutubeDL`)**
- [ ] **Step 2: Triển khai `src/core/video_downloader.py`**
  Thiết lập `outtmpl`, định dạng mp4, cấu hình không in banner rác ra console, bắt ngoại lệ an toàn.
- [ ] **Step 3: Chạy pytest kiểm tra**
  Chạy `pytest tests/test_video_downloader.py`.

---

### Task 6: Cập nhật Module Xuất Báo cáo (`src/core/exporter.py`)
**Files:**
- Create: `src/core/exporter.py`
- Modify: `tests/test_exporter.py`

**Interfaces:**
- `COLUMNS_MAP`: Bổ sung `"video_path": "Đường dẫn Video"`
- `export_to_excel(records: list[dict], output_filepath: Path | str | None = None) -> Path`
  Mặc định lưu vào `EXCEL_DIR / f"reels_content_{timestamp}.xlsx"`.

- [ ] **Step 1: Cập nhật unit test `tests/test_exporter.py` với cột `video_path`**
- [ ] **Step 2: Triển khai `src/core/exporter.py`**
  Định dạng cột mới trong Excel, tự động căn độ rộng cột và style thẩm mỹ.
- [ ] **Step 3: Chạy pytest kiểm tra**
  Chạy `pytest tests/test_exporter.py`.

---

### Task 7: Cập nhật Module Cào Lõi (`src/core/fb_crawler.py`)
**Files:**
- Create: `src/core/fb_crawler.py`
- Modify: `tests/test_fb_crawler.py`

**Interfaces:**
- Nhận tham số mới `download_video: bool = False` trong `run_crawler_pipeline` và `crawl_reels`.
- Sử dụng `channel="msedge"` (fallback Chromium nếu Edge không có).
- Chặn tải media/image khi duyệt Playwright để tiết kiệm RAM.
- Tích hợp `video_downloader` khi `download_video` được bật.
- Quản lý profile Facebook: `get_profile_dir`, `list_available_profiles`, `delete_profile`, `launch_login_browser`.

- [ ] **Step 1: Cập nhật unit tests trong `tests/test_fb_crawler.py`**
- [ ] **Step 2: Triển khai `src/core/fb_crawler.py`**
- [ ] **Step 3: Chạy toàn bộ test suite hiện có**
  Chạy `pytest` để xác nhận tất cả các bài test đều pass.

---

### Task 8: Xây dựng Các Component Giao diện Desktop (`src/ui/components/`)
**Files:**
- Create: `src/ui/__init__.py`
- Create: `src/ui/components/__init__.py`
- Create: `src/ui/components/sidebar.py`
- Create: `src/ui/components/crawler_view.py`
- Create: `src/ui/components/result_table.py`

**Interfaces:**
- `SidebarFrame(ctk.CTkFrame)`:
  - Dropdown chọn profile, nút tạo profile, nút nạp cookie, nút mở trình duyệt đăng nhập.
  - Các slider & checkbox: Số lượng Reels, Delay, Quét bình luận, Ẩn trình duyệt, **[x] Tải video Reels**.
  - Nút: "📂 Mở thư mục Video", "📊 Mở thư mục Excel".
- `CrawlerView(ctk.CTkTabview)`:
  - Tab 1: Input URL Fanpage / Profile.
  - Tab 2: Textbox dán danh sách URL Reels + Nút tải file `.txt`.
  - Nút "🚀 Bắt đầu cào" và "⏹️ Dừng cào".
- `ResultTable(ctk.CTkFrame)`:
  - Thanh tiến trình `CTkProgressBar`, nhãn trạng thái `CTkLabel`.
  - Bảng dữ liệu hiển thị các Reels đã cào (sử dụng `ttk.Treeview` styled dark theme).

- [ ] **Step 1: Xây dựng component `sidebar.py`**
- [ ] **Step 2: Xây dựng component `crawler_view.py`**
- [ ] **Step 3: Xây dựng component `result_table.py`**

---

### Task 9: Tích hợp Cửa sổ Chính Desktop App & Entrypoint
**Files:**
- Create: `src/ui/desktop_app.py`
- Create: `main.py`
- Create: `tests/test_desktop_app.py`

**Interfaces:**
- `DesktopApp(ctk.CTk)`: Kết nối `Sidebar`, `CrawlerView`, `ResultTable` và `src.core.fb_crawler`.
- Xử lý Threading an toàn: Chạy pipeline cào trong `threading.Thread`, sử dụng queue hoặc `after()` để cập nhật UI từ worker thread.

- [ ] **Step 1: Viết test cơ bản cho khởi tạo `DesktopApp`**
- [ ] **Step 2: Triển khai `src/ui/desktop_app.py`**
- [ ] **Step 3: Triển khai `main.py`**
- [ ] **Step 4: Chạy kiểm thử pytest**

---

### Task 10: Xây dựng File Khởi chạy 1-Click & Đóng gói PyInstaller
**Files:**
- Create: `run_desktop.bat`
- Create: `build.bat`
- Modify: `README.md`

- [ ] **Step 1: Tạo `run_desktop.bat`** (1-click chạy `python main.py` với title và giao diện dòng lệnh gọn gàng).
- [ ] **Step 2: Tạo `build.bat`** (sử dụng PyInstaller đóng gói thành file `.exe` độc lập).
- [ ] **Step 3: Cập nhật tài liệu hướng dẫn trong `README.md`**
- [ ] **Step 4: Chạy kiểm tra toàn bộ test suite `pytest`**
