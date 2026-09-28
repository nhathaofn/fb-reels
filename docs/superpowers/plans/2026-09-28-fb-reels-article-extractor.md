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

Tạo file `tests/test_config.py`:
```python
from pathlib import Path
import config

def test_config_paths_and_defaults():
    assert isinstance(config.BASE_DIR, Path)
    assert isinstance(config.PROFILE_DIR, Path)
    assert isinstance(config.OUTPUT_DIR, Path)
    assert config.DEFAULT_MAX_REELS > 0
    assert 0 < config.MIN_DELAY <= config.MAX_DELAY
    assert "Mozilla" in config.USER_AGENT
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (chưa có module `config` hoặc `pytest`).

- [ ] **Step 3: Viết file `requirements.txt` và cài đặt thư viện**

Tạo file `requirements.txt`:
```text
playwright>=1.49.0
trafilatura>=2.0.0
streamlit>=1.40.0
pandas>=2.2.0
openpyxl>=3.1.0
httpx>=0.28.0
pytest>=8.0.0
```

Chạy lệnh cài đặt:
`pip install -r requirements.txt`
`playwright install chromium`

- [ ] **Step 4: Viết file `config.py`**

Tạo file `config.py`:
```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "browser_profile"
OUTPUT_DIR = BASE_DIR / "output"

# Đảm bảo các thư mục tồn tại
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MAX_REELS = 20
MIN_DELAY = 2.0
MAX_DELAY = 5.0
REQUEST_TIMEOUT = 15.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)
```

- [ ] **Step 5: Chạy lại test để xác nhận pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit code**

```bash
git add requirements.txt config.py tests/test_config.py
git commit -m "feat: setup project environment and config module"
```

---

### Task 2: Module bóc tách nội dung bài viết (`article_extractor.py`)

**Files:**
- Create: `article_extractor.py`
- Test: `tests/test_article_extractor.py`

**Interfaces:**
- Produces:
  - `resolve_target_url(url: str, timeout: float = 15.0) -> str`
  - `extract_article_from_html(html: str, url: str = "") -> dict`
  - `extract_article(url: str, timeout: float = 15.0) -> dict` (trả về `{"title": str, "content": str, "status": str}`)

- [ ] **Step 1: Viết test cho `article_extractor`**

Tạo file `tests/test_article_extractor.py`:
```python
from article_extractor import extract_article_from_html, resolve_target_url

def test_extract_article_from_html():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tiêu đề bài viết mẫu</title>
        <meta property="og:title" content="Tiêu đề bài viết mẫu" />
    </head>
    <body>
        <header><nav>Menu rác</nav></header>
        <main>
            <h1>Tiêu đề bài viết mẫu</h1>
            <p>Đây là đoạn văn bản nội dung chính thứ nhất của bài viết chia sẻ kiến thức.</p>
            <p>Đây là đoạn văn bản thứ hai giải thích chi tiết về cách thức triển khai tool.</p>
        </main>
        <footer>Bản quyền 2026</footer>
    </body>
    </html>
    """
    result = extract_article_from_html(sample_html, "https://example.com/bai-viet")
    assert result["status"] == "Thành công"
    assert "Tiêu đề bài viết mẫu" in result["title"]
    assert "đoạn văn bản nội dung chính thứ nhất" in result["content"]

def test_extract_empty_or_invalid():
    result = extract_article_from_html("<html><body></body></html>", "https://example.com/empty")
    assert result["status"] == "Không có nội dung bài viết" or result["content"] == ""
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `pytest tests/test_article_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'article_extractor'`.

- [ ] **Step 3: Viết mã nguồn cho `article_extractor.py`**

Tạo file `article_extractor.py`:
```python
import logging
import httpx
import trafilatura
from bs4 import BeautifulSoup
from config import USER_AGENT, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

def resolve_target_url(url: str, timeout: float = REQUEST_TIMEOUT) -> str:
    """Theo dõi chuyển hướng (redirect) để lấy link đích thực tế."""
    if not url:
        return ""
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.head(url)
            return str(resp.url)
    except Exception:
        # Fallback thử qua GET nếu server từ chối HEAD
        try:
            with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
                resp = client.get(url)
                return str(resp.url)
        except Exception as e:
            logger.warning(f"Không thể resolve link {url}: {e}")
            return url

def extract_article_from_html(html: str, url: str = "") -> dict:
    """Bóc tách tiêu đề và nội dung bài viết từ mã HTML bằng Trafilatura."""
    if not html:
        return {"title": "", "content": "", "status": "HTML rỗng"}
    
    # 1. Trích xuất nội dung văn bản chính
    extracted_text = trafilatura.extract(
        html,
        include_links=False,
        include_images=False,
        output_format="txt",
        url=url
    )
    
    # 2. Trích xuất metadata (tiêu đề)
    title = ""
    metadata = trafilatura.extract_metadata(html, default_url=url)
    if metadata and metadata.title:
        title = metadata.title.strip()
    
    # Fallback tiêu đề qua thẻ <title> hoặc og:title nếu trafilatura chưa lấy được
    if not title:
        soup = BeautifulSoup(html, "html.parser")
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

    if not extracted_text:
        return {
            "title": title,
            "content": "",
            "status": "Không có nội dung bài viết"
        }

    return {
        "title": title,
        "content": extracted_text.strip(),
        "status": "Thành công"
    }

def extract_article(url: str, timeout: float = REQUEST_TIMEOUT) -> dict:
    """Tải và bóc tách bài viết từ URL web đích."""
    if not url:
        return {"title": "", "content": "", "status": "Không có link web"}
    
    final_url = resolve_target_url(url, timeout=timeout)
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.get(final_url)
            if resp.status_code >= 400:
                return {
                    "title": "",
                    "content": "",
                    "status": f"Lỗi HTTP {resp.status_code}"
                }
            html = resp.text
            return extract_article_from_html(html, final_url)
    except Exception as e:
        logger.error(f"Lỗi khi tải trang {final_url}: {e}")
        return {
            "title": "",
            "content": "",
            "status": f"Lỗi tải trang ({type(e).__name__})"
        }
```

- [ ] **Step 4: Chạy test để xác nhận pass**

Run: `pytest tests/test_article_extractor.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit code**

```bash
git add article_extractor.py tests/test_article_extractor.py
git commit -m "feat: implement article content extraction using Trafilatura"
```

---

### Task 3: Module định dạng và xuất file Excel (`exporter.py`)

**Files:**
- Create: `exporter.py`
- Test: `tests/test_exporter.py`

**Interfaces:**
- Produces:
  - `export_to_excel(records: list[dict], output_filepath: Path | str | None = None) -> Path`
  - `get_excel_bytes(records: list[dict]) -> bytes` (dùng cho nút download trên Streamlit)

- [ ] **Step 1: Viết test cho `exporter`**

Tạo file `tests/test_exporter.py`:
```python
from pathlib import Path
import openpyxl
from exporter import export_to_excel, get_excel_bytes

def test_export_to_excel(tmp_path):
    sample_records = [
        {
            "reel_url": "https://www.facebook.com/reel/111",
            "caption": "Mô tả video 1 có link https://tintuc.vn/1",
            "found_in": "Mô tả",
            "target_url": "https://tintuc.vn/1",
            "title": "Tiêu đề tin tức 1",
            "content": "Nội dung chi tiết bài viết 1...",
            "status": "Thành công",
            "scraped_at": "2026-09-28 08:30:00"
        }
    ]
    out_file = tmp_path / "test_result.xlsx"
    saved_path = export_to_excel(sample_records, out_file)
    assert Path(saved_path).exists()
    
    # Kiểm tra nội dung và cột trong file Excel
    wb = openpyxl.load_workbook(saved_path)
    sheet = wb.active
    headers = [cell.value for cell in sheet[1]]
    assert "Link Reel" in headers
    assert "Tiêu đề bài viết" in headers
    assert "Nội dung bài viết" in headers
    assert sheet.cell(row=2, column= headers.index("Tiêu đề bài viết") + 1).value == "Tiêu đề tin tức 1"

def test_get_excel_bytes():
    sample_records = [{"reel_url": "https://www.facebook.com/reel/222"}]
    data_bytes = get_excel_bytes(sample_records)
    assert isinstance(data_bytes, bytes)
    assert len(data_bytes) > 0
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `pytest tests/test_exporter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exporter'`.

- [ ] **Step 3: Viết mã nguồn cho `exporter.py`**

Tạo file `exporter.py`:
```python
from datetime import datetime
from io import BytesIO
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd
from config import OUTPUT_DIR

COLUMNS_MAP = {
    "stt": "STT",
    "reel_url": "Link Reel",
    "caption": "Mô tả Reel",
    "found_in": "Vị trí tìm thấy link",
    "target_url": "Link Web",
    "title": "Tiêu đề bài viết",
    "content": "Nội dung bài viết",
    "status": "Trạng thái",
    "scraped_at": "Thời gian cào"
}

def _build_formatted_workbook(records: list[dict]) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Facebook Reels Content"
    
    # 1. Ghi header
    headers = list(COLUMNS_MAP.values())
    ws.append(headers)
    
    # Style cho Header
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1877F2", end_color="1877F2", fill_type="solid") # Facebook Blue
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
    
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"
    
    # 2. Ghi từng dòng dữ liệu
    thin_border = Border(
        left=Side(style="thin", color="E0E0E0"),
        right=Side(style="thin", color="E0E0E0"),
        top=Side(style="thin", color="E0E0E0"),
        bottom=Side(style="thin", color="E0E0E0")
    )
    
    for idx, rec in enumerate(records, start=1):
        row_data = [
            idx,
            rec.get("reel_url", ""),
            rec.get("caption", ""),
            rec.get("found_in", ""),
            rec.get("target_url", ""),
            rec.get("title", ""),
            rec.get("content", ""),
            rec.get("status", ""),
            rec.get("scraped_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ]
        ws.append(row_data)
        current_row = idx + 1
        
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=current_row, column=col_num)
            cell.font = Font(name="Segoe UI", size=10)
            cell.border = thin_border
            # Đặt wrap text cho cột mô tả và nội dung bài viết
            if headers[col_num - 1] in ["Mô tả Reel", "Nội dung bài viết", "Tiêu đề bài viết"]:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
            elif headers[col_num - 1] in ["STT", "Vị trí tìm thấy link", "Trạng thái", "Thời gian cào"]:
                cell.alignment = Alignment(horizontal="center", vertical="top")
            else:
                cell.alignment = Alignment(vertical="top")

    # 3. Điều chỉnh độ rộng cột
    column_widths = {
        "A": 8,   # STT
        "B": 35,  # Link Reel
        "C": 40,  # Mô tả Reel
        "D": 20,  # Vị trí
        "E": 35,  # Link Web
        "F": 35,  # Tiêu đề bài viết
        "G": 65,  # Nội dung bài viết
        "H": 20,  # Trạng thái
        "I": 22   # Thời gian cào
    }
    for col_letter, width in column_widths.items():
        ws.column_dimensions[col_letter].width = width

    return wb

def export_to_excel(records: list[dict], output_filepath: Path | str | None = None) -> Path:
    """Lưu danh sách bản ghi ra file Excel."""
    if output_filepath is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filepath = OUTPUT_DIR / f"reels_content_{timestamp}.xlsx"
    else:
        output_filepath = Path(output_filepath)
        output_filepath.parent.mkdir(parents=True, exist_ok=True)
        
    wb = _build_formatted_workbook(records)
    wb.save(output_filepath)
    return output_filepath

def get_excel_bytes(records: list[dict]) -> bytes:
    """Trả về buffer bytes Excel phục vụ tải về trực tiếp từ Web UI."""
    wb = _build_formatted_workbook(records)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 4: Chạy test để xác nhận pass**

Run: `pytest tests/test_exporter.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit code**

```bash
git add exporter.py tests/test_exporter.py
git commit -m "feat: implement formatted Excel exporter"
```

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
  - `crawl_reels(input_target: str | list[str], max_reels: int, check_comments: bool, delay_range: tuple, headless: bool, progress_callback: callable) -> list[dict]`

- [ ] **Step 1: Viết test cho `normalize_reels_url` và `extract_urls_from_text`**

Tạo file `tests/test_fb_crawler.py`:
```python
from fb_crawler import normalize_reels_url, extract_urls_from_text

def test_normalize_reels_url():
    # Trường hợp 1: Profile ID không có reels_tab
    url1 = "https://www.facebook.com/profile.php?id=61593414350410"
    assert normalize_reels_url(url1) == "https://www.facebook.com/profile.php?id=61593414350410&sk=reels_tab"

    # Trường hợp 2: Profile ID đã có sẵn reels_tab
    url2 = "https://www.facebook.com/profile.php?id=61593414350410&sk=reels_tab"
    assert normalize_reels_url(url2) == "https://www.facebook.com/profile.php?id=61593414350410&sk=reels_tab"

    # Trường hợp 3: Page username
    url3 = "https://www.facebook.com/kenh14.vn"
    assert normalize_reels_url(url3) == "https://www.facebook.com/kenh14.vn/reels/"

    # Trường hợp 4: Page username đã có /reels hoặc /reels/
    url4 = "https://www.facebook.com/kenh14.vn/reels"
    assert normalize_reels_url(url4) == "https://www.facebook.com/kenh14.vn/reels/"

def test_extract_urls_from_text():
    text = "Xem chi tiết bài viết tại đây: https://dantri.com.vn/xa-hoi/tin-123.htm hoặc http://bit.ly/abc và xem thêm tại https://facebook.com/reel/999"
    urls = extract_urls_from_text(text)
    # Phải lấy được link ngoài, loại bỏ link facebook
    assert "https://dantri.com.vn/xa-hoi/tin-123.htm" in urls
    assert "http://bit.ly/abc" in urls
    assert not any("facebook.com" in u for u in urls)
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `pytest tests/test_fb_crawler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fb_crawler'`.

- [ ] **Step 3: Viết mã nguồn cho `fb_crawler.py`**

Tạo file `fb_crawler.py`:
```python
import logging
import re
import time
import random
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from playwright.sync_api import sync_playwright
from config import PROFILE_DIR, USER_AGENT, MIN_DELAY, MAX_DELAY
from article_extractor import extract_article

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'(?:https?://|www\.)[^\s<>"]+(?<![.,?!:;])',
    re.IGNORECASE
)

IGNORED_DOMAINS = [
    "facebook.com", "fb.com", "fb.watch", "m.facebook.com", 
    "instagram.com", "threads.net"
]

def normalize_reels_url(input_url: str) -> str:
    """Chuẩn hóa mọi định dạng URL trang Facebook thành link tab Reels."""
    clean_url = input_url.strip()
    if not clean_url:
        return ""
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url

    parsed = urlparse(clean_url)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query)

    # 1. Dạng ID: profile.php?id=...
    if "profile.php" in path and "id" in query:
        query["sk"] = ["reels_tab"]
        new_query = urlencode(query, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", new_query, ""))

    # 2. Dạng đã có /reels
    if path.endswith("/reels"):
        return f"{parsed.scheme}://{parsed.netloc}{path}/"
    if "/reels/" in path:
        return clean_url

    # 3. Dạng username thông thường (facebook.com/username)
    if path and not path.endswith("/reels"):
        return f"{parsed.scheme}://{parsed.netloc}{path}/reels/"

    return clean_url

def extract_urls_from_text(text: str) -> list[str]:
    """Tìm tất cả các link web hợp lệ trong văn bản, bỏ qua link nội bộ Facebook."""
    if not text:
        return []
    matches = URL_REGEX.findall(text)
    external_urls = []
    for u in matches:
        if not u.startswith("http"):
            u = "https://" + u
        domain = urlparse(u).netloc.lower()
        if not any(ign in domain for ign in IGNORED_DOMAINS):
            external_urls.append(u)
    return external_urls

def has_logged_in_session() -> bool:
    """Kiểm tra xem thư mục profile đã có dữ liệu phiên chưa."""
    if not PROFILE_DIR.exists():
        return False
    # Kiểm tra xem có file cookie hoặc dữ liệu Storage không
    cookies_path = PROFILE_DIR / "Default" / "Network" / "Cookies"
    local_storage = PROFILE_DIR / "Default" / "Local Storage"
    return cookies_path.exists() or local_storage.exists() or any(PROFILE_DIR.iterdir())

def launch_login_browser(headless: bool = False):
    """Mở trình duyệt thực để người dùng đăng nhập tài khoản Facebook."""
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.facebook.com/")
        # Chờ đến khi người dùng đóng trình duyệt thủ công
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        finally:
            context.close()

def crawl_reels_from_tab(page, reels_url: str, max_count: int, delay_range: tuple) -> list[str]:
    """Lướt tab Reels của Page để lấy danh sách link video."""
    page.goto(reels_url, wait_until="networkidle", timeout=45000)
    time.sleep(3)
    
    collected_urls = []
    scroll_attempts = 0
    max_scroll_attempts = 30

    while len(collected_urls) < max_count and scroll_attempts < max_scroll_attempts:
        # Tìm tất cả link dạng /reel/<id>/ hoặc /reel/<id>
        links = page.query_selector_all('a[href*="/reel/"]')
        for a in links:
            href = a.get_attribute("href")
            if href:
                # Chuẩn hóa link reel
                clean_href = href.split("?")[0]
                if not clean_href.startswith("http"):
                    clean_href = "https://www.facebook.com" + clean_href
                if clean_href not in collected_urls and "/reel/" in clean_href:
                    collected_urls.append(clean_href)
                    if len(collected_urls) >= max_count:
                        break
                        
        # Cuộn trang xuống
        page.evaluate("window.scrollBy(0, 1000)")
        sleep_time = random.uniform(delay_range[0], delay_range[1])
        time.sleep(sleep_time)
        scroll_attempts += 1

    return collected_urls[:max_count]

def extract_single_reel(page, reel_url: str, check_comments: bool, delay_range: tuple) -> dict:
    """Truy cập từng Reel, lấy caption, tìm link web và bình luận."""
    page.goto(reel_url, wait_until="networkidle", timeout=35000)
    time.sleep(random.uniform(delay_range[0], delay_range[1]))
    
    caption_text = ""
    target_url = ""
    found_in = "Không tìm thấy"

    # 1. Trích xuất Caption
    # Facebook Reels thường để caption trong span hoặc div có role hoặc dir="auto"
    caption_elements = page.query_selector_all('div[dir="auto"], span[dir="auto"]')
    captions_found = []
    for el in caption_elements:
        txt = el.inner_text().strip()
        if txt and len(txt) > 5 and not txt.startswith("Thích") and not txt.startswith("Bình luận"):
            captions_found.append(txt)
    
    if captions_found:
        caption_text = max(captions_found, key=len)
    
    # Tìm URL trong caption
    urls_in_caption = extract_urls_from_text(caption_text)
    if urls_in_caption:
        target_url = urls_in_caption[0]
        found_in = "Trong mô tả"
        
    # 2. Nếu không thấy URL và bật check_comments
    if not target_url and check_comments:
        try:
            # Tìm và click nút mở bình luận nếu có
            comment_btn = page.query_selector('div[aria-label*="Bình luận"], div[aria-label*="Comment"]')
            if comment_btn:
                comment_btn.click()
                time.sleep(2)
            
            # Quét các comment item
            comment_texts = page.query_selector_all('div[role="article"], div[dir="auto"]')
            for c_el in comment_texts:
                c_text = c_el.inner_text()
                c_urls = extract_urls_from_text(c_text)
                if c_urls:
                    target_url = c_urls[0]
                    found_in = "Trong bình luận"
                    break
        except Exception as e:
            logger.warning(f"Lỗi khi quét bình luận Reel {reel_url}: {e}")

    # 3. Trích xuất nội dung bài viết từ link web tìm được
    article_data = {"title": "", "content": "", "status": "Không tìm thấy link web"}
    if target_url:
        article_data = extract_article(target_url)

    return {
        "reel_url": reel_url,
        "caption": caption_text,
        "found_in": found_in,
        "target_url": target_url,
        "title": article_data.get("title", ""),
        "content": article_data.get("content", ""),
        "status": article_data.get("status", ""),
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def run_crawler_pipeline(
    input_type: str, # "page" hoặc "list"
    target_data: str | list[str],
    max_reels: int = 20,
    check_comments: bool = True,
    delay_range: tuple = (MIN_DELAY, MAX_DELAY),
    headless: bool = True,
    progress_callback = None
) -> list[dict]:
    """Hàm pipeline chạy toàn bộ luồng cào dữ liệu."""
    results = []
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            reel_urls = []
            if input_type == "page":
                page_reels_url = normalize_reels_url(str(target_data))
                if progress_callback:
                    progress_callback(0, 0, f"Đang quét danh sách Reels từ: {page_reels_url}", None)
                reel_urls = crawl_reels_from_tab(page, page_reels_url, max_reels, delay_range)
            else:
                reel_urls = [u.strip() for u in target_data if u.strip()][:max_reels]

            total = len(reel_urls)
            if total == 0:
                if progress_callback:
                    progress_callback(0, 0, "Không tìm thấy video Reel nào.", None)
                return []

            for idx, r_url in enumerate(reel_urls, start=1):
                if progress_callback:
                    progress_callback(idx, total, f"Đang xử lý Reel ({idx}/{total}): {r_url}", None)
                
                reel_data = extract_single_reel(page, r_url, check_comments, delay_range)
                results.append(reel_data)
                
                if progress_callback:
                    progress_callback(idx, total, f"Đã hoàn thành Reel {idx}/{total}", reel_data)

        finally:
            context.close()

    return results
```

- [ ] **Step 4: Chạy test để xác nhận pass**

Run: `pytest tests/test_fb_crawler.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit code**

```bash
git add fb_crawler.py tests/test_fb_crawler.py
git commit -m "feat: implement Facebook Reels crawler with URL normalization and Playwright persistent context"
```

---

### Task 5: Xây dựng Giao diện Web UI Streamlit (`app.py` & `run.bat`)

**Files:**
- Create: `app.py`
- Create: `run.bat`

**Interfaces:**
- Consumes:
  - `fb_crawler.has_logged_in_session()`, `fb_crawler.launch_login_browser()`, `fb_crawler.run_crawler_pipeline()`
  - `exporter.export_to_excel()`, `exporter.get_excel_bytes()`
- Produces:
  - Interactive Streamlit dashboard on `http://localhost:8501`
  - 1-click startup batch script `run.bat`

- [ ] **Step 1: Viết file giao diện Streamlit `app.py`**

Tạo file `app.py`:
- Sidebar: Hiển thị trạng thái đăng nhập, nút mở Chromium đăng nhập Facebook, các cấu hình (số lượng reel tối đa, delay, checkbox cào bình luận, chọn headless hay có cửa sổ).
- Main Content: 2 Tabs (Tab 1: Quét Fanpage/Profile URL, Tab 2: Dán danh sách link lẻ).
- Nút " Bắt đầu cào", " Dừng".
- Live progress bar + status text.
- Bảng hiển thị kết quả trực tiếp (st.dataframe cập nhật từng dòng khi cào xong).
- Nút tải file Excel `.xlsx` và CSV ngay tại giao diện.

- [ ] **Step 2: Viết script `run.bat`**

Tạo file `run.bat` với nội dung khởi động nhanh:
```bat
@echo off
chcp 65001 > nul
title Facebook Reels & Article Content Extractor
echo ========================================================
echo   FACEBOOK REELS & ARTICLE CONTENT EXTRACTOR TOOL
echo ========================================================
echo Dang khoi dong Web UI...
streamlit run app.py
pause
```

- [ ] **Step 3: Chạy thử nghiệm cú pháp và khởi chạy thử Streamlit**

Run: `python -m py_compile app.py`
Expected: Return 0 (không lỗi cú pháp).

- [ ] **Step 4: Commit code**

```bash
git add app.py run.bat
git commit -m "feat: implement Streamlit Web UI dashboard and run.bat launcher"
```

---

### Task 6: Kiểm thử tổng thể & Hướng dẫn sử dụng

**Files:**
- Create: `README.md`
- Test: Chạy toàn bộ test suite `pytest tests/`

- [ ] **Step 1: Chạy toàn bộ test suite**

Run: `pytest tests/ -v`
Expected: 100% tests pass.

- [ ] **Step 2: Viết tài liệu `README.md`**

Hướng dẫn sử dụng chi tiết bằng tiếng Việt:
- Cài đặt nhanh với 1 dòng lệnh.
- Cách đăng nhập Facebook an toàn lần đầu.
- Cách cào theo Fanpage / Profile hoặc danh sách link lẻ.
- Cách tải và mở file Excel kết quả.

- [ ] **Step 3: Commit code và hoàn tất**

```bash
git add README.md
git commit -m "docs: add user manual and instructions in README.md"
```
