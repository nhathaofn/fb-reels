import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.url_helper import normalize_reels_url, extract_urls_from_text

def test_normalize_reels_url_variations():
    # ID format
    url_id = "https://www.facebook.com/profile.php?id=123456789"
    norm_id = normalize_reels_url(url_id)
    assert "sk=reels_tab" in norm_id

    # Normal username format
    url_user = "https://www.facebook.com/myfanpage"
    norm_user = normalize_reels_url(url_user)
    assert norm_user == "https://www.facebook.com/myfanpage/reels/"

    # Already reels
    url_reels = "https://www.facebook.com/myfanpage/reels"
    assert normalize_reels_url(url_reels) == "https://www.facebook.com/myfanpage/reels/"

    # Empty
    assert normalize_reels_url("") == ""

def test_extract_urls_from_text():
    text = (
        "Xem bài viết chi tiết tại https://example.com/bai-viet-1 "
        "hoặc ghé thăm www.testnews.vn/tin-tuc. "
        "Bỏ qua link https://www.facebook.com/reel/123456"
    )
    urls = extract_urls_from_text(text)
    assert "https://example.com/bai-viet-1" in urls
    assert "https://www.testnews.vn/tin-tuc" in urls
    assert not any("facebook.com" in u for u in urls)

def test_extract_urls_with_facebook_redirect():
    text = "Link bài: https://l.facebook.com/l.php?u=https%3A%2F%2Fcleanlink.com%2Fpost-123"
    urls = extract_urls_from_text(text)
    assert "https://cleanlink.com/post-123" in urls


def test_ignored_meta_domains():
    text = (
        "Check here: https://meta.com/about and https://whatsapp.com/channel/123 "
        "and real site: https://validnews.org/story/1"
    )
    urls = extract_urls_from_text(text)
    assert "https://validnews.org/story/1" in urls
    assert not any("meta.com" in u for u in urls)
    assert not any("whatsapp.com" in u for u in urls)


def test_extract_shortlinks_and_domain_urls():
    text = (
        "Story full here: bit.ly/chapter1! Mua hàng: shopee.vn/product/999?ref=12. "
        "Domain link: linger.treeiq.biz/blog/post-1... (bỏ qua nếu cụt) "
        "nhưng link này chuẩn: linger.treeiq.biz/blog/post-full"
    )
    urls = extract_urls_from_text(text)

def test_universal_tld_extraction():
    text = (
        "Truy cập https://storyvault009.cafex.biz/blog/9ziyvg để đọc tiếp, "
        "hoặc vào novel-reader.top/chapter/1 hay reading.story/news/123 "
        "và https://web.read.icu/p/456."
    )
    urls = extract_urls_from_text(text)
    assert "https://storyvault009.cafex.biz/blog/9ziyvg" in urls
    assert "https://novel-reader.top/chapter/1" in urls
    assert "https://reading.story/news/123" in urls
    assert "https://web.read.icu/p/456" in urls


def test_reject_dotted_censored_words_and_typos():
    text = (
        "Ryan slipped the toe of his boot beneath Victoria’s plastic bucket and k.i.c.ked it aside. "
        "He pressed down until the side of the bucket c.r.a.c.ked open. "
        "Hello Mr.Smith how are you? Meeting at 5 p.m. today, e.g. for discussion. "
        "PHẦN TIẾP THEO: https://storyvault009.cafex.biz/blog/6qva4i"
    )
    urls = extract_urls_from_text(text)
    assert "https://k.i.c.ked" not in urls
    assert "https://c.r.a.c.ked" not in urls
    assert not any("smith" in u.lower() for u in urls)
    assert not any("e.g" in u.lower() for u in urls)
    assert urls == ["https://storyvault009.cafex.biz/blog/6qva4i"]




