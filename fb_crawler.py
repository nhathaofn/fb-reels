import logging
import random
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from playwright.sync_api import sync_playwright

from article_extractor import extract_article
from config import MAX_DELAY, MIN_DELAY, PROFILE_DIR, USER_AGENT

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'(?:https?://|www\.)[^\s<>"]+(?<![.,?!:;])',
    re.IGNORECASE
)

IGNORED_DOMAINS = [
    "facebook.com",
    "fb.com",
    "fb.watch",
    "m.facebook.com",
    "instagram.com",
    "threads.net"
]


def normalize_reels_url(input_url: str) -> str:
    """Chuẩn hóa mọi định dạng URL trang Facebook thành link tab Reels."""
    clean_url = input_url.strip()
    if not clean_url:
        return ""
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url

    parsed = urlparse(clean_url)
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    query = parse_qs(parsed.query)

    # 1. Dạng ID: profile.php?id=...
    if "profile.php" in path_lower and "id" in query:
        query["sk"] = ["reels_tab"]
        new_query = urlencode(query, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", new_query, ""))

    # 2. Dạng đã có /reels
    if path_lower.endswith("/reels"):
        return f"{parsed.scheme}://{parsed.netloc}{path}/"
    if "/reels/" in path_lower:
        return clean_url

    # 3. Dạng username thông thường (facebook.com/username)
    if path and not path_lower.endswith("/reels"):
        return f"{parsed.scheme}://{parsed.netloc}{path}/reels/"

    return clean_url


def extract_urls_from_text(text: str) -> list[str]:
    """Tìm tất cả các link web hợp lệ trong văn bản, bỏ qua link nội bộ Facebook/Meta."""
    if not text:
        return []
    matches = URL_REGEX.findall(text)
    external_urls = []
    for u in matches:
        u = u.rstrip(")]}>\"'")
        if not u:
            continue
        if not u.startswith("http"):
            u = "https://" + u

        parsed_u = urlparse(u)
        domain = parsed_u.netloc.lower()

        # Giải mã link redirect của Facebook (l.facebook.com/l.php?u=...) nếu có
        if "facebook.com" in domain and "/l.php" in parsed_u.path:
            qs = parse_qs(parsed_u.query)
            if "u" in qs and qs["u"]:
                u = qs["u"][0]
                domain = urlparse(u).netloc.lower()

        if not any(ign in domain for ign in IGNORED_DOMAINS):
            if u not in external_urls:
                external_urls.append(u)

    return external_urls


def has_logged_in_session() -> bool:
    """Kiểm tra xem thư mục profile đã có dữ liệu phiên đăng nhập chưa."""
    if not PROFILE_DIR.exists():
        return False

    cookies_path = PROFILE_DIR / "Default" / "Network" / "Cookies"
    local_storage = PROFILE_DIR / "Default" / "Local Storage"

    if cookies_path.exists() or local_storage.exists():
        return True

    # Kiểm tra xem có file nào khác ngoài .gitkeep không
    try:
        entries = [f for f in PROFILE_DIR.iterdir() if f.name != ".gitkeep"]
        return len(entries) > 0
    except Exception:
        return False


def launch_login_browser(headless: bool = False) -> None:
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
        try:
            page.goto("https://www.facebook.com/")
            page.wait_for_event("close", timeout=0)
        except Exception as e:
            logger.info(f"Đã đóng phiên đăng nhập trình duyệt: {e}")
        finally:
            try:
                context.close()
            except Exception:
                pass


def crawl_reels_from_tab(page, reels_url: str, max_count: int, delay_range: tuple) -> list[str]:
    """Lướt tab Reels của Page để lấy danh sách link video."""
    try:
        page.goto(reels_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        logger.warning(f"Lỗi hoặc timeout khi mở tab Reels {reels_url}: {e}")

    time.sleep(min(3.0, delay_range[0]))

    collected_urls: list[str] = []
    scroll_attempts = 0
    max_scroll_attempts = 30

    while len(collected_urls) < max_count and scroll_attempts < max_scroll_attempts:
        links = page.query_selector_all('a[href*="/reel/"]')
        for a in links:
            try:
                href = a.get_attribute("href")
            except Exception:
                href = None

            if href:
                clean_href = href.split("?")[0]
                if not clean_href.startswith("http"):
                    clean_href = "https://www.facebook.com" + clean_href
                if "/reel/" in clean_href and clean_href not in collected_urls:
                    collected_urls.append(clean_href)
                    if len(collected_urls) >= max_count:
                        break

        try:
            page.evaluate("window.scrollBy(0, 1000)")
        except Exception as e:
            logger.warning(f"Lỗi khi cuộn trang: {e}")
            break

        sleep_time = random.uniform(delay_range[0], delay_range[1])
        time.sleep(sleep_time)
        scroll_attempts += 1

    return collected_urls[:max_count]


def extract_single_reel(page, reel_url: str, check_comments: bool, delay_range: tuple) -> dict:
    """Truy cập từng Reel, lấy caption, tìm link web và bình luận."""
    try:
        page.goto(reel_url, wait_until="domcontentloaded", timeout=35000)
    except Exception as e:
        logger.warning(f"Lỗi hoặc timeout khi tải Reel {reel_url}: {e}")

    time.sleep(random.uniform(delay_range[0], delay_range[1]))

    caption_text = ""
    target_url = ""
    found_in = "Không tìm thấy"

    # 1. Trích xuất Caption
    caption_elements = page.query_selector_all('div[dir="auto"], span[dir="auto"]')
    captions_found = []
    for el in caption_elements:
        try:
            txt = el.inner_text().strip()
            if txt and len(txt) > 5 and not txt.startswith("Thích") and not txt.startswith("Bình luận"):
                captions_found.append(txt)
        except Exception:
            continue

    if captions_found:
        caption_text = max(captions_found, key=len)

    # Tìm URL trong caption
    urls_in_caption = extract_urls_from_text(caption_text)
    if not urls_in_caption and captions_found:
        # Kiểm tra thêm các khối text khác trong caption nếu khối dài nhất chưa có link
        for cand in captions_found:
            cand_urls = extract_urls_from_text(cand)
            if cand_urls:
                urls_in_caption = cand_urls
                break

    if urls_in_caption:
        target_url = urls_in_caption[0]
        found_in = "Trong mô tả"

    # 2. Nếu không thấy URL và bật check_comments
    if not target_url and check_comments:
        try:
            comment_btn = page.query_selector('div[aria-label*="Bình luận"], div[aria-label*="Comment"]')
            if comment_btn:
                try:
                    comment_btn.click()
                    time.sleep(2)
                except Exception:
                    pass

            comment_texts = page.query_selector_all('div[role="article"], div[dir="auto"]')
            for c_el in comment_texts:
                try:
                    c_text = c_el.inner_text()
                    c_urls = extract_urls_from_text(c_text)
                    if c_urls:
                        target_url = c_urls[0]
                        found_in = "Trong bình luận"
                        break
                except Exception:
                    continue
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
    input_type: str,
    target_data: str | list[str],
    max_reels: int = 20,
    check_comments: bool = True,
    delay_range: tuple = (MIN_DELAY, MAX_DELAY),
    headless: bool = True,
    progress_callback = None,
    stop_check_callback = None
) -> list[dict]:
    """Hàm pipeline chạy toàn bộ luồng cào dữ liệu Facebook Reels."""
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
            reel_urls: list[str] = []
            if input_type == "page":
                page_reels_url = normalize_reels_url(str(target_data))
                if progress_callback:
                    progress_callback(0, 0, f"Đang quét danh sách Reels từ: {page_reels_url}", None)
                reel_urls = crawl_reels_from_tab(page, page_reels_url, max_reels, delay_range)
            else:
                if isinstance(target_data, str):
                    raw_list = [line.strip() for line in target_data.splitlines() if line.strip()]
                else:
                    raw_list = target_data
                reel_urls = [u.strip() for u in raw_list if u.strip()][:max_reels]

            total = len(reel_urls)
            if total == 0:
                if progress_callback:
                    progress_callback(0, 0, "Không tìm thấy video Reel nào.", None)
                return []

            for idx, r_url in enumerate(reel_urls, start=1):
                if stop_check_callback and stop_check_callback():
                    logger.info("Nhận được tín hiệu dừng cào từ stop_check_callback.")
                    if progress_callback:
                        progress_callback(idx - 1, total, "⏹️ Quá trình cào đã được dừng.", None)
                    break

                if progress_callback:
                    cb_status = progress_callback(idx, total, f"Đang xử lý Reel ({idx}/{total}): {r_url}", None)
                    if cb_status is False:
                        logger.info("Nhận được tín hiệu dừng cào từ progress_callback.")
                        break

                try:
                    reel_data = extract_single_reel(page, r_url, check_comments, delay_range)
                except Exception as e:
                    logger.error(f"Lỗi khi cào Reel {r_url}: {e}")
                    reel_data = {
                        "reel_url": r_url,
                        "caption": "",
                        "found_in": "Lỗi",
                        "target_url": "",
                        "title": "",
                        "content": "",
                        "status": f"Lỗi cào video: {e}",
                        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }

                results.append(reel_data)

                if progress_callback:
                    progress_callback(idx, total, f"Đã hoàn thành Reel {idx}/{total}", reel_data)

        finally:
            try:
                context.close()
            except Exception:
                pass

    return results


def crawl_reels(
    input_target: str | list[str],
    max_reels: int = 20,
    check_comments: bool = True,
    delay_range: tuple = (MIN_DELAY, MAX_DELAY),
    headless: bool = True,
    progress_callback = None,
    stop_check_callback = None
) -> list[dict]:
    """Hàm wrapper tiện ích cào reels nhận target là URL fanpage hoặc danh sách URL reels."""
    if isinstance(input_target, list):
        input_type = "list"
    elif isinstance(input_target, str) and ("\n" in input_target or "/reel/" in input_target):
        input_type = "list"
    else:
        input_type = "page"

    return run_crawler_pipeline(
        input_type=input_type,
        target_data=input_target,
        max_reels=max_reels,
        check_comments=check_comments,
        delay_range=delay_range,
        headless=headless,
        progress_callback=progress_callback,
        stop_check_callback=stop_check_callback
    )
