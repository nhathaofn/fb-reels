import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.fb_crawler import (
    normalize_reels_url,
    extract_urls_from_text,
    has_logged_in_session,
    crawl_reels_from_tab,
    extract_single_reel,
    run_crawler_pipeline,
    crawl_reels,
    get_profile_dir,
    list_available_profiles,
    delete_profile,
    parse_cookie_input,
    save_cookies_to_profile,
    load_profile_settings,
    save_profile_settings,
    load_profile_last_results,
    save_profile_last_results,
    clean_caption_text,
)


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

    url5 = "https://www.facebook.com/kenh14.vn/reels/"
    assert normalize_reels_url(url5) == "https://www.facebook.com/kenh14.vn/reels/"

    # Edge cases: URL không có http hoặc rỗng
    assert normalize_reels_url("") == ""
    assert normalize_reels_url("   ") == ""
    assert normalize_reels_url("facebook.com/kenh14.vn") == "https://facebook.com/kenh14.vn/reels/"
    assert normalize_reels_url("https://www.facebook.com/kenh14.vn/REELS") == "https://www.facebook.com/kenh14.vn/REELS/"
    assert normalize_reels_url("https://www.facebook.com/PROFILE.PHP?id=123") == "https://www.facebook.com/PROFILE.PHP?id=123&sk=reels_tab"


def test_extract_urls_from_text():
    text = (
        "Xem chi tiết bài viết tại đây: (https://dantri.com.vn/xa-hoi/tin-123.htm) "
        "hoặc [http://bit.ly/abc] và xem thêm tại \"https://facebook.com/reel/999\" "
        "hoặc <https://instagram.com/p/123>."
    )
    urls = extract_urls_from_text(text)
    # Phải lấy được link ngoài, không dính dấu ngoặc đóng ), ], >, ", loại bỏ facebook/instagram
    assert "https://dantri.com.vn/xa-hoi/tin-123.htm" in urls
    assert "http://bit.ly/abc" in urls
    assert not any("facebook.com" in u for u in urls)
    assert not any("instagram.com" in u for u in urls)

    # Empty text
    assert extract_urls_from_text("") == []
    assert extract_urls_from_text(None) == []


def test_has_logged_in_session(tmp_path, monkeypatch):
    import sqlite3
    test_profile = tmp_path / "browser_profile"
    monkeypatch.setattr("src.core.fb_crawler.PROFILE_DIR", test_profile)
    monkeypatch.setattr("src.core.fb_crawler.PROFILES_DIR", test_profile / "profiles")

    # Thư mục chưa tồn tại
    assert has_logged_in_session() is False

    # Thư mục rỗng
    test_profile.mkdir()
    assert has_logged_in_session() is False

    # Có file Cookies nhưng không có cookie c_user (khách vãng lai)
    cookies_file = test_profile / "Default" / "Network" / "Cookies"
    cookies_file.parent.mkdir(parents=True)
    con = sqlite3.connect(cookies_file)
    con.execute("CREATE TABLE cookies (name TEXT, value TEXT)")
    con.execute("INSERT INTO cookies VALUES ('datr', '123')")
    con.commit()
    con.close()
    assert has_logged_in_session() is False

    # Thêm cookie c_user (đã đăng nhập thật)
    con = sqlite3.connect(cookies_file)
    con.execute("INSERT INTO cookies VALUES ('c_user', '1000123')")
    con.commit()
    con.close()
    assert has_logged_in_session() is True



def test_crawl_reels_from_tab():
    mock_page = MagicMock()
    
    # Giả lập trả về các phần tử link reel
    link1 = MagicMock()
    link1.get_attribute.return_value = "/reel/100001?s=fb"
    link2 = MagicMock()
    link2.get_attribute.return_value = "https://www.facebook.com/reel/100002"
    link3 = MagicMock()
    link3.get_attribute.return_value = "/reel/100001"  # trùng link 1
    link4 = MagicMock()
    link4.get_attribute.return_value = "https://www.facebook.com/reel/100003"
    
    mock_page.query_selector_all.return_value = [link1, link2, link3, link4]

    # Chế độ mặc định (oldest): video ở đáy feed (100003 - đăng đầu tiên) đứng đầu STT 1
    urls_oldest = crawl_reels_from_tab(mock_page, "https://www.facebook.com/kenh14.vn/reels/", max_count=2, delay_range=(0.01, 0.02), crawl_order="oldest")
    assert len(urls_oldest) == 2
    assert urls_oldest[0] == "https://www.facebook.com/reel/100003"
    assert urls_oldest[1] == "https://www.facebook.com/reel/100002"

    # Chế độ newest: video ở đỉnh feed (100001 - mới nhất) đứng đầu
    urls_newest = crawl_reels_from_tab(mock_page, "https://www.facebook.com/kenh14.vn/reels/", max_count=2, delay_range=(0.01, 0.02), crawl_order="newest")
    assert len(urls_newest) == 2
    assert urls_newest[0] == "https://www.facebook.com/reel/100001"
    assert urls_newest[1] == "https://www.facebook.com/reel/100002"


def test_extract_single_reel_caption_url():
    mock_page = MagicMock()
    
    # Mock caption elements
    cap_el = MagicMock()
    cap_el.inner_text.return_value = "Tin tức nóng hôm nay xem tại https://vnexpress.net/tin-nong-123.htm"
    mock_page.query_selector_all.return_value = [cap_el]

    with patch("src.core.fb_crawler.extract_article") as mock_extract:
        mock_extract.return_value = {
            "title": "Tin nóng hôm nay",
            "content": "Nội dung chi tiết tin nóng...",
            "status": "Thành công"
        }
        
        result = extract_single_reel(
            mock_page,
            reel_url="https://www.facebook.com/reel/100001",
            check_comments=True,
            delay_range=(0.01, 0.02)
        )

        mock_page.goto.assert_called_once_with("https://www.facebook.com/reel/100001", wait_until="domcontentloaded", timeout=35000)
        assert result["reel_url"] == "https://www.facebook.com/reel/100001"
        assert result["found_in"] == "Trong mô tả"
        assert result["target_url"] == "https://vnexpress.net/tin-nong-123.htm"
        assert result["title"] == "Tin nóng hôm nay"
        assert result["content"] == "Nội dung chi tiết tin nóng..."
        assert result["status"] == "Thành công"
        assert "scraped_at" in result


def test_extract_single_reel_comment_url():
    mock_page = MagicMock()
    
    # Caption không chứa link
    cap_el = MagicMock()
    cap_el.inner_text.return_value = "Xem clip này vui quá các bạn ơi"
    
    # Comment chứa link
    comment_el = MagicMock()
    comment_el.inner_text.return_value = "Link nguồn bài viết: https://tuoitre.vn/bai-viet-456.htm"

    def fake_query_selector_all(selector):
        if 'role="article"' in selector:
            return [comment_el]
        return [cap_el]

    mock_page.query_selector_all.side_effect = fake_query_selector_all

    with patch("src.core.fb_crawler.extract_article") as mock_extract:
        mock_extract.return_value = {
            "title": "Bài viết Tuổi Trẻ",
            "content": "Nội dung bài viết tuổi trẻ...",
            "status": "Thành công"
        }

        result = extract_single_reel(
            mock_page,
            reel_url="https://www.facebook.com/reel/100002",
            check_comments=True,
            delay_range=(0.01, 0.02)
        )

        assert result["found_in"] == "Trong bình luận"
        assert result["target_url"] == "https://tuoitre.vn/bai-viet-456.htm"
        assert result["title"] == "Bài viết Tuổi Trẻ"


def test_extract_single_reel_no_url():
    mock_page = MagicMock()
    cap_el = MagicMock()
    cap_el.inner_text.return_value = "Chỉ là một video giải trí đơn thuần không kèm link."
    mock_page.query_selector_all.return_value = [cap_el]

    result = extract_single_reel(
        mock_page,
        reel_url="https://www.facebook.com/reel/100003",
        check_comments=False,
        delay_range=(0.01, 0.02)
    )

    assert result["found_in"] == "Không tìm thấy"
    assert result["target_url"] == ""
    assert result["status"] == "Không tìm thấy link web"


def test_run_crawler_pipeline_page_mode():
    mock_callback = MagicMock()

    with patch("src.core.fb_crawler.sync_playwright") as mock_playwright_ctx, \
         patch("src.core.fb_crawler.crawl_reels_from_tab") as mock_crawl_tab, \
         patch("src.core.fb_crawler.extract_single_reel") as mock_extract_single:

        mock_playwright = MagicMock()
        mock_playwright_ctx.return_value.__enter__.return_value = mock_playwright
        mock_context = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]

        mock_crawl_tab.return_value = [
            "https://www.facebook.com/reel/111",
            "https://www.facebook.com/reel/222"
        ]
        mock_extract_single.side_effect = [
            {"reel_url": "https://www.facebook.com/reel/222", "title": "Tin 2"},
            {"reel_url": "https://www.facebook.com/reel/111", "title": "Tin 1"}
        ]

        results = run_crawler_pipeline(
            input_type="page",
            target_data="https://www.facebook.com/kenh14.vn",
            max_reels=2,
            check_comments=True,
            delay_range=(0.01, 0.02),
            headless=True,
            progress_callback=mock_callback
        )

        assert len(results) == 2
        assert results[0]["title"] == "Tin 2"
        assert results[0]["stt"] == 1
        assert results[1]["title"] == "Tin 1"
        assert results[1]["stt"] == 2
        assert mock_callback.call_count >= 2
        mock_context.close.assert_called_once()


def test_run_crawler_pipeline_list_mode_and_crawl_reels():
    with patch("src.core.fb_crawler.sync_playwright") as mock_playwright_ctx, \
         patch("src.core.fb_crawler.extract_single_reel") as mock_extract_single:

        mock_playwright = MagicMock()
        mock_playwright_ctx.return_value.__enter__.return_value = mock_playwright
        mock_context = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]

        mock_extract_single.return_value = {"reel_url": "https://www.facebook.com/reel/999", "title": "Tin 999"}

        # Kiểm tra qua hàm wrapper crawl_reels nhận danh sách link
        reels_list = ["https://www.facebook.com/reel/999"]
        results = crawl_reels(
            input_target=reels_list,
            max_reels=5,
            check_comments=False,
            delay_range=(0.01, 0.02),
            headless=True
        )

        assert len(results) == 1
        assert results[0]["title"] == "Tin 999"


def test_run_crawler_pipeline_empty():
    with patch("src.core.fb_crawler.sync_playwright") as mock_playwright_ctx, \
         patch("src.core.fb_crawler.crawl_reels_from_tab") as mock_crawl_tab:

        mock_playwright = MagicMock()
        mock_playwright_ctx.return_value.__enter__.return_value = mock_playwright
        mock_context = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]

        mock_crawl_tab.return_value = []
        progress_mock = MagicMock()

        results = run_crawler_pipeline(
            input_type="page",
            target_data="https://www.facebook.com/empty.page",
            progress_callback=progress_mock
        )

        assert results == []
        progress_mock.assert_called_with(0, 0, "Không tìm thấy video Reel nào.", None)


def test_run_crawler_pipeline_single_reel_exception_isolated():
    mock_callback = MagicMock()

    with patch("src.core.fb_crawler.sync_playwright") as mock_playwright_ctx, \
         patch("src.core.fb_crawler.extract_single_reel") as mock_extract_single:

        mock_playwright = MagicMock()
        mock_playwright_ctx.return_value.__enter__.return_value = mock_playwright
        mock_context = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]

        # Reel 1 ném ngoại lệ bất ngờ, Reel 2 thành công
        mock_extract_single.side_effect = [
            RuntimeError("Network crashed during reel parsing"),
            {
                "reel_url": "https://www.facebook.com/reel/222",
                "caption": "Mô tả 2",
                "found_in": "Trong mô tả",
                "target_url": "https://example.com/2",
                "title": "Tin 2",
                "content": "Nội dung 2",
                "status": "Thành công",
                "scraped_at": "2026-09-28 09:00:00"
            }
        ]

        reels_list = ["https://www.facebook.com/reel/111", "https://www.facebook.com/reel/222"]
        results = run_crawler_pipeline(
            input_type="list",
            target_data=reels_list,
            max_reels=2,
            progress_callback=mock_callback
        )

        assert len(results) == 2
        # Bản ghi 1 ghi nhận lỗi mà không làm sập pipeline
        assert results[0]["reel_url"] == "https://www.facebook.com/reel/111"
        assert results[0]["found_in"] == "Lỗi"
        assert "Lỗi cào video: Network crashed during reel parsing" in results[0]["status"]
        # Bản ghi 2 xử lý thành công
        assert results[1]["reel_url"] == "https://www.facebook.com/reel/222"
        assert results[1]["title"] == "Tin 2"
        assert results[1]["status"] == "Thành công"
        # Callback được gọi đủ 2 lần
        assert mock_callback.call_count >= 2


def test_run_crawler_pipeline_stop_check_callback():
    """Kiểm tra dừng cào sớm khi nhận tín hiệu stop_check_callback."""
    with patch("src.core.fb_crawler.sync_playwright") as mock_pw, \
         patch("src.core.fb_crawler.extract_single_reel") as mock_extract:

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_context

        mock_extract.return_value = {
            "reel_url": "https://www.facebook.com/reel/111",
            "caption": "Mô tả 1",
            "found_in": "Trong mô tả",
            "target_url": "https://example.com/1",
            "title": "Tin 1",
            "content": "Nội dung 1",
            "status": "Thành công",
            "scraped_at": "2026-09-28 09:00:00"
        }

        # Giả lập stop_check_callback trả về False lần 1, True lần 2 (dừng trước reel 2)
        stop_signals = [False, True]
        def fake_stop():
            return stop_signals.pop(0) if stop_signals else True

        reels_list = [
            "https://www.facebook.com/reel/111",
            "https://www.facebook.com/reel/222",
            "https://www.facebook.com/reel/333"
        ]
        results = run_crawler_pipeline(
            input_type="list",
            target_data=reels_list,
            max_reels=3,
            stop_check_callback=fake_stop
        )

        # Chỉ cào được 1 reel đầu tiên trước khi dừng
        assert len(results) == 1
        assert results[0]["reel_url"] == "https://www.facebook.com/reel/111"
        assert mock_extract.call_count == 1


def test_run_crawler_pipeline_auto_saves_captions(tmp_path):
    """Kiểm tra pipeline tự động xuất file caption_{idx}.txt ngay khi cào xong từng link."""
    with patch("src.core.fb_crawler.sync_playwright") as mock_pw, \
         patch("src.core.fb_crawler.extract_single_reel") as mock_extract:

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_context

        mock_extract.side_effect = [
            {
                "reel_url": "https://www.facebook.com/reel/111",
                "caption": "Nội dung caption 1",
                "found_in": "Trong mô tả",
                "target_url": "",
                "title": "",
                "content": "",
                "status": "Thành công",
                "scraped_at": "2026-09-28 09:00:00"
            },
            {
                "reel_url": "https://www.facebook.com/reel/222",
                "caption": "Nội dung caption 2",
                "found_in": "Trong mô tả",
                "target_url": "",
                "title": "",
                "content": "",
                "status": "Thành công",
                "scraped_at": "2026-09-28 09:01:00"
            }
        ]

        target_cap_dir = tmp_path / "custom_captions"
        reels_list = [
            "https://www.facebook.com/reel/111",
            "https://www.facebook.com/reel/222"
        ]

        results = run_crawler_pipeline(
            input_type="list",
            target_data=reels_list,
            max_reels=2,
            caption_output_dir=target_cap_dir,
            auto_save_captions=True
        )

        assert len(results) == 2
        cap1 = target_cap_dir / "caption_1.txt"
        cap2 = target_cap_dir / "caption_2.txt"

        assert cap1.exists()
        assert cap2.exists()
        assert cap1.read_text(encoding="utf-8") == "Nội dung caption 1"
        assert cap2.read_text(encoding="utf-8") == "Nội dung caption 2"
        assert results[0]["caption_path"] == str(cap1)
        assert results[1]["caption_path"] == str(cap2)


def test_get_profile_dir(tmp_path, monkeypatch):
    """Kiểm tra trả về đúng thư mục profile."""
    mock_base = tmp_path / "browser_profile"
    mock_sub = mock_base / "profiles"
    monkeypatch.setattr("src.core.fb_crawler.PROFILE_DIR", mock_base)
    monkeypatch.setattr("src.core.fb_crawler.PROFILES_DIR", mock_sub)

    # default
    assert get_profile_dir("default") == mock_base
    assert get_profile_dir("") == mock_base
    assert get_profile_dir("   ") == mock_base

    # custom profile name
    p1 = get_profile_dir("user_a")
    assert p1 == mock_sub / "user_a"
    assert p1.exists()

    # sanitize special chars
    p2 = get_profile_dir("user #1 / test!")
    assert p2 == mock_sub / "user__1___test_"
    assert p2.exists()


def test_list_available_profiles(tmp_path, monkeypatch):
    """Kiểm tra liệt kê các profile có sẵn."""
    mock_base = tmp_path / "browser_profile"
    mock_sub = mock_base / "profiles"
    monkeypatch.setattr("src.core.fb_crawler.PROFILES_DIR", mock_sub)

    # Khi thư mục profiles chưa có
    assert list_available_profiles() == ["default"]

    # Khi tạo một số profile con
    mock_sub.mkdir(parents=True)
    (mock_sub / "may_1").mkdir()
    (mock_sub / "may_2").mkdir()
    (mock_sub / "some_file.txt").write_text("hello")

    profiles = list_available_profiles()
    assert profiles == ["default", "may_1", "may_2"]


def test_delete_profile(tmp_path, monkeypatch):
    """Kiểm tra xóa profile."""
    mock_base = tmp_path / "browser_profile"
    mock_sub = mock_base / "profiles"
    monkeypatch.setattr("src.core.fb_crawler.PROFILE_DIR", mock_base)
    monkeypatch.setattr("src.core.fb_crawler.PROFILES_DIR", mock_sub)

    # Tạo profile con may_1
    p1 = mock_sub / "may_1"
    p1.mkdir(parents=True)
    (p1 / "test.txt").write_text("data")
    assert p1.exists()

    res = delete_profile("may_1")
    assert res is True
    assert not p1.exists()

    # Xóa default (chỉ xóa nội dung bên trong trừ profiles & .gitkeep)
    mock_base.mkdir(parents=True, exist_ok=True)
    (mock_base / "dummy.txt").write_text("data")
    res_default = delete_profile("default")
    assert res_default is True
    assert not (mock_base / "dummy.txt").exists()


def test_parse_cookie_input():
    """Kiểm tra parse cookie JSON và chuỗi key=val."""
    # 1. Rỗng hoặc khoảng trắng
    assert parse_cookie_input("") == []
    assert parse_cookie_input("   ") == []

    # 2. JSON array từ Cookie-Editor
    json_str = """[
        {"name": "c_user", "value": "1000123456", "domain": ".facebook.com", "path": "/", "secure": true, "sameSite": "no_restriction"},
        {"name": "xs", "value": "abcdef%3A123", "domain": ".facebook.com", "path": "/", "httpOnly": true}
    ]"""
    cookies_json = parse_cookie_input(json_str)
    assert len(cookies_json) == 2
    assert cookies_json[0]["name"] == "c_user"
    assert cookies_json[0]["value"] == "1000123456"
    assert cookies_json[0]["domain"] == ".facebook.com"
    assert cookies_json[0]["secure"] is True
    assert cookies_json[0].get("sameSite") == "None" or cookies_json[0].get("sameSite") is None
    assert cookies_json[1]["name"] == "xs"
    assert cookies_json[1]["httpOnly"] is True

    # 3. Chuỗi c_user=...; xs=...
    raw_str = "c_user=1000999; xs=3456%3A9; fr=0xyz123;"
    cookies_raw = parse_cookie_input(raw_str)
    assert len(cookies_raw) == 3
    assert cookies_raw[0]["name"] == "c_user"
    assert cookies_raw[0]["value"] == "1000999"
    assert cookies_raw[0]["domain"] == ".facebook.com"
    assert cookies_raw[1]["name"] == "xs"
    assert cookies_raw[1]["value"] == "3456%3A9"


def test_save_cookies_to_profile(tmp_path, monkeypatch):
    """Kiểm tra lưu cookie vào profile."""
    mock_base = tmp_path / "browser_profile"
    mock_sub = mock_base / "profiles"
    monkeypatch.setattr("src.core.fb_crawler.PROFILE_DIR", mock_base)
    monkeypatch.setattr("src.core.fb_crawler.PROFILES_DIR", mock_sub)

    # 1. Cookie không hợp lệ
    success, msg = save_cookies_to_profile("default", "invalid_text")
    assert success is False
    assert "Không tìm thấy cookie hợp lệ" in msg

    # 2. Mock Playwright lưu thành công
    with patch("src.core.fb_crawler.sync_playwright") as mock_pw:
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_context

        valid_input = "c_user=10001; xs=sec_tok;"
        success, msg = save_cookies_to_profile("user_b", valid_input)
        assert success is True
        assert "Đã lưu thành công 2 cookies" in msg
        mock_context.add_cookies.assert_called_once()
        assert len(mock_context.add_cookies.call_args[0][0]) == 2


def test_load_and_save_profile_settings(tmp_path, monkeypatch):
    """Kiểm tra lưu và nạp cấu hình settings.json cho profile."""
    mock_base = tmp_path / "browser_profile"
    mock_sub = mock_base / "profiles"
    monkeypatch.setattr("src.core.fb_crawler.PROFILE_DIR", mock_base)
    monkeypatch.setattr("src.core.fb_crawler.PROFILES_DIR", mock_sub)

    # 1. Khi chưa có file settings.json, trả về defaults
    s1 = load_profile_settings("may_test")
    assert s1["max_reels"] == 20
    assert s1["check_comments"] is True
    assert s1["last_page_url"] == ""

    # 2. Lưu cấu hình mới
    custom_cfg = {
        "max_reels": 50,
        "delay_min": 1.5,
        "delay_max": 3.5,
        "check_comments": False,
        "headless": False,
        "last_page_url": "https://www.facebook.com/testpage"
    }
    save_profile_settings("may_test", custom_cfg)

    # 3. Nạp lại và kiểm tra
    s2 = load_profile_settings("may_test")
    assert s2["max_reels"] == 50
    assert s2["delay_min"] == 1.5
    assert s2["check_comments"] is False
    assert s2["last_page_url"] == "https://www.facebook.com/testpage"


def test_load_and_save_profile_last_results(tmp_path, monkeypatch):
    """Kiểm tra lưu và nạp kết quả cào gần nhất last_results.json."""
    mock_base = tmp_path / "browser_profile"
    mock_sub = mock_base / "profiles"
    monkeypatch.setattr("src.core.fb_crawler.PROFILE_DIR", mock_base)
    monkeypatch.setattr("src.core.fb_crawler.PROFILES_DIR", mock_sub)

    # 1. Khi chưa có kết quả
    assert load_profile_last_results("may_test") == []

    # 2. Lưu kết quả
    dummy = [
        {"reel_url": "https://fb.com/reel/1", "title": "Bài 1", "content": "Nội dung 1"},
        {"reel_url": "https://fb.com/reel/2", "title": "Bài 2", "content": "Nội dung 2"}
    ]
    save_profile_last_results("may_test", dummy)

    # 3. Nạp lại
    loaded = load_profile_last_results("may_test")
    assert len(loaded) == 2
    assert loaded[0]["title"] == "Bài 1"
    assert loaded[1]["reel_url"] == "https://fb.com/reel/2"


def test_clean_caption_text():
    assert clean_caption_text("") == ""
    assert clean_caption_text("This is original caption.") == "This is original caption."
    assert clean_caption_text("Caption text...\nẨn bản dịch") == "Caption text..."
    assert clean_caption_text("Caption text... Xem thêm\nẨn bản dịch") == "Caption text"
    assert clean_caption_text("Story details... See more\nSee original") == "Story details"
    assert clean_caption_text("Story details... See less") == "Story details"
    assert clean_caption_text("Some text\nRate this translation") == "Some text"


def test_run_crawler_pipeline_skip_duplicate_and_sequential_numbering(tmp_path):
    """Kiểm tra:
    1. Bỏ qua tải lại nếu video Reel đã tồn tại trong folder video/.
    2. Đánh số thứ tự nối tiếp (sequential numbering) cho video mới và caption mới.
    """
    video_dir = tmp_path / "video"
    caption_dir = tmp_path / "caption"
    video_dir.mkdir()
    caption_dir.mkdir()

    # Giả lập đã có video STT 1 của Reel 111 từ đợt trước
    old_vid = video_dir / "1_111.mp4"
    old_vid.write_bytes(b"existing video content")
    (caption_dir / "caption_1.txt").write_text("old caption 1", encoding="utf-8")

    with patch("src.core.fb_crawler.sync_playwright") as mock_pw, \
         patch("src.core.fb_crawler.extract_single_reel") as mock_extract, \
         patch("src.core.fb_crawler.download_reel_video") as mock_download:

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_context

        # Cào 2 reel: 111 (đã có) và 222 (mới)
        mock_extract.side_effect = [
            {
                "reel_url": "https://www.facebook.com/reel/111",
                "caption": "Caption 1 updated",
                "found_in": "Mô tả",
                "target_url": "",
                "title": "",
                "content": "",
                "status": "Thành công",
                "scraped_at": "2026-09-29 09:00:00"
            },
            {
                "reel_url": "https://www.facebook.com/reel/222",
                "caption": "Caption 2 new",
                "found_in": "Mô tả",
                "target_url": "",
                "title": "",
                "content": "",
                "status": "Thành công",
                "scraped_at": "2026-09-29 09:01:00"
            }
        ]

        mock_download.return_value = (True, str(video_dir / "2_222.mp4"), "Tải thành công")

        results = run_crawler_pipeline(
            input_type="list",
            target_data=[
                "https://www.facebook.com/reel/111",
                "https://www.facebook.com/reel/222"
            ],
            max_reels=2,
            download_video=True,
            video_output_dir=video_dir,
            caption_output_dir=caption_dir,
            auto_save_captions=True
        )

        assert len(results) == 2

        # 1. Reel 111: Đã có sẵn -> Giữ STT 1, video_path trỏ vào old_vid, download_reel_video KHÔNG gọi cho 111
        assert results[0]["stt"] == 1
        assert results[0]["video_path"] == str(old_vid)

        # 2. Reel 222: Video mới -> Đánh số tiếp theo là STT 2!
        assert results[1]["stt"] == 2
        assert results[1]["video_path"] == str(video_dir / "2_222.mp4")

        # 3. download_reel_video CHỈ được gọi đúng 1 lần cho Reel 222
        assert mock_download.call_count == 1
        call_args, call_kwargs = mock_download.call_args
        assert call_args[0] == "https://www.facebook.com/reel/222"
        assert call_kwargs["filename_template"] == "2_%(id)s.%(ext)s"

        # 4. Caption mới caption_2.txt được lưu
        assert (caption_dir / "caption_2.txt").exists()
        assert (caption_dir / "caption_2.txt").read_text(encoding="utf-8") == "Caption 2 new"


def test_crawler_pipeline_triggers_on_item_ready(tmp_path):
    """Kiểm tra run_crawler_pipeline gọi on_item_ready ngay khi video được tải xong."""
    from src.core.fb_crawler import run_crawler_pipeline

    ready_items = []
    def on_ready(item):
        ready_items.append(item)

    fake_vid = tmp_path / "1_123456789.mp4"
    fake_vid.write_bytes(b"dummy")

    with patch("src.core.fb_crawler.sync_playwright") as mock_pw, \
         patch("src.core.fb_crawler.extract_single_reel") as mock_extract, \
         patch("src.core.fb_crawler.download_reel_video") as mock_dl:

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_context

        mock_extract.return_value = {
            "reel_id": "123456789",
            "reel_url": "https://www.facebook.com/reel/123456789",
            "caption": "Reel Caption",
            "target_url": "",
            "title": "",
            "content": "",
            "status": "Thành công"
        }
        mock_dl.return_value = (True, str(fake_vid), "OK")

        results = run_crawler_pipeline(
            input_type="list",
            target_data=["https://www.facebook.com/reel/123456789"],
            max_reels=1,
            download_video=True,
            video_output_dir=str(tmp_path),
            on_item_ready=on_ready
        )

        assert len(results) == 1
        assert len(ready_items) == 1
        assert ready_items[0]["reel_id"] == "123456789"
        assert ready_items[0]["video_path"] == str(fake_vid)





