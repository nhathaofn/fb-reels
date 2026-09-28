# Kế hoạch Chuyển Đổi sang Đánh Chặn Mạng GraphQL & Xóa Bỏ Hardcode

> **Phương pháp thực thi**: Tuân thủ quy trình kiểm thử và chất lượng của Superpowers. Các bước được tổ chức thành các tác vụ độc lập, kiểm thử đơn vị trước khi ghép nối vào hệ thống.

**Mục tiêu:** Chuyển đổi toàn diện cơ chế cào dữ liệu Reels sang Phương án 1 (Network Response Interception - Đánh chặn GraphQL API), kết hợp Condition-Based Waiting và chuẩn hóa Regex phổ quát, xóa bỏ hoàn toàn các đoạn mã hardcode (chuỗi giao diện, delay cố định `time.sleep`, danh sách đuôi tên miền hạn chế).

**Kiến trúc:** 
1. **Network Interceptor Layer**: Lắng nghe sự kiện `page.on("response")` để thu thập payload GraphQL từ Facebook (`FBUnifiedVideoFeedbackRightRailWithCommentPreloadingQuery`, `PolarisReelCommentsQuery`, `VideoReelViewerQuery`).
2. **GraphQL Parser Engine**: Trích xuất đệ quy tiêu đề, mô tả, bình luận và liên kết ngoài đính kèm từ cây JSON có cấu trúc mà không cần phụ thuộc vào cấu trúc DOM hay ngôn ngữ hiển thị.
3. **Adaptive Condition Waiting**: Thay thế hoàn toàn `time.sleep(2.5)` bằng vòng lặp chờ theo điều kiện (Condition-based polling) với timeout linh hoạt.
4. **Universal URL Helper**: Mở rộng Regex phát hiện URL theo tiêu chuẩn IANA, xóa bỏ danh sách cứng các TLD.

**Công nghệ sử dụng:** Playwright Sync API, Python 3.13, JSON, urllib.parse, Pytest, Trafilatura.

---

## Global Constraints
- Không được phá vỡ giao diện CustomTkinter Desktop (`DesktopApp`).
- Đảm bảo tất cả 58 bài kiểm thử hiện có tiếp tục vượt qua 100%.
- Không dùng `time.sleep(...)` cố định để chờ dữ liệu mạng; mọi tác vụ chờ mạng phải dùng Condition Polling với timeout.
- Không dùng danh sách TLD hardcode trong nhận diện URL.
- Không dùng chuỗi ngôn ngữ cố định (như "Bình luận", "Comment") làm điều kiện duy nhất để tương tác; kết hợp selector thuộc tính, SVG icon và API response.

---

### Task 1: Nâng cấp `url_helper.py` thành Universal URL Parser (Xóa bỏ Hardcode TLD)

**Files:**
- Modify: `src/utils/url_helper.py:4-26, 60-91`
- Test: `tests/test_url_helper.py`

**Interfaces:**
- Consumes: Chuỗi văn bản bất kỳ (caption, comment, raw string).
- Produces: `extract_urls_from_text(text: str) -> list[str]`: Danh sách liên kết hợp lệ, loại bỏ liên kết nội bộ Facebook/Meta, giải mã `l.facebook.com/l.php?u=...`.

- [x] **Step 1: Viết test mở rộng cho `test_url_helper.py` kiểm tra các TLD mới và định dạng không hardcode**
- [x] **Step 2: Chạy test để xác nhận kiểm thử thất bại với code hiện tại**
- [x] **Step 3: Cập nhật `src/utils/url_helper.py` sử dụng Regex phổ quát theo chuẩn IANA**
- [x] **Step 4: Chạy lại toàn bộ test suite của `test_url_helper.py`**

---

### Task 2: Xây dựng Module Phân Tích Dữ Liệu GraphQL (`graphql_parser.py`)

**Files:**
- Create: `src/core/graphql_parser.py`
- Test: `tests/test_graphql_parser.py`

**Interfaces:**
- Consumes: Chuỗi payload NDJSON trả về từ Facebook GraphQL API (`api/graphql/`).
- Produces: `parse_graphql_payload(raw_text: str) -> dict`: Trả về dict gồm `{"caption": str, "target_urls": list[str], "found_in": str}`.

- [x] **Step 1: Viết test cho `parse_graphql_payload` trong `tests/test_graphql_parser.py`**
- [x] **Step 2: Chạy test xác nhận FAIL khi file chưa tồn tại**
- [x] **Step 3: Tạo `src/core/graphql_parser.py` với thuật toán duyệt cây JSON đệ quy**
- [x] **Step 4: Chạy lại test `tests/test_graphql_parser.py`**

---

### Task 3: Tái cấu trúc `extract_single_reel` với Network Interceptor & Condition-Based Waiting

**Files:**
- Modify: `src/core/fb_crawler.py:451-725`
- Test: `tests/test_fb_crawler.py`

**Interfaces:**
- Consumes: `page` (Playwright Page), `reel_url` (str), `check_comments` (bool), `delay_range` (tuple).
- Produces: `extract_single_reel(...) -> dict` với dữ liệu bóc tách đầy đủ (reel_url, caption, found_in, target_url, title, content, status).

- [x] **Step 1: Bổ sung lắng nghe sự kiện `page.on("response", ...)` trong `extract_single_reel`**
- [x] **Step 2: Tích hợp `parse_graphql_payload` để lấy thông tin từ tầng mạng ngay lập tức**
- [x] **Step 3: Thay thế `b.click()` JS thô sơ bằng Native Locator Click và Condition Polling**
- [x] **Step 4: Chạy kiểm thử đơn vị `tests/test_fb_crawler.py`**

---

### Task 4: Tối ưu Thuật toán Cuộn Tab Reels (`crawl_reels_from_tab`) - Chống Dừng Non

**Files:**
- Modify: `src/core/fb_crawler.py:319-450`
- Test: `tests/test_fb_crawler.py`

**Interfaces:**
- Consumes: `page`, `reels_url`, `max_count`, `delay_range`, `crawl_order`.
- Produces: Danh sách các link video Reels đã chuẩn hóa.

- [x] **Step 1: Cải tiến logic phát hiện đáy trang**
- [x] **Step 2: Chạy kiểm thử `tests/test_fb_crawler.py`**

---

### Task 5: Kiểm thử Toàn Diện Hệ Thống (End-to-End Test Suite & Real Reel Verification)

**Files:**
- Test: `tests/` (toàn bộ 9 file test)
- Execution script: Kiểm thử cào trực tiếp 2 Reel thực tế `1081251921258536` và `1128966652805682`.

- [x] **Step 1: Chạy toàn bộ test suite Pytest để đảm bảo không phát sinh regression**
- [x] **Step 2: Chạy kiểm thử End-to-End với 2 URL thực tế của người dùng**
- [x] **Step 3: Dọn dẹp các file scratch tạm thời trong quá trình debug**
