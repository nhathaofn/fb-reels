# Thiết kế Kỹ thuật: Tái cấu trúc Kiến trúc Hệ thống, Ứng dụng Desktop & Tải Video Facebook Reels

- **Ngày tạo**: 2026-09-28
- **Tác giả**: Antigravity & User
- **Trạng thái**: Đã phê duyệt (Approved)

---

## 1. Mục tiêu (Goals & Requirements)

1. **Tái cấu trúc thư mục & mã nguồn (Clean Architecture)**:
   - Tách biệt rõ ràng các tầng: `src/core/` (nghiệp vụ cào, tải video, bóc tách bài viết, xuất file), `src/ui/` (giao diện người dùng Desktop), `src/utils/` (tiện ích cookie, URL, logging).
   - Tách biệt dữ liệu đầu ra: `output/excel/` và `output/videos/`.
   - Entrypoint rõ ràng: `main.py` ở thư mục gốc để khởi chạy ứng dụng.
2. **Giao diện Desktop chuyên nghiệp (CustomTkinter)**:
   - Thay thế việc phụ thuộc vào trình duyệt web (Streamlit) để chạy trực tiếp trên Windows như một phần mềm độc lập.
   - Hỗ trợ Dark Mode / Light Mode hiện đại.
   - Xử lý đa luồng (Background Threading) để UI không bị đơ giật trong lúc cào.
   - Nút "Dừng cào" phản hồi tức thì.
   - Nút 1-click "📂 Mở thư mục Video" và "📊 Mở file Excel".
3. **Tính năng Tải Video Reels (.mp4)**:
   - Tích hợp module `video_downloader` (dựa trên `yt-dlp` / direct stream).
   - Cho phép người dùng bật/tắt tải video (`[x] Tải video về máy`).
   - Tự động gắn phiên/cookie của Profile hiện tại để tải được cả các video bị giới hạn.
   - Lưu video vào `output/videos/<reel_id>.mp4`.
   - Ghi đường dẫn file video vào file Excel kết quả.
4. **Tối ưu hóa Playwright & Môi trường chạy trên từng máy**:
   - Sử dụng Microsoft Edge hoặc Google Chrome có sẵn trên Windows (`channel="msedge"` hoặc `channel="chrome"`).
   - Chặn tải media (video streaming ngầm) khi Playwright quét DOM để tiết kiệm 80% RAM và băng thông mạng (việc tải video thực tế được giao cho downloader chuyên dụng).
   - Tạo script `run_desktop.bat` và `build.bat` (đóng gói PyInstaller thành `.exe`).

---

## 2. Kiến trúc Thư mục Chi tiết

```text
reels_fb/
├── src/
│   ├── __init__.py
│   ├── config.py                 # Cấu hình hằng số, đường dẫn (BASE_DIR, OUTPUT_DIR, etc.)
│   ├── core/                     # TẦNG NGHIỆP VỤ LÕI
│   │   ├── __init__.py
│   │   ├── fb_crawler.py         # Quét danh sách Reels, trích xuất caption & link ngoài
│   │   ├── video_downloader.py   # Tải video .mp4 chất lượng cao bằng yt-dlp / stream
│   │   ├── article_extractor.py  # Bóc tách nội dung website ngoài bằng Trafilatura
│   │   └── exporter.py           # Xuất báo cáo Excel / CSV có định dạng thẩm mỹ
│   ├── ui/                       # TẦNG GIAO DIỆN DESKTOP
│   │   ├── __init__.py
│   │   ├── desktop_app.py        # Cửa sổ chính CustomTkinter (App Window & Controller)
│   │   └── components/           # Các widget con tái sử dụng
│   │       ├── __init__.py
│   │       ├── sidebar.py        # Sidebar quản lý Profile Facebook & cài đặt cào
│   │       ├── crawler_view.py   # Tab nhập Fanpage & Tab nhập danh sách link Reels
│   │       └── result_table.py   # Bảng hiển thị kết quả & tiến trình trực tiếp
│   └── utils/                    # TIỆN ÍCH DÙNG CHUNG
│       ├── __init__.py
│       ├── cookies.py            # Phân tích, nạp & xác thực cookie Facebook
│       ├── url_helper.py         # Chuẩn hóa link Reel, giải mã link redirect FB
│       └── logger.py             # Cấu hình logging thống nhất
├── tests/                        # BỘ TEST SUITE TOÀN DIỆN (PYTEST)
│   ├── test_config.py
│   ├── test_cookies.py
│   ├── test_url_helper.py
│   ├── test_article_extractor.py
│   ├── test_video_downloader.py
│   ├── test_exporter.py
│   └── test_fb_crawler.py
├── output/
│   ├── excel/                    # Chứa các file .xlsx
│   └── videos/                   # Chứa các file .mp4
├── browser_profile/              # Phiên đăng nhập Playwright cho các profile
├── main.py                       # Điểm khởi chạy phần mềm Desktop
├── requirements.txt              # Thư viện phụ thuộc
├── run_desktop.bat               # Khởi chạy 1-click trên Windows
└── build.bat                     # Đóng gói PyInstaller thành .exe
```

---

## 3. Thiết kế Chi tiết các Module

### 3.1. `src/config.py`
- Xác định đường dẫn gốc: `BASE_DIR = Path(__file__).resolve().parent.parent`
- Đường dẫn profile: `PROFILE_DIR = BASE_DIR / "browser_profile"`
- Đường dẫn đầu ra: 
  - `OUTPUT_DIR = BASE_DIR / "output"`
  - `EXCEL_DIR = OUTPUT_DIR / "excel"`
  - `VIDEOS_DIR = OUTPUT_DIR / "videos"`
- Đảm bảo tự động tạo các thư mục này nếu chưa có.
- Cấu hình timeouts, user agents, delay ranges, browser channels (`msedge`).

### 3.2. `src/utils/`
- **`cookies.py`**:
  - `parse_cookie_input(cookie_input: str) -> list[dict]`: Parse JSON hoặc chuỗi `c_user=...; xs=...`.
  - `save_cookies_to_profile(profile_name, cookie_input, channel="msedge") -> tuple[bool, str]`.
  - `has_logged_in_session(profile_name) -> bool`: Đọc SQLite cookies kiểm tra `c_user`.
- **`url_helper.py`**:
  - `normalize_reels_url(input_url: str) -> str`: Chuẩn hóa URL page/profile thành `/reels/`.
  - `extract_urls_from_text(text: str) -> list[str]`: Lọc URL bỏ qua tên miền meta/facebook, giải mã `l.facebook.com/l.php?u=...`.
- **`logger.py`**:
  - Cấu hình chuẩn định dạng log, stream ra console và ghi file log nếu cần.

### 3.3. `src/core/video_downloader.py`
- `download_reel_video(reel_url: str, output_dir: Path, cookies_list: list[dict] | None = None) -> tuple[bool, str, str]`:
  - Trả về `(success: bool, video_path: str, message: str)`.
  - Sử dụng `yt-dlp` API (`yt_dlp.YoutubeDL`).
  - Đặt template tên file theo `reel_id` hoặc timestamp: `output/videos/{reel_id}.mp4`.
  - Nếu có cookies của profile, trích xuất hoặc truyền cookie sang yt-dlp.
  - Fallback trực tiếp nếu yt-dlp gặp trục trặc: bắt link `.mp4` từ Playwright stream tải về.

### 3.4. `src/core/fb_crawler.py`
- Tối ưu với `channel="msedge"`: khởi chạy ngay lập tức trên mọi máy Windows không cần cài đặt thêm Chromium.
- Tối ưu chặn media/ảnh trong lúc cào DOM:
  ```python
  def block_media(route):
      if route.request.resource_type in ["media", "image", "font"]:
          route.abort()
      else:
          route.continue_()
  page.route("**/*", block_media)
  ```
- Nhận tham số mới `download_video: bool = False`.
- Nếu `download_video == True`, sau khi trích xuất thông tin Reel, gọi `download_reel_video(reel_url, VIDEOS_DIR, cookies)`.
- Ghi trường `video_path` vào dictionary kết quả.

### 3.5. `src/core/exporter.py`
- Bổ sung cột mới vào bảng Excel:
  - `COLUMNS_MAP`:
    - `video_path`: "Đường dẫn Video"
- Căn chỉnh độ rộng cột, style màu sắc và đóng băng tiêu đề.

### 3.6. `src/ui/desktop_app.py`
- Sử dụng thư viện `customtkinter` (kế thừa `ctk.CTk`).
- Gồm:
  - **Sidebar**:
    - Chọn Profile Facebook, Nạp Cookie nhanh, Mở trình duyệt đăng nhập, Thêm Profile.
    - Cài đặt: Số lượng Reels, Delay ngẫu nhiên, Quét bình luận, Ẩn trình duyệt.
    - **Check-box:** `[x] Tải video Reels (.mp4) về máy`.
    - **Nút:** `📂 Mở thư mục Video`, `📊 Mở thư mục Excel`.
  - **Main Area**:
    - Tabview: Tab 1 "Fanpage / Profile", Tab 2 "Danh sách Reels lẻ".
    - Hàng nút hành động: `🚀 Bắt đầu cào dữ liệu` (Primary), `⏹️ Dừng cào` (Danger).
    - Progress Bar + Label trạng thái (hiển thị phần trăm và chi tiết thao tác đang chạy).
    - Result Treeview / Data Table: Bảng danh sách kết quả trực tiếp với scrollbar dọc/ngang.
  - **Threading**:
    - Sử dụng `threading.Thread(target=..., daemon=True)` khi bấm Bắt đầu để đảm bảo UI mượt mà 60fps.
    - Tín hiệu dừng `stop_event = threading.Event()`.

---

## 4. Kế hoạch Đóng gói & Phân phối (Packaging)

- **`run_desktop.bat`**: File batch khởi chạy nhanh môi trường Python cục bộ hoặc venv.
- **`build.bat`**: Chạy PyInstaller với lệnh:
  ```bat
  pyinstaller --noconfirm --onedir --windowed ^
    --add-data "src;src" ^
    --name "FacebookReelsExtractor" ^
    main.py
  ```
- Hướng dẫn tạo bản Portable cho người dùng sao chép sang máy khác chạy ngay.
