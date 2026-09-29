import logging
import httpx
import trafilatura
from bs4 import BeautifulSoup
from src.config import USER_AGENT, REQUEST_TIMEOUT

logger = logging.getLogger("article_extractor")


def resolve_target_url(url: str, timeout: float = REQUEST_TIMEOUT) -> str:
    """Theo dõi chuyển hướng (redirect) để lấy link đích thực tế."""
    if not url:
        return ""
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.head(url)
            resp.raise_for_status()
            return str(resp.url)
    except Exception:
        # Fallback thử qua GET nếu server từ chối HEAD hoặc trả mã lỗi
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
    soup = None
    if not title:
        soup = BeautifulSoup(html, "html.parser")
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.get_text(strip=True):
            title = soup.title.get_text(strip=True)

    # Fallback nội dung qua og:description hoặc meta description nếu trafilatura chưa bóc tách được (trang JS/SPA nhẹ)
    if not extracted_text:
        if soup is None:
            soup = BeautifulSoup(html, "html.parser")
        meta_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            extracted_text = meta_desc["content"].strip()

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
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1"
    }
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
