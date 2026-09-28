import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app
from app import (
    build_display_dataframe,
    make_progress_callback,
    parse_reels_input,
    render_sidebar,
    should_stop_crawl,
    main,
)
from exporter import COLUMNS_MAP


def test_module_structure_and_imports():
    """Kiểm tra sự tồn tại của các hàm cốt lõi trong module app."""
    assert callable(build_display_dataframe)
    assert callable(parse_reels_input)
    assert callable(make_progress_callback)
    assert callable(render_sidebar)
    assert callable(should_stop_crawl)
    assert callable(main)


def test_parse_reels_input_empty():
    """Kiểm tra xử lý danh sách đầu vào rỗng."""
    assert parse_reels_input("", "") == []
    assert parse_reels_input("   \n\n  ", None) == []


def test_parse_reels_input_text_only():
    """Kiểm tra bóc tách URL từ văn bản người dùng nhập."""
    raw_text = (
        "https://www.facebook.com/reel/111\n"
        "\n"
        "  https://www.facebook.com/reel/222  \n"
        "https://www.facebook.com/reel/333\n"
    )
    urls = parse_reels_input(raw_text)
    assert urls == [
        "https://www.facebook.com/reel/111",
        "https://www.facebook.com/reel/222",
        "https://www.facebook.com/reel/333",
    ]


def test_parse_reels_input_file_only():
    """Kiểm tra bóc tách URL từ nội dung file tải lên."""
    file_content = (
        "https://www.facebook.com/reel/444\r\n"
        "https://www.facebook.com/reel/555\r\n"
    )
    urls = parse_reels_input("", file_content)
    assert urls == [
        "https://www.facebook.com/reel/444",
        "https://www.facebook.com/reel/555",
    ]


def test_parse_reels_input_combined_and_deduplicate():
    """Kiểm tra kết hợp textarea và file tải lên, tự động loại bỏ trùng lặp và giữ nguyên thứ tự."""
    text_input = "https://www.facebook.com/reel/111\nhttps://www.facebook.com/reel/222"
    file_input = "https://www.facebook.com/reel/222\nhttps://www.facebook.com/reel/333\nhttps://www.facebook.com/reel/111"

    urls = parse_reels_input(text_input, file_input)
    assert urls == [
        "https://www.facebook.com/reel/111",
        "https://www.facebook.com/reel/222",
        "https://www.facebook.com/reel/333",
    ]


def test_build_display_dataframe_empty():
    """Kiểm tra tạo DataFrame hiển thị khi chưa có bản ghi nào."""
    df = build_display_dataframe([])
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == list(COLUMNS_MAP.values())
    assert len(df) == 0


def test_build_display_dataframe_with_data():
    """Kiểm tra định dạng và cấu trúc dữ liệu hiển thị có đúng cột tiếng Việt và STT."""
    records = [
        {
            "reel_url": "https://www.facebook.com/reel/100",
            "caption": "Reel review phim hay",
            "found_in": "Trong mô tả",
            "target_url": "https://example.com/movie-review",
            "title": "Top phim hay 2026",
            "content": "Nội dung chi tiết bài viết...",
            "status": "Thành công",
            "scraped_at": "2026-09-28 10:00:00",
        },
        {
            "reel_url": "https://www.facebook.com/reel/200",
            "caption": "Video ngắn thú vị",
            "found_in": "Không tìm thấy",
            "target_url": "",
            "title": "",
            "content": "",
            "status": "Không tìm thấy link web",
            "scraped_at": "2026-09-28 10:01:00",
        },
    ]

    df = build_display_dataframe(records)
    assert len(df) == 2
    assert list(df.columns) == list(COLUMNS_MAP.values())
    assert df.iloc[0]["STT"] == 1
    assert df.iloc[1]["STT"] == 2
    assert df.iloc[0]["Link Reel"] == "https://www.facebook.com/reel/100"
    assert df.iloc[0]["Vị trí tìm thấy link"] == "Trong mô tả"
    assert df.iloc[0]["Tiêu đề bài viết"] == "Top phim hay 2026"
    assert df.iloc[1]["Trạng thái"] == "Không tìm thấy link web"


def test_build_display_dataframe_missing_fields():
    """Kiểm tra xử lý các bản ghi khuyết trường dữ liệu."""
    partial_record = [{"reel_url": "https://www.facebook.com/reel/999"}]
    df = build_display_dataframe(partial_record)
    assert len(df) == 1
    assert df.iloc[0]["STT"] == 1
    assert df.iloc[0]["Link Reel"] == "https://www.facebook.com/reel/999"
    assert df.iloc[0]["Mô tả Reel"] == ""
    assert df.iloc[0]["Link Web"] == ""


def test_make_progress_callback_progress_and_message():
    """Kiểm tra callback cập nhật thanh tiến trình và thông báo trạng thái."""
    mock_bar = MagicMock()
    mock_status = MagicMock()
    mock_table = MagicMock()
    results = []

    cb = make_progress_callback(mock_bar, mock_status, mock_table, results)

    # Khi cào đang duyệt tìm kiếm (item_data là None, total_count=0)
    cb(0, 0, "Đang quét danh sách...", None)
    mock_status.info.assert_called_with("Đang quét danh sách...")
    mock_bar.progress.assert_not_called()
    assert len(results) == 0

    # Khi đang cào reel 1/4 (chưa xong item_data)
    cb(1, 4, "Đang xử lý Reel 1/4", None)
    mock_bar.progress.assert_called_with(0.25)
    mock_status.info.assert_called_with("Đang xử lý Reel 1/4")
    assert len(results) == 0


def test_make_progress_callback_item_data_update():
    """Kiểm tra callback khi hoàn tất 1 reel và trả về dữ liệu item."""
    mock_bar = MagicMock()
    mock_status = MagicMock()
    mock_table = MagicMock()
    results = []

    cb = make_progress_callback(mock_bar, mock_status, mock_table, results)

    item = {
        "reel_url": "https://www.facebook.com/reel/1",
        "caption": "Cap 1",
        "found_in": "Trong mô tả",
        "target_url": "https://test.com",
        "title": "Test Title",
        "content": "Test Content",
        "status": "Thành công",
        "scraped_at": "2026-09-28 10:00:00",
    }

    cb(1, 2, "Đã hoàn thành Reel 1/2", item)

    assert len(results) == 1
    assert results[0] == item
    mock_bar.progress.assert_called_with(0.5)
    mock_status.info.assert_called_with("Đã hoàn thành Reel 1/2")
    mock_table.dataframe.assert_called_once()


def test_make_progress_callback_none_handles_safely():
    """Kiểm tra callback hoạt động an toàn khi các đối tượng UI là None."""
    results = []
    cb = make_progress_callback(None, None, None, results)

    # Không gây ra Exception
    cb(1, 5, "Thông báo kiểm tra", {"reel_url": "https://test.com/reel/1"})
    assert len(results) == 1


@patch("app.has_logged_in_session")
@patch("app.st")
def test_render_sidebar_logged_in(mock_st, mock_has_session):
    """Kiểm tra render sidebar khi đã có phiên đăng nhập."""
    mock_has_session.return_value = True
    mock_st.number_input.return_value = 25
    mock_st.slider.return_value = (2.0, 5.0)
    mock_st.checkbox.side_effect = [True, False]
    mock_st.button.return_value = False

    max_reels, delay_range, check_comments, headless = render_sidebar()

    mock_st.success.assert_called_with("🟢 Đã có phiên đăng nhập")
    assert max_reels == 25
    assert delay_range == (2.0, 5.0)
    assert check_comments is True
    assert headless is False


@patch("app.has_logged_in_session")
@patch("app.st")
def test_render_sidebar_not_logged_in(mock_st, mock_has_session):
    """Kiểm tra render sidebar khi chưa có phiên đăng nhập."""
    mock_has_session.return_value = False
    mock_st.number_input.return_value = 10
    mock_st.slider.return_value = (3.0, 6.0)
    mock_st.checkbox.side_effect = [False, True]
    mock_st.button.return_value = False

    max_reels, delay_range, check_comments, headless = render_sidebar()

    mock_st.warning.assert_called_with("🟡 Chưa đăng nhập")
    assert max_reels == 10
    assert check_comments is False
    assert headless is True


@patch("app.launch_login_browser")
@patch("app.has_logged_in_session")
@patch("app.st")
def test_render_sidebar_launch_login(mock_st, mock_has_session, mock_launch):
    """Kiểm tra nhấn nút mở trình duyệt đăng nhập trong sidebar."""
    mock_has_session.return_value = False
    mock_st.button.return_value = True
    mock_st.number_input.return_value = 20
    mock_st.slider.return_value = (2.0, 5.0)
    mock_st.checkbox.side_effect = [True, True]

    render_sidebar()

    mock_launch.assert_called_once_with(headless=False)
    mock_st.rerun.assert_called_once()


def _mock_columns(spec):
    count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
    return [MagicMock() for _ in range(count)]


@patch("app.render_sidebar")
@patch("app.st")
def test_main_initial_render(mock_st, mock_render_sidebar):
    """Kiểm tra render trang chính khi không có thao tác cào."""
    mock_render_sidebar.return_value = (20, (2.0, 5.0), True, True)

    mock_tab1 = MagicMock()
    mock_tab2 = MagicMock()
    mock_st.tabs.return_value = [mock_tab1, mock_tab2]
    mock_st.session_state = {}
    mock_st.columns.side_effect = _mock_columns

    # Giả lập người dùng chưa nhấn nút nào
    mock_st.button.return_value = False

    main()

    mock_st.set_page_config.assert_called_once_with(
        page_title="Facebook Reels & Article Extractor",
        page_icon="🎬",
        layout="wide",
    )
    assert "results" in mock_st.session_state
    assert mock_st.session_state["results"] == []


@patch("app.export_to_excel")
@patch("app.get_excel_bytes")
@patch("app.run_crawler_pipeline")
@patch("app.render_sidebar")
@patch("app.st")
def test_main_trigger_crawl_page(
    mock_st,
    mock_render_sidebar,
    mock_crawler,
    mock_get_bytes,
    mock_export,
    tmp_path,
):
    """Kiểm tra kích hoạt cào từ Tab 1 (Fanpage URL)."""
    mock_render_sidebar.return_value = (10, (2.0, 4.0), True, True)
    mock_tab1 = MagicMock()
    mock_tab2 = MagicMock()
    mock_st.tabs.return_value = [mock_tab1, mock_tab2]
    mock_st.session_state = {}

    # Giả lập người dùng nhập link và bấm nút cào ở Tab 1
    mock_st.text_input.return_value = "https://www.facebook.com/kenh14.vn"
    # start_tab1 (True), btn_stop_page (False), start_tab2 (False), btn_stop_list (False)
    mock_st.button.side_effect = [True, False, False, False]

    dummy_results = [{"reel_url": "https://www.facebook.com/reel/1", "status": "Thành công"}]
    mock_crawler.return_value = dummy_results
    test_file = tmp_path / "test.xlsx"
    mock_export.return_value = test_file
    mock_get_bytes.return_value = b"excelbytes"
    mock_st.columns.side_effect = _mock_columns

    main()

    mock_crawler.assert_called_once()
    call_kwargs = mock_crawler.call_args[1]
    assert call_kwargs["input_type"] == "page"
    assert call_kwargs["target_data"] == "https://www.facebook.com/kenh14.vn"
    assert call_kwargs["max_reels"] == 10
    assert mock_st.session_state["results"] == dummy_results
    assert mock_st.session_state["excel_bytes"] == b"excelbytes"


@patch("app.export_to_excel")
@patch("app.get_excel_bytes")
@patch("app.run_crawler_pipeline")
@patch("app.render_sidebar")
@patch("app.st")
def test_main_trigger_crawl_list(
    mock_st,
    mock_render_sidebar,
    mock_crawler,
    mock_get_bytes,
    mock_export,
    tmp_path,
):
    """Kiểm tra kích hoạt cào từ Tab 2 (Danh sách URL Reels lẻ)."""
    mock_render_sidebar.return_value = (5, (1.0, 3.0), False, False)
    mock_tab1 = MagicMock()
    mock_tab2 = MagicMock()
    mock_st.tabs.return_value = [mock_tab1, mock_tab2]
    mock_st.session_state = {}

    # Giả lập người dùng nhập danh sách link ở Tab 2
    mock_st.text_area.return_value = "https://www.facebook.com/reel/111\nhttps://www.facebook.com/reel/222"
    mock_st.file_uploader.return_value = None
    # start_tab1 (False), btn_stop_page (False), start_tab2 (True), btn_stop_list (False)
    mock_st.button.side_effect = [False, False, True, False]

    dummy_results = [
        {"reel_url": "https://www.facebook.com/reel/111", "status": "Thành công"},
        {"reel_url": "https://www.facebook.com/reel/222", "status": "Thành công"},
    ]
    mock_crawler.return_value = dummy_results
    test_file = tmp_path / "test_list.xlsx"
    mock_export.return_value = test_file
    mock_get_bytes.return_value = b"bytes_list"
    mock_st.columns.side_effect = _mock_columns

    main()

    mock_crawler.assert_called_once()
    call_kwargs = mock_crawler.call_args[1]
    assert call_kwargs["input_type"] == "list"
    assert call_kwargs["target_data"] == [
        "https://www.facebook.com/reel/111",
        "https://www.facebook.com/reel/222",
    ]
    assert call_kwargs["max_reels"] == 5
    assert call_kwargs["check_comments"] is False
    assert call_kwargs["headless"] is False
    assert mock_st.session_state["results"] == dummy_results
    assert mock_st.session_state["excel_bytes"] == b"bytes_list"


def test_should_stop_crawl():
    """Kiểm tra logic cờ should_stop_crawl từ session_state."""
    with patch("app.st") as mock_st:
        mock_st.session_state = {}
        assert should_stop_crawl() is False

        mock_st.session_state = {"stop_crawling": False}
        assert should_stop_crawl() is False

        mock_st.session_state = {"stop_crawling": True}
        assert should_stop_crawl() is True


def test_make_progress_callback_with_stop_check():
    """Kiểm tra callback trả về False khi cờ dừng được bật."""
    mock_bar = MagicMock()
    mock_status = MagicMock()
    mock_table = MagicMock()
    results = []

    # Giả lập cờ dừng trả về True
    cb = make_progress_callback(
        mock_bar,
        mock_status,
        mock_table,
        results,
        stop_check=lambda: True
    )

    res = cb(1, 5, "Đang cào...", None)
    assert res is False
    # Không tiếp tục cập nhật UI khi đã dừng
    mock_bar.progress.assert_not_called()


def test_file_upload_bom_handling():
    """Kiểm tra file txt có BOM UTF-8 (từ Notepad Windows) được decode chính xác và không bị lỗi \ufeff."""
    bom_content = "\ufeffhttps://www.facebook.com/reel/111\nhttps://www.facebook.com/reel/222".encode("utf-8")
    mock_file = MagicMock()
    mock_file.getvalue.return_value = bom_content

    decoded_text = mock_file.getvalue().decode("utf-8-sig", errors="ignore")
    urls = parse_reels_input("", decoded_text)
    assert urls == [
        "https://www.facebook.com/reel/111",
        "https://www.facebook.com/reel/222",
    ]
    assert not urls[0].startswith("\ufeff")


@patch("app.render_sidebar")
@patch("app.st")
def test_main_click_stop_button(mock_st, mock_render_sidebar):
    """Kiểm tra người dùng nhấn nút Dừng cào trong Tab 1."""
    mock_render_sidebar.return_value = (10, (2.0, 4.0), True, True)
    mock_tab1 = MagicMock()
    mock_tab2 = MagicMock()
    mock_st.tabs.return_value = [mock_tab1, mock_tab2]
    mock_st.session_state = {}
    mock_st.columns.side_effect = _mock_columns

    # Giả lập bấm nút Dừng ở Tab 1
    # Buttons trong main:
    # 1. start_tab1 (False)
    # 2. btn_stop_page (True)
    # 3. start_tab2 (False)
    # 4. btn_stop_list (False)
    mock_st.button.side_effect = [False, True, False, False]

    main()

    assert mock_st.session_state["stop_crawling"] is True
    mock_st.toast.assert_called_with("⏹️ Đang gửi tín hiệu dừng cào...")
