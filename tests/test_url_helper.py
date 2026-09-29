import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.url_helper import (
    normalize_reels_url,
    extract_urls_from_text,
    extract_channel_id,
    resolve_channel_project_dirs,
    extract_reel_id,
    scan_existing_reels_folder,
)

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


def test_extract_channel_id():
    # 1. Profile with ID
    url1 = "https://www.facebook.com/profile.php?id=61593384835679"
    assert extract_channel_id(url1) == "61593384835679"

    # 2. Profile with ID and additional query params
    url2 = "https://www.facebook.com/profile.php?id=61593384835679&sk=reels_tab"
    assert extract_channel_id(url2) == "61593384835679"

    # 3. Fanpage / Username
    url3 = "https://www.facebook.com/nhathaofn/reels/"
    assert extract_channel_id(url3) == "nhathaofn"

    # 4. Bare numeric ID
    assert extract_channel_id("61593384835679") == "61593384835679"

    # 5. Empty or fallback
    assert extract_channel_id("") == "channel"


def test_resolve_channel_project_dirs(tmp_path):
    root = tmp_path / "project_root"

    # 1. Lần đầu cào kênh profile: https://www.facebook.com/profile.php?id=61593384835679
    # Sẽ tự động tạo folder: 1_61593384835679
    url_profile = "https://www.facebook.com/profile.php?id=61593384835679"
    res1 = resolve_channel_project_dirs(root, url_profile)

    assert res1["channel_id"] == "61593384835679"
    assert res1["folder_name"] == "1_61593384835679"
    assert res1["channel_dir"].exists()
    assert (res1["channel_dir"] / "video").is_dir()
    assert (res1["channel_dir"] / "caption").is_dir()
    assert (res1["channel_dir"] / "final").is_dir()

    # 2. Cào lại kênh cũ đó -> Tái sử dụng folder 1_61593384835679
    res1_repeat = resolve_channel_project_dirs(root, "61593384835679")
    assert res1_repeat["folder_name"] == "1_61593384835679"
    assert res1_repeat["channel_dir"] == res1["channel_dir"]

    # 3. Cào kênh thứ 2 mới: https://www.facebook.com/nhathaofn
    # Sẽ tự động tăng STT: 2_nhathaofn
    res2 = resolve_channel_project_dirs(root, "https://www.facebook.com/nhathaofn")
    assert res2["folder_name"] == "2_nhathaofn"
    assert res2["channel_dir"].exists()
    assert (res2["channel_dir"] / "video").is_dir()
    assert (res2["channel_dir"] / "caption").is_dir()
    assert (res2["channel_dir"] / "final").is_dir()

    # 4. Cào kênh thứ 3 mới: ID 999888
    # Sẽ tự động tăng STT: 3_999888
    res3 = resolve_channel_project_dirs(root, "https://www.facebook.com/profile.php?id=999888")
    assert res3["folder_name"] == "3_999888"
    assert res3["channel_dir"].exists()


def test_extract_reel_id():
    assert extract_reel_id("https://www.facebook.com/reel/1098330379252955") == "1098330379252955"
    assert extract_reel_id("https://www.facebook.com/reel/1098330379252955?s=share") == "1098330379252955"
    assert extract_reel_id("https://www.facebook.com/watch/?v=1098330379252955") == "1098330379252955"
    assert extract_reel_id("https://www.facebook.com/username/videos/1098330379252955/") == "1098330379252955"
    assert extract_reel_id("1098330379252955") == "1098330379252955"
    assert extract_reel_id("") == ""


def test_scan_existing_reels_folder(tmp_path):
    video_dir = tmp_path / "video"
    caption_dir = tmp_path / "caption"
    video_dir.mkdir()
    caption_dir.mkdir()

    # 1. Thư mục trống -> max_stt = 0
    max_stt, existing = scan_existing_reels_folder(video_dir, caption_dir)
    assert max_stt == 0
    assert len(existing) == 0

    # 2. Tạo sẵn 3 video và 3 caption
    (video_dir / "1_1001.mp4").write_bytes(b"dummy")
    (video_dir / "2_1002.mp4").write_bytes(b"dummy")
    (video_dir / "3_1003.mp4").write_bytes(b"dummy")

    (caption_dir / "caption_1.txt").write_text("cap 1", encoding="utf-8")
    (caption_dir / "caption_2.txt").write_text("cap 2", encoding="utf-8")
    (caption_dir / "caption_3.txt").write_text("cap 3", encoding="utf-8")

    max_stt, existing = scan_existing_reels_folder(video_dir, caption_dir)
    assert max_stt == 3
    assert "1001" in existing
    assert "1002" in existing
    assert "1003" in existing
    assert existing["1001"]["stt"] == 1
    assert existing["1003"]["stt"] == 3






