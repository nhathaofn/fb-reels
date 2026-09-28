import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import httpx

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from article_extractor import extract_article_from_html, resolve_target_url, extract_article


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


def test_extract_article_from_html_empty_input():
    result = extract_article_from_html("")
    assert result["status"] == "HTML rỗng"
    assert result["title"] == ""
    assert result["content"] == ""


def test_extract_article_from_html_fallback_og_title():
    sample_html = """
    <html>
    <head>
        <meta property="og:title" content="Fallback OG Title" />
    </head>
    <body>
        <p>Đây là nội dung bài viết với fallback title nhằm kiểm tra trích xuất metadata.</p>
    </body>
    </html>
    """
    result = extract_article_from_html(sample_html, "https://example.com/fallback-og")
    assert "Fallback OG Title" in result["title"]


def test_extract_article_from_html_fallback_tag_title():
    sample_html = """
    <html>
    <head>
        <title>Fallback Tag Title</title>
    </head>
    <body>
        <p>Đây là nội dung bài viết với fallback title nhằm kiểm tra trích xuất thẻ title.</p>
    </body>
    </html>
    """
    result = extract_article_from_html(sample_html, "https://example.com/fallback-tag")
    assert "Fallback Tag Title" in result["title"]


def test_resolve_target_url_empty():
    assert resolve_target_url("") == ""


def test_resolve_target_url_head_success():
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.url = "https://example.com/final-destination"
        mock_client.head.return_value = mock_response
        mock_client.__enter__.return_value = mock_client

        mock_client_cls.return_value = mock_client

        resolved = resolve_target_url("https://t.co/shortlink")
        assert resolved == "https://example.com/final-destination"
        mock_client.head.assert_called_once_with("https://t.co/shortlink")


def test_resolve_target_url_head_fails_get_succeeds():
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.head.side_effect = httpx.RequestError("HEAD method not allowed")
        mock_response = MagicMock()
        mock_response.url = "https://example.com/from-get"
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client

        mock_client_cls.return_value = mock_client

        resolved = resolve_target_url("https://short.io/link")
        assert resolved == "https://example.com/from-get"


def test_resolve_target_url_all_fail():
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.head.side_effect = httpx.ConnectError("Network down")
        mock_client.get.side_effect = httpx.ConnectError("Network down")
        mock_client.__enter__.return_value = mock_client

        mock_client_cls.return_value = mock_client

        original = "https://failing-domain.com/path"
        resolved = resolve_target_url(original)
        assert resolved == original


def test_extract_article_empty_url():
    result = extract_article("")
    assert result["status"] == "Không có link web"
    assert result["title"] == ""
    assert result["content"] == ""


def test_extract_article_http_error():
    with patch("article_extractor.resolve_target_url", return_value="https://example.com/404"):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.get.return_value = mock_response
            mock_client.__enter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            result = extract_article("https://example.com/404")
            assert result["status"] == "Lỗi HTTP 404"


def test_extract_article_network_exception():
    with patch("article_extractor.resolve_target_url", return_value="https://example.com/error"):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectTimeout("Connection timed out")
            mock_client.__enter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            result = extract_article("https://example.com/error")
            assert "Lỗi tải trang" in result["status"]
            assert "ConnectTimeout" in result["status"]


def test_extract_article_success():
    html_content = """
    <html>
    <head><title>Trang tin tức</title></head>
    <body>
        <h1>Trang tin tức</h1>
        <p>Đây là bài viết đầy đủ đã được trích xuất thành công từ trang web.</p>
    </body>
    </html>
    """
    with patch("article_extractor.resolve_target_url", return_value="https://example.com/news/1"):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = html_content
            mock_client.get.return_value = mock_response
            mock_client.__enter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            result = extract_article("https://example.com/news/1")
            assert result["status"] == "Thành công"
            assert "Trang tin tức" in result["title"]
            assert "Đây là bài viết đầy đủ" in result["content"]
