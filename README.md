# 🎬 Facebook Reels & Article Content Extractor

Công cụ tự động hóa mạnh mẽ giúp cào dữ liệu video **Facebook Reels** (theo Fanpage/Profile hoặc danh sách link lẻ), tự động trích xuất các **đường link bài viết** gắn trong Caption hoặc Top bình luận, giải mã link rút gọn, bóc tách sạch sẽ **Tiêu đề & Nội dung bài viết gốc** từ các website báo chí/blog, và xuất ra file **Excel (.xlsx)** có định dạng chuyên nghiệp.

---

## 🌟 Tính Năng Nổi Bật

- 🚀 **Cào đa nguồn linh hoạt**:
  - Hỗ trợ cào trực tiếp theo đường dẫn **Fanpage** hoặc **Profile cá nhân** (tự động nhận diện cả dạng username `/reels/` lẫn dạng ID `profile.php?id=...&sk=reels_tab`).
  - Hỗ trợ cào theo **danh sách link Reels lẻ** (nhập trực tiếp vào ô văn bản hoặc tải lên file `.txt`, hỗ trợ cả UTF-8 và UTF-8 with BOM).
  - Tự động chuẩn hóa liên kết, loại bỏ trùng lặp và cuộn trang thu thập thông minh.
- 🔗 **Bóc tách & Giải mã liên kết thông minh**:
  - Tự động nhận diện URL bài viết nằm trong Caption của Reel.
  - Tự động quét tìm link trong Top bình luận (nếu Caption không chứa link).
  - Tự động giải mã và theo dõi chuỗi chuyển hướng của các dịch vụ rút gọn link (`bit.ly`, `tinyurl`, `t.co`...) để tìm ra URL bài viết đích thực tế.
- 📰 **Trích xuất nội dung bài viết chất lượng cao**:
  - Tích hợp thư viện chuyên dụng **Trafilatura** kết hợp fallback **BeautifulSoup4** trích xuất sạch Tiêu đề (Title) và Nội dung (Article Body), loại bỏ triệt để quảng cáo, banner, mã rác.
- 🛡️ **Đăng nhập an toàn & Chống Checkpoint**:
  - Sử dụng cơ chế **Playwright Persistent Context** lưu session/cookie cục bộ trong thư mục `browser_profile/`.
  - Hỗ trợ người dùng tự mở trình duyệt thực tế để đăng nhập tài khoản một lần duy nhất (hỗ trợ cả 2FA / OTP), không lưu mật khẩu, an toàn tuyệt đối cho tài khoản.
- 📊 **Xuất báo cáo Excel chuyên nghiệp**:
  - File Excel (.xlsx) được tự động kẻ khung, định dạng màu sắc tiêu đề trang nhã, căn chỉnh độ rộng cột và bật ngắt dòng tự động (Wrap Text).
  - Tự động lưu trữ lịch sử cào vào thư mục `output/` kèm timestamp và hỗ trợ tải trực tiếp qua giao diện Web.
- 🖥️ **Giao diện Web Streamlit hiện đại**:
  - Hiển thị tiến trình thời gian thực (Real-time Progress Bar & Status).
  - Bảng xem trước dữ liệu trực tiếp (Live Preview Table) ngay khi mỗi Reel được cào xong.
  - Trang bị nút **⏹️ Dừng cào (Stop Crawling)** an toàn, cho phép dừng bất kỳ lúc nào mà không làm mất dữ liệu đã cào.

---

## 📋 Yêu Cầu Hệ Thống

- **Hệ điều hành**: Windows 10/11, macOS, hoặc Linux.
- **Python**: Phiên bản `3.10` trở lên (Khuyến nghị **Python 3.13** 64-bit).
- **Trình duyệt**: Đã cài đặt Chromium cho Playwright (hướng dẫn bên dưới).

---

## ⚡ Hướng Dẫn Cài Đặt Nhanh

### Bước 1: Mở Terminal / PowerShell
Di chuyển vào thư mục chứa mã nguồn của tool:
```bash
cd <thư_mục_chứa_tool>
```

### Bước 2: Cài đặt trọn gói bằng 1 dòng lệnh
Cài đặt toàn bộ các thư viện phụ thuộc và trình duyệt Playwright Chromium chỉ với một câu lệnh:
```bash
pip install -r requirements.txt && playwright install chromium
```

> **Ghi chú**: Bạn cũng có thể cài đặt từng bước riêng biệt nếu muốn:
> 1. `pip install -r requirements.txt` (cài các thư viện Python)
> 2. `playwright install chromium` (tải trình duyệt Chromium cho Playwright)

---

## 🚀 Cách Mở & Khởi Chạy Tool (Máy Chủ & Mạng LAN)

Bạn có thể khởi động công cụ bằng một trong hai cách đơn giản sau trên máy chủ (Host):

### Cách 1: Sử dụng file chạy nhanh (Dành cho Windows - Khuyên dùng)
- Click đúp chuột vào file **`run.bat`** tại thư mục gốc của dự án.
- Cửa sổ Console sẽ tự động khởi tạo môi trường và mở ứng dụng Web trên cổng `8501`.
- Giao diện sẽ thông báo rõ:
  - Địa chỉ truy cập tại máy chủ: `http://localhost:8501`
  - Địa chỉ truy cập từ các máy khác trong mạng LAN: `http://<IP_MAY_CHU>:8501` (ví dụ: `http://192.168.1.27:8501`).

### Cách 2: Khởi chạy bằng lệnh qua Terminal / PowerShell
Chạy dòng lệnh sau:
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

---

## 🌐 Hướng Dẫn Sử Dụng Trong Mạng LAN & Quản Lý Đa Profile (Multi-Profile)

Tool hỗ trợ mô hình **1 Máy chủ chạy Tool - Nhiều máy trạm (Client) cùng sử dụng qua mạng LAN**, trong đó mỗi máy/người dùng sử dụng một **Profile Facebook hoàn toàn độc lập**, không dùng chung tài khoản với máy chủ.

### 1. Truy cập từ máy trạm trong mạng LAN
- Đảm bảo máy trạm kết nối cùng mạng Wi-Fi hoặc mạng LAN với máy chủ.
- Trên trình duyệt máy trạm (Chrome, Edge, Cốc Cốc...), truy cập địa chỉ: `http://<IP_MAY_CHU>:8501` (ví dụ: `http://192.168.1.27:8501`).
- *Lưu ý*: Nếu máy trạm không mở được, hãy kiểm tra Firewall trên máy chủ Windows để mở cổng 8501 (xem mục FAQ bên dưới).

### 2. Tạo Profile riêng cho máy của bạn
- Tại thanh Sidebar bên trái, bấm vào mục **"Tạo Profile mới"**.
- Nhập tên đại diện cho bạn hoặc máy của bạn (ví dụ: `may_nam`, `user_linh`, `pc_02`...) rồi bấm **"Tạo Profile"**.
- Chọn Profile vừa tạo trong danh sách chọn Profile.

### 3. Đăng nhập Facebook cho Profile (Chỉ làm 1 lần duy nhất)

Có 2 cách đăng nhập:

#### Cách A: Nhập Cookie trực tiếp từ trình duyệt của bạn (Dành cho máy trạm LAN - Tiện lợi nhất)
Vì Playwright chạy trên máy chủ nên máy trạm trong mạng LAN không thể nhìn thấy cửa sổ trình duyệt pop-up của máy chủ. Cách nhanh nhất và an toàn nhất là xuất Cookie từ trình duyệt của bạn:
1. Trên trình duyệt của bạn (máy cá nhân), đăng nhập tài khoản Facebook bình thường.
2. Cài đặt tiện ích mở rộng miễn phí **[Cookie-Editor](https://cookie-editor.com/)** (hoặc J2TEAM Cookies) trên Chrome/Edge.
3. Khi đang ở trang Facebook, bấm vào icon Cookie-Editor -> bấm **Export** -> chọn **Export as JSON** (hoặc copy giá trị `c_user=...; xs=...`).
4. Quay lại trang Tool Web, mở mục **"📥 Nhập Cookie trực tiếp cho Profile"**.
5. Dán đoạn Cookie vừa copy vào ô văn bản và bấm **"Lưu Cookie vào Profile"**.
6. Hệ thống sẽ lưu phiên vĩnh viễn vào thư mục riêng `browser_profile/profiles/<profile_name>/`. Trạng thái chuyển thành `🟢 Đã có phiên đăng nhập`. Từ các lần cào sau, bạn **không bao giờ phải nhập lại**.

#### Cách B: Mở trình duyệt đăng nhập tương tác (Dành cho người ngồi trực tiếp tại máy chủ)
1. Chọn Profile cần đăng nhập (ví dụ: `default`).
2. Bấm nút **"🔐 Mở trình duyệt đăng nhập Facebook"**.
3. Cửa sổ Chromium bật lên trên màn hình máy chủ, đăng nhập tài khoản Facebook bình thường (hỗ trợ cả 2FA).
4. Đăng nhập xong, đóng trình duyệt lại và bấm **"🔄 Tôi đã đăng nhập xong"**.

### 4. Cơ chế URL Route & Tự động lưu cấu hình (Không lo bị mất khi F5)
- **Tự động gắn route URL**: Khi bạn chọn hoặc tạo Profile, trình duyệt sẽ tự động gắn tham số URL tương ứng: `http://<IP_MAY_CHU>:8501/?profile=<tên_profile>` (ví dụ: `http://192.168.1.27:8501/?profile=may_nam`).
- **Bookmark tiện lợi**: Bạn có thể lưu dấu trang (Bookmark) đường link có gắn `?profile=...` này trên trình duyệt máy bạn để luôn mở đúng tài khoản của mình.
- **Không sợ F5 mất cấu hình**: Mọi thông số thiết lập cào (Số Reels, delay, quét bình luận, headless, link Fanpage nhập gần nhất) và bảng kết quả cào đều được **tự động lưu vào profile**. Khi bấm **F5 (Reload trang)**, toàn bộ trạng thái đăng nhập, thiết lập và kết quả đều được giữ nguyên vẹn 100%!

---

## 📖 Hướng Dẫn Sử Dụng Chi Tiết

Giao diện chính được chia thành 2 chế độ cào chuyên biệt:

### 1. Cào theo Fanpage / Profile URL (Tab 1)
- Chọn tab **"🏢 Cào theo Fanpage / Profile"**.
- Dán đường dẫn Fanpage hoặc Trang cá nhân vào ô nhập liệu:
  - *Dạng Fanpage có username*: `https://www.facebook.com/vtv24news` hoặc `https://www.facebook.com/vtv24news/reels/`
  - *Dạng Profile cá nhân hoặc trang dùng ID*: `https://www.facebook.com/profile.php?id=10006456789` hoặc `https://www.facebook.com/profile.php?id=10006456789&sk=reels_tab`
- Hệ thống sẽ tự động chuẩn hóa URL, điều hướng đến tab Reels của đối tượng, tự động cuộn trang (Infinite Scroll) để quét lấy danh sách Reels mới nhất.
- Bấm nút **"🚀 Bắt đầu cào nội dung"**.

### 2. Cào theo danh sách link Reels lẻ (Tab 2)
- Chọn tab **"🔗 Cào theo danh sách Reels lẻ"**.
- Cung cấp danh sách các link Reels Facebook theo 1 trong 2 cách (hoặc kết hợp cả hai):
  - **Nhập trực tiếp**: Dán các link vào ô Text Area (mỗi dòng một link).
  - **Tải file text**: Bấm tải lên file `.txt` chứa danh sách link (hỗ trợ cả bảng mã UTF-8 và UTF-8 có BOM từ Windows Notepad).
- Hệ thống sẽ tự động gộp dữ liệu, loại bỏ các liên kết trùng lặp và làm sạch định dạng.
- Bấm nút **"🚀 Bắt đầu cào nội dung"**.

### 3. Tùy chỉnh các thông số cào (Sidebar bên trái)
- **Số lượng Reels tối đa**: Giới hạn số lượng video Reels cần xử lý (mặc định 20, có thể chỉnh từ 1 đến 500).
- **Khoảng Delay ngẫu nhiên**: Thời gian nghỉ giữa các thao tác (mặc định 2.0s - 5.0s) nhằm mô phỏng hành vi người dùng thật, giúp chống bị hạn chế tần suất (Rate limit).
- **Quét link trong bình luận**:
  - Bật (khuyên dùng): Nếu Caption không có link bài viết, tool sẽ tự động tìm link ở Top Comments.
  - Tắt: Chỉ tìm kiếm link trong Caption của Reel.
- **Ẩn cửa sổ trình duyệt (Headless)**:
  - Bật (mặc định): Trình duyệt chạy ngầm mượt mà, tiết kiệm tài nguyên máy tính.
  - Tắt: Bật cửa sổ trình duyệt lên để bạn theo dõi trực tiếp các thao tác cào.

### 4. Kiểm soát tiến trình & Nút Dừng cào (Stop)
- Khi bắt đầu cào, thanh tiến trình (Progress Bar) sẽ hiển thị tỷ lệ hoàn thành cùng dòng thông báo trạng thái từng bước (đang tải trang, đang lấy caption, đang bóc tách bài viết...).
- Bảng kết quả xem trước (Live Preview) sẽ cập nhật từng dòng dữ liệu ngay khi vừa cào xong từng Reel.
- **Nút "⏹️ Dừng cào"**: Bạn có thể bấm nút này bất cứ lúc nào nếu muốn dừng sớm. Tool sẽ ngắt vòng lặp an toàn và bảo toàn nguyên vẹn toàn bộ những kết quả đã cào được trước đó.

### 5. Tải và sử dụng file kết quả
Sau khi hoàn tất (hoặc khi dừng cào), bảng kết quả hoàn chỉnh sẽ xuất hiện:
- Bấm nút **"📥 Tải xuống file Excel (.xlsx)"**: Tải về file Excel đã được format đẹp mắt, sẵn sàng để gửi báo cáo hoặc mở bằng Microsoft Excel / Google Sheets.
- Bấm nút **"📥 Tải xuống file CSV (.csv)"**: Tải file dữ liệu dạng CSV (mã hóa chuẩn `utf-8-sig` không bao giờ bị lỗi font tiếng Việt).
- File Excel cũng được tự động lưu một bản sao trong thư mục `output/` của dự án với tên file chứa ngày giờ: `output/reels_content_YYYYMMDD_HHMMSS.xlsx`.

#### Các cột dữ liệu trong file kết quả (khớp chuẩn 9 cột):
| Cột | Ý nghĩa |
| :--- | :--- |
| **STT** | Số thứ tự tăng dần (1, 2, 3...) |
| **Link Reel** | URL video Facebook Reels gốc |
| **Mô tả Reel** | Toàn bộ caption/mô tả của video Reel |
| **Vị trí tìm thấy link** | Vị trí phát hiện link bài viết ("Trong mô tả" hoặc "Trong bình luận") |
| **Link Web** | URL trang web bài viết trích xuất được (đã giải mã link rút gọn) |
| **Tiêu đề bài viết** | Tiêu đề bóc tách được từ trang web bài viết |
| **Nội dung bài viết** | Toàn bộ nội dung văn bản bài viết (đã bật ngắt dòng tự động Wrap Text) |
| **Trạng thái** | Trạng thái xử lý ("Thành công", "Không tìm thấy link web", "Lỗi tải trang web"...) |
| **Thời gian cào** | Ngày giờ hoàn thành bóc tách video (định dạng `YYYY-MM-DD HH:MM:SS`) |

---

## 📁 Cấu Trúc Thư Mục Dự Án

```
Tool_/get_content/
├── app.py                   # Giao diện Web UI chính xây dựng bằng Streamlit
├── fb_crawler.py            # Module cào Facebook Reels & xử lý Playwright
├── article_extractor.py     # Module giải mã URL rút gọn & trích xuất nội dung bài viết
├── exporter.py              # Module xuất dữ liệu ra file Excel (.xlsx) có định dạng
├── config.py                # Cấu hình hệ thống (đường dẫn, User-Agent, timeouts, delay)
├── requirements.txt         # Danh sách các thư viện Python phụ thuộc
├── run.bat                  # Script khởi động nhanh 1-click cho người dùng Windows
├── README.md                # Tài liệu hướng dẫn sử dụng chi tiết (tiếng Việt)
├── browser_profile/         # Thư mục lưu trữ phiên đăng nhập Facebook cục bộ (Playwright)
│   └── profiles/            # Thư mục chứa từng profile riêng cho từng máy con trong mạng LAN
├── output/                  # Thư mục chứa các file Excel kết quả tự động xuất ra
└── tests/                   # Bộ test suite kiểm thử tự động toàn diện (pytest)
    ├── test_app.py
    ├── test_article_extractor.py
    ├── test_config.py
    ├── test_exporter.py
    └── test_fb_crawler.py
```

---

## 🧪 Kiểm Thử Hệ Thống (Test Suite)

Dự án tuân thủ phương pháp phát triển kiểm thử nghiêm ngặt (Test-Driven Development - TDD) với độ phủ toàn diện trên tất cả các module.

Để chạy toàn bộ bộ kiểm thử:
```bash
pytest tests/ -v
```

Kết quả: **61/61 test cases vượt qua (100% Passed)**.

---

## 💡 Câu Hỏi Thường Gặp & Xử Lý Sự Cố (FAQ & Troubleshooting)

### 1. Máy trạm trong mạng LAN không vào được Web qua `http://<IP_MAY_CHU>:8501`?
- **Nguyên nhân**: Tường lửa Windows (Windows Defender Firewall) trên máy chủ đang chặn cổng kết nối đến 8501.
- **Cách khắc phục**: Mở PowerShell với quyền Administrator trên máy chủ và chạy câu lệnh sau để mở cổng:
  ```powershell
  New-NetFirewallRule -DisplayName "Streamlit LAN Port 8501" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
  ```
- Hoặc vào **Windows Defender Firewall** -> **Advanced Settings** -> **Inbound Rules** -> **New Rule** -> Chọn **Port** -> **TCP 8501** -> **Allow the connection**.

### 2. Báo lỗi `Executable doesn't exist at ... chromium` khi bấm cào?
- **Nguyên nhân**: Bạn chưa tải trình duyệt Chromium cho Playwright.
- **Cách khắc phục**: Chạy lệnh `playwright install chromium` trong Terminal hoặc Command Prompt rồi khởi động lại tool.

### 3. Làm thế nào để đổi sang tài khoản Facebook khác hoặc xóa Profile?
- **Cách 1**: Trên Sidebar, chọn Profile tương ứng rồi bấm **"🗑️ Xóa Profile"** hoặc bấm **"🔐 Mở trình duyệt đăng nhập Facebook"** để đăng xuất và đăng nhập lại.
- **Cách 2**: Nhập Cookie mới vào ô **"📥 Nhập Cookie trực tiếp cho Profile"** và bấm lưu để ghi đè.

### 4. Một số bài viết không lấy được nội dung (Nội dung rỗng hoặc ghi lỗi)?
- **Nguyên nhân**: Một số trang web báo chí/blog kích hoạt tường lửa chống bot (Cloudflare Turnstile, Cloudflare WAF) hoặc yêu cầu trả phí đọc báo (Paywall).
- **Xử lý**: Tool tự động ghi nhận trạng thái vào cột **Trạng thái** trong file Excel để người dùng dễ dàng lọc và kiểm tra thủ công.

### 5. Bị lỗi hiển thị tiếng Việt khi mở file CSV trong Excel?
- Nút tải file CSV của tool đã được cấu hình bảng mã `utf-8-sig` (chứa ký tự Byte Order Mark) đặc trị lỗi hiển thị tiếng Việt trên Microsoft Excel. Tuy nhiên, khuyên dùng file **.xlsx** để có trải nghiệm hiển thị và định dạng cột đẹp nhất.

---

## 📄 Bản Quyền & Giấy Phép

Dự án được xây dựng phục vụ mục đích nghiên cứu, học tập và tự động hóa trích xuất nội dung phục vụ công việc. Vui lòng tuân thủ điều khoản dịch vụ của các nền tảng mạng xã hội và bản quyền nội dung báo chí khi sử dụng dữ liệu.
