# Thiết kế Kỹ thuật: Facebook Reels & Article Content Extractor Tool

- **Ngày tạo**: 2026-09-28
- **Tác giả**: Antigravity & User
- **Trạng thái**: Đã phê duyệt thiết kế (Design Approved)

---

## 1. Giới thiệu & Mục tiêu (Problem & Goals)

### 1.1. Bối cảnh
Người dùng cần một công cụ tự động để:
1. Thu thập danh sách các video Reels từ một Trang Facebook (Fanpage/Profile) hoặc từ một danh sách các link video Reels lẻ có sẵn.
2. Trích xuất thông tin chi tiết từng video: Link video Reel, phần mô tả (caption/description).
3. Tìm kiếm đường dẫn trang web (external website URL) gắn liền với video đó (nằm trong phần mô tả hoặc trong phần bình luận/comment ghim).
4. Tự động truy cập vào trang web đích đó, bóc tách toàn bộ tiêu đề và nội dung bài viết chính (loại bỏ quảng cáo, rác, thanh điều hướng).
5. Xuất toàn bộ dữ liệu đã tổng hợp ra file Excel (`.xlsx`) và CSV có định dạng thẩm mỹ, dễ đọc.
6. Cung cấp giao diện Web trực quan (Streamlit) dễ dàng thao tác, theo dõi tiến trình trực tiếp (real-time) và tải file kết quả.

### 1.2. Mục tiêu kỹ thuật
- **Ổn định cao, chống checkpoint/block**: Sử dụng Playwright với profile trình duyệt thật (Persistent Context) để người dùng đăng nhập tài khoản một lần, các lần sau tự động kế thừa phiên đăng nhập mà không cần đăng nhập lại.
- **Linh hoạt đầu vào**: Hỗ trợ mọi định dạng link Facebook (Profile ID `...&sk=reels_tab`, Fanpage username `.../reels/`, link trang chủ tự chuyển hướng, hoặc danh sách link Reel lẻ).
- **Trích xuất thông minh**: Sử dụng thư viện `trafilatura` chuyên dụng để bóc tách bài viết từ bất kỳ website tin tức/blog nào với độ chính xác cao.
- **Trải nghiệm người dùng tốt**: Giao diện Streamlit có nút mở trình duyệt đăng nhập, thanh tiến trình %, bảng cập nhật dữ liệu trực tiếp khi đang chạy và nút tải file 1-click.

---

## 2. Kiến trúc Hệ thống (System Architecture)

### 2.1. Cấu trúc thư mục dự án
```text
get_content/
├── app.py                      # Giao diện chính Streamlit Web UI
├── config.py                   # Cấu hình hệ thống (paths, delays, timeouts)
├── fb_crawler.py               # Module tự động hóa cào Facebook Reels bằng Playwright
├── article_extractor.py        # Module bóc tách nội dung bài viết từ link web (Trafilatura)
├── exporter.py                 # Module định dạng và xuất dữ liệu ra Excel (.xlsx / .csv)
├── browser_profile/            # Thư mục lưu phiên đăng nhập Facebook của người dùng
├── output/                     # Thư mục lưu trữ các file Excel kết quả
├── requirements.txt            # Danh sách thư viện Python phụ thuộc
├── run.bat                     # File thực thi 1-click trên Windows
└── docs/                       # Tài liệu kỹ thuật và thiết kế
```

### 2.2. Sơ đồ luồng dữ liệu (Data Flow)
```mermaid
flowchart TD
    User([Người dùng]) -->|1. Cấu hình & Nhập link| UI[Giao diện Streamlit - app.py]
    UI -->|2. Kiểm tra/Mở đăng nhập| SessionMgr[Quản lý phiên - browser_profile]
    UI -->|3. Khởi chạy cào| Crawler[fb_crawler.py - Playwright]
    
    subgraph Facebook Crawler
        Crawler -->|Chuẩn hóa link| URLNorm[normalize_reels_url]
        URLNorm -->|Lướt Reels Tab| ReelsList[Thu thập danh sách Reel URLs]
        ReelsList -->|Với từng Reel| ReelPage[Truy cập trang Reel]
        ReelPage -->|Bóc caption & Regex| ExtractCaption[Lấy Caption & tìm URL]
        ExtractCaption -->|Không thấy link?| CheckComments[Mở bình luận & tìm URL]
    end
    
    Facebook Crawler -->|4. Trả về Link Web| Extractor[article_extractor.py]
    
    subgraph Web Article Extractor
        Extractor -->|Giải mã redirect| ResolvLink[Resolve shortlink]
        ResolvLink -->|Trafilatura fetch| ParseArticle[Bóc tách Tiêu đề & Nội dung chính]
        ParseArticle -->|Fallback nếu trang SPA| PWFallback[Playwright render fallback]
    end
    
    Web Article Extractor -->|5. Dòng dữ liệu hoàn chỉnh| StreamlitState[Cập nhật Real-time bảng UI]
    StreamlitState -->|6. Xuất dữ liệu| Exporter[exporter.py]
    Exporter -->|Lưu file| ExcelFile[output/*.xlsx & Nút Download UI]
```

---

## 3. Chi tiết các Module chức năng

### 3.1. Module `config.py`
Chứa các hằng số và cấu hình mặc định:
- `PROFILE_DIR`: Đường dẫn tới thư mục `browser_profile/`.
- `OUTPUT_DIR`: Đường dẫn tới thư mục `output/`.
- `DEFAULT_MAX_REELS`: Số video mặc định cần cào (20).
- `MIN_DELAY`, `MAX_DELAY`: Khoảng thời gian nghỉ ngẫu nhiên giữa các thao tác (2 - 5 giây).
- `REQUEST_TIMEOUT`: Timeout cho tải trang web (15 giây).
- `USER_AGENT`: User-Agent trình duyệt hiện đại.

### 3.2. Module `fb_crawler.py`
Chịu trách nhiệm tương tác và trích xuất dữ liệu từ Facebook:
1. **`launch_login_browser()`**:
   - Khởi chạy Chromium không headless với persistent context lưu tại `browser_profile/`.
   - Điều hướng tới `https://www.facebook.com`.
   - Giữ trình duyệt mở để người dùng đăng nhập tài khoản. Khi người dùng đóng trình duyệt, phiên đăng nhập được lưu lại trọn vẹn.
2. **`is_logged_in()`**:
   - Kiểm tra xem trong `browser_profile/` đã có dữ liệu đăng nhập hay chưa (kiểm tra cookie c_user / datr).
3. **`normalize_reels_url(input_url: str) -> str`**:
   - Xử lý link dạng ID: `facebook.com/profile.php?id=123...` -> `facebook.com/profile.php?id=123...&sk=reels_tab`.
   - Xử lý link dạng Username: `facebook.com/username` -> `facebook.com/username/reels/`.
   - Giữ nguyên các link đã ở tab reels sẵn (`...&sk=reels_tab`, `.../reels/`, `.../reels`).
4. **`collect_reels_from_page(page, reels_url, max_count)`**:
   - Truy cập vào trang Reels.
   - Giả lập hành vi cuộn chuột tự nhiên (human-like scrolling) và chờ nội dung tải thêm.
   - Thu thập các phần tử chứa link Reel dạng `https://www.facebook.com/reel/<id>`.
   - Loại bỏ trùng lặp và dừng khi đạt `max_count` hoặc hết video.
5. **`extract_reel_details(page, reel_url, check_comments=True)`**:
   - Mở link Reel.
   - Trích xuất toàn bộ text trong vùng mô tả (caption).
   - Dùng Regex tìm URL hợp lệ bên trong caption (bỏ qua domain `facebook.com`, `fb.watch`).
   - Nếu không thấy URL và `check_comments=True`:
     - Click mở bảng bình luận (nếu chưa mở).
     - Quét nội dung các bình luận đầu tiên / bình luận được ghim.
     - Tìm URL trong nội dung bình luận.
   - Trả về: `{"reel_url": reel_url, "caption": caption, "found_in": "caption"|"comment"|"none", "target_url": target_url}`.

### 3.3. Module `article_extractor.py`
Chịu trách nhiệm bóc tách nội dung trang web đích:
1. **`resolve_target_url(url: str) -> str`**:
   - Sử dụng `httpx` hoặc `requests` theo dõi redirect để chuyển các link rút gọn (`bit.ly`, `tinyurl`, `fb.me`...) về link bài viết thực sự.
2. **`extract_article(url: str) -> dict`**:
   - Dùng `trafilatura.fetch_url(url)` và `trafilatura.extract(html, include_links=False, output_format='txt')`.
   - Lấy tiêu đề bài viết thông qua `trafilatura.extract_metadata(html).title` hoặc fallback thẻ `<title>`, `<meta property="og:title">`.
   - Lấy nội dung bài viết sạch (`article_text`).
   - **Cơ chế Fallback**: Nếu trang yêu cầu JavaScript hoặc chặn bot HTTP, sử dụng Playwright headless để render DOM và bóc tách.
   - Trả về: `{"title": title, "content": content, "status": "Thành công"|"Lỗi tải trang web"}`.

### 3.4. Module `exporter.py`
Chịu trách nhiệm định dạng và xuất file Excel:
- Tạo DataFrame với các cột:
  1. `STT` (Số thứ tự)
  2. `Link Reel`
  3. `Mô tả Reel`
  4. `Vị trí tìm thấy link`
  5. `Link Web`
  6. `Tiêu đề bài viết`
  7. `Nội dung bài viết`
  8. `Trạng thái`
  9. `Thời gian cào`
- Định dạng qua `openpyxl`:
  - Căn chỉnh độ rộng cột tự động và cài đặt cột "Nội dung bài viết" rộng 60 đơn vị, bật `wrap_text=True`.
  - Hàng tiêu đề in đậm, nền xanh navy / xanh lá nhạt, chữ nổi bật.
  - Freeze pane hàng đầu tiên (tiêu đề luôn cố định khi cuộn xuống).
  - Xuất ra file Excel `.xlsx` và tạo buffer tải về cho Streamlit.

### 3.5. Module `app.py` (Streamlit Web UI)
Giao diện người dùng hoàn chỉnh:
- **Sidebar**:
  - Trạng thái đăng nhập (Đã đăng nhập / Chưa đăng nhập).
  - Nút *" Mở trình duyệt đăng nhập Facebook"*.
  - Bộ chỉnh số lượng Reel tối đa, khoảng delay giữa các video, checkbox cào bình luận, chế độ chạy ẩn (headless) hay hiện cửa sổ.
- **Main View**:
  - Tab 1: Cào theo Fanpage/Profile.
  - Tab 2: Cào theo danh sách link Reel lẻ.
  - Nút *" Bắt đầu lấy nội dung"* và *" Dừng lại"*.
  - Tiến trình cào: Thanh Progress Bar + nhãn trạng thái theo thời gian thực.
  - Bảng dữ liệu: Cập nhật trực tiếp từng dòng dữ liệu ngay khi hoàn thành bóc tách video đó.
  - Khu vực tải file: Nút bấm tải file Excel và CSV sau khi chạy xong.

---

## 4. Xử lý lỗi & Chống chặn (Error Handling & Anti-Bot)

| Tình huống | Phương án xử lý |
| :--- | :--- |
| **Facebook chặn bot không đăng nhập** | Bắt buộc chạy trên profile thực tế của người dùng (`browser_profile/`), mang đầy đủ cookie, fingerprint trình duyệt thực. |
| **Tần suất request quá nhanh** | Sử dụng thời gian trễ ngẫu nhiên (`random.uniform(min_delay, max_delay)`) giữa các thao tác cuộn và mở video. |
| **Link Reel không có link web trong mô tả** | Tự động mở bình luận kiểm tra bình luận ghim hoặc bình luận đầu của tác giả. Nếu vẫn không có, đánh dấu trạng thái "Không có link web". |
| **Link web đích là link rút gọn** | Resolve redirect qua HTTP HEAD/GET để lấy URL cuối cùng trước khi bóc tách bài viết. |
| **Trang web đích chặn cào tĩnh (Cloudflare/SPA)** | Chuyển đổi sang cơ chế Playwright headless render DOM để lấy nội dung. |
| **Lỗi mạng / Trang web 404** | Ghi nhận lỗi vào cột "Trạng thái", tiếp tục xử lý các Reel tiếp theo mà không làm crash ứng dụng. |

---

## 5. Kế hoạch Kiểm thử (Testing Plan)
1. **Kiểm thử chuẩn hóa URL (`normalize_reels_url`)**:
   - Kiểm thử với định dạng Profile ID (`...profile.php?id=61593414350410`).
   - Kiểm thử với định dạng Username (`...facebook.com/tenpage`).
   - Kiểm thử với link tab reels trực tiếp (`...&sk=reels_tab`).
2. **Kiểm thử bóc tách link Regex**:
   - Trích xuất chính xác URL bên trong mô tả có chứa nhiều text và ký tự đặc biệt, lọc bỏ link nội bộ Facebook.
3. **Kiểm thử bóc tách bài viết (`article_extractor`)**:
   - Kiểm thử với các trang báo phổ biến (VnExpress, Dân Trí, Tuổi Trẻ, blog cá nhân...).
4. **Kiểm thử xuất file Excel (`exporter`)**:
   - Kiểm tra định dạng wrap text, độ rộng cột, font chữ tiếng Việt không bị lỗi font.
5. **Kiểm thử tích hợp trên giao diện Streamlit**:
   - Chạy thử nghiệm cào thực tế từ 1 Page Facebook và tải file kết quả.
