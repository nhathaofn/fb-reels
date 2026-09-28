# Facebook Reels & Article Content Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng tool hoàn chỉnh thu thập video Reels từ Facebook (qua Fanpage/Profile hoặc danh sách link lẻ), trích xuất link trang web từ mô tả/bình luận, tự động bóc tách tiêu đề và nội dung bài viết bằng Trafilatura, xuất ra file Excel (.xlsx), điều khiển qua giao diện Web UI Streamlit.

**Architecture:** Kiến trúc module hóa tách biệt: `fb_crawler.py` (Playwright persistent profile tự động hóa cào Facebook), `article_extractor.py` (Trafilatura + HTTP client bóc tách bài viết), `exporter.py` (Pandas + Openpyxl xuất file Excel căn chỉnh đẹp mắt), `config.py` (cấu hình tập trung), và `app.py` (Giao diện Streamlit Web UI thời gian thực).

**Tech Stack:** Python 3.13, Playwright, Trafilatura, Streamlit, Pandas, Openpyxl, Httpx, Pytest.

**Spec:** [2026-09-28-fb-reels-article-extractor-design.md](file:///d:/nhathao/1_code/Tool_/get_content/docs/superpowers/specs/2026-09-28-fb-reels-article-extractor-design.md)

## Global Constraints

- HĐH: Windows, Shell: PowerShell, Python: 3.13.14.
- Đăng nhập Facebook: Phải hỗ trợ profile người dùng thực tế (`browser_profile/`) qua Playwright để chống bot/checkpoint.
- Xử lý link Facebook: Hỗ trợ linh hoạt cả link Profile ID (`profile.php?id=...&sk=reels_tab`), link Vanity Username (`.../reels/`), và danh sách link Reel lẻ (`.../reel/<id>`).
- Cột xuất Excel: `STT`, `Link Reel`, `Mô tả Reel`, `Vị trí tìm thấy link`, `Link Web`, `Tiêu đề bài viết`, `Nội dung bài viết`, `Trạng thái`, `Thời gian cào`. Cột nội dung tự động xuống dòng (`wrap_text=True`).

---

### Task 1: Thiết lập môi trường & Module cấu hình (`config.py`)

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `config.BASE_DIR: Path`
  - `config.PROFILE_DIR: Path`
  - `config.OUTPUT_DIR: Path`
  - `config.DEFAULT_MAX_REELS: int`
  - `config.MIN_DELAY: float`, `config.MAX_DELAY: float`
  - `config.USER_AGENT: str`

- [ ] **Step 1: Viết test kiểm tra cấu hình**
- [ ] **Step 2: Chạy test để xác nhận fail**
- [ ] **Step 3: Viết file `requirements.txt` và cài đặt thư viện**
- [ ] **Step 4: Viết file `config.py`**
- [ ] **Step 5: Chạy lại test để xác nhận pass**
- [ ] **Step 6: Commit code**

---

### Task 2: Module bóc tách nội dung bài viết (`article_extractor.py`)

**Files:**
- Create: `article_extractor.py`
- Test: `tests/test_article_extractor.py`

**Interfaces:**
- Produces:
  - `resolve_target_url(url: str, timeout: float = 15.0) -> str`
  - `extract_article_from_html(html: str, url: str = "") -> dict`
  - `extract_article(url: str, timeout: float = 15.0) -> dict`

- [ ] **Step 1: Viết test cho `article_extractor`**
- [ ] **Step 2: Chạy test để xác nhận fail**
- [ ] **Step 3: Viết mã nguồn cho `article_extractor.py`**
- [ ] **Step 4: Chạy test để xác nhận pass**
- [ ] **Step 5: Commit code**

---

### Task 3: Module định dạng và xuất file Excel (`exporter.py`)

**Files:**
- Create: `exporter.py`
- Test: `tests/test_exporter.py`

**Interfaces:**
- Produces:
  - `export_to_excel(records: list[dict], output_filepath: Path | str | None = None) -> Path`
  - `get_excel_bytes(records: list[dict]) -> bytes`

- [ ] **Step 1: Viết test cho `exporter`**
- [ ] **Step 2: Chạy test để xác nhận fail**
- [ ] **Step 3: Viết mã nguồn cho `exporter.py`**
- [ ] **Step 4: Chạy test để xác nhận pass**
- [ ] **Step 5: Commit code**

---

### Task 4: Module Facebook Reels Crawler & Link Normalizer (`fb_crawler.py`)

**Files:**
- Create: `fb_crawler.py`
- Test: `tests/test_fb_crawler.py`

**Interfaces:**
- Produces:
  - `normalize_reels_url(input_url: str) -> str`
  - `extract_urls_from_text(text: str) -> list[str]`
  - `launch_login_browser(headless: bool = False) -> None`
  - `has_logged_in_session() -> bool`
  - `crawl_reels(...)`

- [ ] **Step 1: Viết test cho `normalize_reels_url` và `extract_urls_from_text`**
- [ ] **Step 2: Chạy test để xác nhận fail**
- [ ] **Step 3: Viết mã nguồn cho `fb_crawler.py`**
- [ ] **Step 4: Chạy test để xác nhận pass**
- [ ] **Step 5: Commit code**

---

### Task 5: Xây dựng Giao diện Web UI Streamlit (`app.py` & `run.bat`)

**Files:**
- Create: `app.py`
- Create: `run.bat`

- [ ] **Step 1: Viết file giao diện Streamlit `app.py`**
- [ ] **Step 2: Viết script `run.bat`**
- [ ] **Step 3: Chạy thử nghiệm cú pháp và khởi chạy thử Streamlit**
- [ ] **Step 4: Commit code**

---

### Task 6: Kiểm thử tổng thể & Hướng dẫn sử dụng

**Files:**
- Create: `README.md`
- Test: Chạy toàn bộ test suite `pytest tests/`

- [ ] **Step 1: Chạy toàn bộ test suite**
- [ ] **Step 2: Viết tài liệu `README.md`**
- [ ] **Step 3: Commit code và hoàn tất**
