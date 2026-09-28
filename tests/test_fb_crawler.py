import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fb_crawler import (
    normalize_reels_url,
    extract_urls_from_text,
    has_logged_in_session,
    crawl_reels_from_tab,
    extract_single_reel,
    run_crawler_pipeline,
    crawl_reels,
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
    test_profile = tmp_path / "browser_profile"
    monkeypatch.setattr("fb_crawler.PROFILE_DIR", test_profile)

    # Thư mục chưa tồn tại
    assert has_logged_in_session() is False

    # Thư mục rỗng
    test_profile.mkdir()
    assert has_logged_in_session() is False

    # Có file Cookies
    cookies_file = test_profile / "Default" / "Network" / "Cookies"
    cookies_file.parent.mkdir(parents=True)
    cookies_file.write_text("dummy_cookie")
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

    urls = crawl_reels_from_tab(mock_page, "https://www.facebook.com/kenh14.vn/reels/", max_count=2, delay_range=(0.01, 0.02))
    
    assert len(urls) == 2
    assert urls[0] == "https://www.facebook.com/reel/100001"
    assert urls[1] == "https://www.facebook.com/reel/100002"
    mock_page.goto.assert_called_once_with("https://www.facebook.com/kenh14.vn/reels/", wait_until="domcontentloaded", timeout=45000)


def test_extract_single_reel_caption_url():
    mock_page = MagicMock()
    
    # Mock caption elements
    cap_el = MagicMock()
    cap_el.inner_text.return_value = "Tin tức nóng hôm nay xem tại https://vnexpress.net/tin-nong-123.htm"
    mock_page.query_selector_all.return_value = [cap_el]

    with patch("fb_crawler.extract_article") as mock_extract:
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

    with patch("fb_crawler.extract_article") as mock_extract:
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

    with patch("fb_crawler.sync_playwright") as mock_playwright_ctx, \
         patch("fb_crawler.crawl_reels_from_tab") as mock_crawl_tab, \
         patch("fb_crawler.extract_single_reel") as mock_extract_single:

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
            {"reel_url": "https://www.facebook.com/reel/111", "title": "Tin 1"},
            {"reel_url": "https://www.facebook.com/reel/222", "title": "Tin 2"}
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
        assert results[0]["title"] == "Tin 1"
        assert results[1]["title"] == "Tin 2"
        assert mock_callback.call_count >= 2
        mock_context.close.assert_called_once()


def test_run_crawler_pipeline_list_mode_and_crawl_reels():
    with patch("fb_crawler.sync_playwright") as mock_playwright_ctx, \
         patch("fb_crawler.extract_single_reel") as mock_extract_single:

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
    with patch("fb_crawler.sync_playwright") as mock_playwright_ctx, \
         patch("fb_crawler.crawl_reels_from_tab") as mock_crawl_tab:

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

    with patch("fb_crawler.sync_playwright") as mock_playwright_ctx, \
         patch("fb_crawler.extract_single_reel") as mock_extract_single:

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
    with patch("fb_crawler.sync_playwright") as mock_pw, \
         patch("fb_crawler.extract_single_reel") as mock_extract:

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

