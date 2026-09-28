# 🎬 Facebook Reels & Article Content Extractor (Desktop & Web Edition)

Công cụ tự động hóa mạnh mẽ giúp cào dữ liệu video **Facebook Reels** (theo Fanpage/Profile hoặc danh sách link lẻ), tự động **tải video Reels (.mp4)** về máy, trích xuất các **đường link bài viết** gắn trong Caption hoặc bình luận, giải mã link rút gọn, bóc tách sạch sẽ **Tiêu đề & Nội dung bài viết gốc** từ các website báo chí/blog, và xuất ra file **Excel (.xlsx)** có định dạng chuyên nghiệp.

Hỗ trợ cả **Giao diện Desktop hiện đại (CustomTkinter)** chạy trực tiếp trên Windows và **Giao diện Web (Streamlit)** truy cập qua mạng LAN.

---

## 🌟 Tính Năng Nổi Bật

- 🖥️ **Ứng dụng Desktop Windows hiện đại (CustomTkinter)**:
  - Giao diện Dark/Light mode chuẩn phong cách Windows 11.
  - Chạy ngầm đa luồng (Background Threading), giao diện mượt mà không bị đơ/lag khi cào.
  - Phím dừng cào tức thì (Stop Crawling) an toàn, không làm mất dữ liệu đã cào.
  - Nút 1-click **"📂 Mở thư mục Video"** và **"📊 Mở thư mục Excel"**.
  - Nhấp đúp vào dòng dữ liệu để mở trực tiếp Video hoặc Link Web trên máy tính.
- 🎬 **Tải Video Reels (.mp4) trực tiếp về máy**:
  - Tích hợp module tải video chất lượng cao thông qua `yt-dlp`.
  - Tùy chọn bật/tắt tải video (`[x] Tải video Reels`).
  - Video được lưu trực tiếp vào thư mục `output/videos/<reel_id>.mp4`.
  - Tự động gắn đường dẫn video vào báo cáo Excel.
- ⚡ **Tối ưu hóa hiệu năng & Tương thích từng máy**:
  - Tự động sử dụng **Microsoft Edge** hoặc **Google Chrome** có sẵn trên máy Windows (`channel="msedge"`), không bắt buộc phải tải thêm Chromium rời.
  - Chặn tải ngầm media/image/font khi Playwright duyệt DOM giúp tiết kiệm 80% RAM và băng thông mạng.
- 🚀 **Cào đa nguồn linh hoạt**:
  - Hỗ trợ cào trực tiếp theo đường dẫn **Fanpage** hoặc **Profile cá nhân** (hỗ trợ cả dạng username `/reels/` lẫn dạng ID `profile.php?id=...&sk=reels_tab`).
  - Hỗ trợ cào theo **danh sách link Reels lẻ** (nhập trực tiếp hoặc tải file `.txt`).
- 🔗 **Bóc tách & Giải mã liên kết thông minh**:
  - Tự động nhận diện URL bài viết trong Caption hoặc quét trong bình luận.
  - Tự động giải mã và theo dõi chuỗi chuyển hướng của các dịch vụ rút gọn link (`bit.ly`, `tinyurl`...).
- 📰 **Trích xuất nội dung bài viết chất lượng cao**:
  - Tích hợp thư viện chuyên dụng **Trafilatura** kết hợp fallback **BeautifulSoup4** trích xuất Tiêu đề và Nội dung bài viết gốc sạch sẽ.
- 🛡️ **Quản lý Đa Profile (Multi-Profile) & Cookie**:
  - Quản lý nhiều tài khoản Facebook riêng biệt trong `browser_profile/profiles/`.
  - Hỗ trợ nạp Cookie (JSON từ Cookie-Editor hoặc chuỗi `c_user=...; xs=...`) hoặc mở trình duyệt đăng nhập trực tiếp.
- 📊 **Xuất báo cáo Excel chuyên nghiệp**:
  - File Excel (.xlsx) tự động lưu vào `output/excel/` kèm định dạng màu sắc thẩm mỹ, căn chỉnh độ rộng cột và tự động wrap text.

---

## 🏗️ Kiến Trúc Thư Mục Mới (Clean Architecture)

```text
reels_fb/
├── src/                                  # Toàn bộ mã nguồn ứng dụng
│   ├── config.py                         # Cấu hình hằng số, đường dẫn hệ thống
│   ├── core/                             # TẦNG NGHIỆP VỤ LÕI (Không phụ thuộc UI)
│   │   ├── fb_crawler.py                 # Quét Reels, lấy Caption & link ngoài
│   │   ├── video_downloader.py           # Tải video .mp4 bằng yt-dlp
│   │   ├── article_extractor.py          # Bóc tách bài viết website ngoài
│   │   └── exporter.py                   # Xuất dữ liệu Excel & CSV
│   ├── ui/                               # TẦNG GIAO DIỆN
│   │   ├── desktop_app.py                # Cửa sổ chính CustomTkinter
│   │   └── components/                   # Các widget con tái sử dụng
│   │       ├── sidebar.py                # Sidebar quản lý Profile & Settings
│   │       ├── crawler_view.py           # Tab nhập Fanpage & Tab link Reels lẻ
│   │       └── result_table.py           # Bảng tiến trình & xem kết quả
│   └── utils/                            # TIỆN ÍCH DÙNG CHUNG
│       ├── cookies.py                    # Phân tích, nạp, kiểm tra cookie FB
│       ├── url_helper.py                 # Chuẩn hóa link Reel, giải mã redirect
│       └── logger.py                     # Quản lý log hệ thống
├── tests/                                # Bộ kiểm thử tự động toàn diện (Pytest)
├── output/                               # THƯ MỤC CHỨA DỮ LIỆU ĐẦU RA
│   ├── excel/                            # Chứa file kết quả .xlsx
│   └── videos/                           # Chứa các file video .mp4 tải về
├── browser_profile/                      # Lưu trữ phiên đăng nhập Playwright
├── main.py                               # Entrypoint khởi chạy Desktop App
├── run_desktop.bat                       # 1-click khởi chạy Desktop App
├── run.bat                               # 1-click khởi chạy Web App (Streamlit)
├── build.bat                             # Script đóng gói thành file .exe (PyInstaller)
└── requirements.txt                      # Thư viện phụ thuộc
```

---

## ⚡ Hướng Dẫn Cài Đặt Nhanh

1. Mở PowerShell hoặc Terminal tại thư mục dự án:
```bash
pip install -r requirements.txt
```
*(Tùy chọn nếu chưa có sẵn trình duyệt trên máy)*:
```bash
playwright install chromium
```

---

## 🚀 Cách Sử Dụng

### 1. Chạy Ứng dụng Desktop (Khuyên dùng)
- **Cách 1**: Nhấp đúp chuột vào file **`run_desktop.bat`**.
- **Cách 2**: Chạy lệnh từ terminal:
  ```bash
  python main.py
  ```

### 2. Đóng gói thành file `.exe` chạy độc lập (PyInstaller)
- Nhấp đúp chuột vào file **`build.bat`**.
- Sau khi đóng gói hoàn tất, thư mục phần mềm sẽ nằm tại:
  `dist/FacebookReelsExtractor/FacebookReelsExtractor.exe`
- Bạn có thể nén zip thư mục này và chuyển sang bất kỳ máy tính Windows nào khác để sử dụng mà không cần cài đặt Python.

### 3. Chạy Bản Web LAN Server (Nếu muốn)
- Nhấp đúp vào file **`run.bat`** để mở phiên bản Web Streamlit trên cổng `8501`.

---

## 🧪 Kiểm Thử Tự Động (Testing)

Chạy toàn bộ 73 bài kiểm thử tự động (Unit & Integration tests):
```bash
pytest
```
Mọi module (crawler, video downloader, article extractor, exporter, cookies, url helper, desktop app) đều được kiểm thử với độ bao phủ cao.
