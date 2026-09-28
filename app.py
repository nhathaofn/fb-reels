from datetime import datetime
import pandas as pd
import streamlit as st

from config import DEFAULT_MAX_REELS, MAX_DELAY, MIN_DELAY, OUTPUT_DIR
from exporter import COLUMNS_MAP, export_to_excel, get_excel_bytes
from fb_crawler import has_logged_in_session, launch_login_browser, run_crawler_pipeline


def build_display_dataframe(records: list[dict]) -> pd.DataFrame:
    """Chuyển đổi danh sách bản ghi cào được thành DataFrame có tên cột tiếng Việt."""
    if not records:
        return pd.DataFrame(columns=list(COLUMNS_MAP.values()))

    rows = []
    for idx, rec in enumerate(records, start=1):
        row = {
            "STT": idx,
            "Link Reel": rec.get("reel_url", ""),
            "Mô tả Reel": rec.get("caption", ""),
            "Vị trí tìm thấy link": rec.get("found_in", ""),
            "Link Web": rec.get("target_url", ""),
            "Tiêu đề bài viết": rec.get("title", ""),
            "Nội dung bài viết": rec.get("content", ""),
            "Trạng thái": rec.get("status", ""),
            "Thời gian cào": rec.get("scraped_at", ""),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def parse_reels_input(text_content: str = "", file_content: str = "") -> list[str]:
    """Phân tích và trích xuất danh sách URL Reels từ textarea và file tải lên."""
    combined_lines = []
    if text_content:
        combined_lines.extend(text_content.splitlines())
    if file_content:
        combined_lines.extend(file_content.splitlines())

    urls = []
    for line in combined_lines:
        clean = line.strip()
        if clean and clean not in urls:
            urls.append(clean)
    return urls


def should_stop_crawl() -> bool:
    """Kiểm tra xem người dùng đã bấm nút yêu cầu dừng cào hay chưa."""
    return bool(st.session_state.get("stop_crawling", False))


def make_progress_callback(
    progress_bar,
    status_text,
    table_placeholder,
    results_holder: list,
    stop_check=None
):
    """Tạo hàm callback cập nhật tiến trình cào dữ liệu lên giao diện Streamlit."""
    def callback(current_idx: int, total_count: int, message: str, item_data: dict | None):
        if stop_check and stop_check():
            return False

        if total_count > 0:
            fraction = min(max(current_idx / total_count, 0.0), 1.0)
            if progress_bar is not None:
                progress_bar.progress(fraction)
        if status_text is not None and message:
            status_text.info(message)
        if item_data is not None:
            results_holder.append(item_data)
            if table_placeholder is not None:
                df = build_display_dataframe(results_holder)
                table_placeholder.dataframe(df, use_container_width=True)
        return True
    return callback


def render_sidebar():
    """Hiển thị sidebar cấu hình và trạng thái tài khoản Facebook."""
    with st.sidebar:
        st.header("🔐 Trạng thái tài khoản")
        is_logged_in = has_logged_in_session()
        if is_logged_in:
            st.success("🟢 Đã có phiên đăng nhập")
        else:
            st.warning("🟡 Chưa đăng nhập")
            st.caption("Khuyên dùng: Đăng nhập trước khi cào để hạn chế checkpoint và tránh bị Facebook chặn.")

        if st.button("🔐 Mở trình duyệt đăng nhập Facebook", use_container_width=True):
            st.info("Đang mở trình duyệt Chromium... Vui lòng đăng nhập Facebook rồi đóng cửa sổ trình duyệt.")
            launch_login_browser(headless=False)
            st.rerun()

        st.markdown("---")
        st.header("⚙️ Cấu hình cào")
        max_reels = st.number_input(
            "Số lượng Reels tối đa:",
            min_value=1,
            max_value=500,
            value=DEFAULT_MAX_REELS,
            step=1,
            help="Số lượng video Reels tối đa cần lấy trên mỗi Fanpage hoặc từ danh sách."
        )
        delay_range = st.slider(
            "Khoảng delay ngẫu nhiên (giây):",
            min_value=1.0,
            max_value=20.0,
            value=(MIN_DELAY, MAX_DELAY),
            step=0.5,
            help="Thời gian nghỉ ngẫu nhiên giữa các thao tác để tránh bị Facebook nghi vấn bot."
        )
        check_comments = st.checkbox(
            "Quét link trong bình luận",
            value=True,
            help="Nếu mô tả video không chứa link ngoài, mở khu vực bình luận để tìm link."
        )
        headless = st.checkbox(
            "Chạy ẩn trình duyệt (Headless)",
            value=True,
            help="Bật để trình duyệt chạy ngầm (tiết kiệm tài nguyên), tắt để hiển thị cửa sổ trực quan."
        )

        st.markdown("---")
        st.caption(f"📁 Dữ liệu xuất tự động lưu vào: `{OUTPUT_DIR}`")

        return int(max_reels), delay_range, check_comments, headless


def main():
    st.set_page_config(
        page_title="Facebook Reels & Article Extractor",
        page_icon="🎬",
        layout="wide"
    )

    st.title("🎬 Facebook Reels & Article Extractor")
    st.markdown(
        "Công cụ tự động quét video Facebook Reels, trích xuất link đích trong mô tả / bình luận "
        "và cào nội dung bài viết website xuất ra file Excel."
    )

    # Khởi tạo session_state
    if "results" not in st.session_state:
        st.session_state["results"] = []
    if "excel_bytes" not in st.session_state:
        st.session_state["excel_bytes"] = None
    if "saved_filename" not in st.session_state:
        st.session_state["saved_filename"] = ""
    if "stop_crawling" not in st.session_state:
        st.session_state["stop_crawling"] = False

    max_reels, delay_range, check_comments, headless = render_sidebar()

    # Main content tabs
    tab1, tab2 = st.tabs(["🏢 Cào theo Fanpage / Profile", "🔗 Cào theo danh sách Reels lẻ"])

    crawl_target_type = None
    crawl_target_data = None
    start_crawling = False

    with tab1:
        st.markdown("##### Quét tự động toàn bộ video Reels từ trang Fanpage hoặc Profile cá nhân")
        page_url_input = st.text_input(
            "Nhập link Fanpage hoặc Profile Facebook:",
            placeholder="https://www.facebook.com/username hoặc https://www.facebook.com/profile.php?id=...",
            key="page_url_input"
        )
        col_b1, col_b2 = st.columns([3, 1])
        with col_b1:
            start_tab1 = st.button("🚀 Bắt đầu cào nội dung", key="btn_crawl_page", type="primary")
        with col_b2:
            if st.button("⏹️ Dừng cào", key="btn_stop_page"):
                st.session_state["stop_crawling"] = True
                st.toast("⏹️ Đang gửi tín hiệu dừng cào...")

        if start_tab1:
            if not page_url_input.strip():
                st.warning("⚠️ Vui lòng nhập link Fanpage hoặc Profile Facebook!")
            else:
                crawl_target_type = "page"
                crawl_target_data = page_url_input.strip()
                start_crawling = True

    with tab2:
        st.markdown("##### Cào dữ liệu theo danh sách link video Reels cụ thể")
        reels_text_input = st.text_area(
            "Dán danh sách link Reels (mỗi dòng 1 link):",
            placeholder="https://www.facebook.com/reel/123456789\nhttps://www.facebook.com/reel/987654321",
            height=130,
            key="reels_text_input"
        )
        uploaded_txt_file = st.file_uploader(
            "Hoặc tải lên file .txt chứa danh sách link Reels:",
            type=["txt"],
            key="reels_file_upload"
        )
        col_b3, col_b4 = st.columns([3, 1])
        with col_b3:
            start_tab2 = st.button("🚀 Bắt đầu cào nội dung", key="btn_crawl_list", type="primary")
        with col_b4:
            if st.button("⏹️ Dừng cào", key="btn_stop_list"):
                st.session_state["stop_crawling"] = True
                st.toast("⏹️ Đang gửi tín hiệu dừng cào...")

        if start_tab2:
            file_text = ""
            if uploaded_txt_file is not None:
                file_text = uploaded_txt_file.getvalue().decode("utf-8-sig", errors="ignore")
            parsed_urls = parse_reels_input(reels_text_input, file_text)
            if not parsed_urls:
                st.warning("⚠️ Vui lòng dán link Reels hoặc tải lên file .txt hợp lệ!")
            else:
                crawl_target_type = "list"
                crawl_target_data = parsed_urls
                start_crawling = True

    # Khu vực hiển thị tiến trình và kết quả
    progress_container = st.container()

    if start_crawling and crawl_target_type and crawl_target_data:
        st.session_state["results"] = []
        st.session_state["excel_bytes"] = None
        st.session_state["saved_filename"] = ""
        st.session_state["stop_crawling"] = False

        with progress_container:
            st.markdown("---")
            st.subheader("⏳ Tiến trình cào dữ liệu")
            progress_bar = st.progress(0.0)
            status_text = st.empty()
            table_placeholder = st.empty()

            live_results = []
            callback = make_progress_callback(
                progress_bar=progress_bar,
                status_text=status_text,
                table_placeholder=table_placeholder,
                results_holder=live_results,
                stop_check=should_stop_crawl
            )

            status_text.info("🚀 Đang khởi động trình duyệt và bắt đầu cào...")

            try:
                results = run_crawler_pipeline(
                    input_type=crawl_target_type,
                    target_data=crawl_target_data,
                    max_reels=max_reels,
                    check_comments=check_comments,
                    delay_range=delay_range,
                    headless=headless,
                    progress_callback=callback,
                    stop_check_callback=should_stop_crawl
                )

                was_stopped = should_stop_crawl()
                st.session_state["stop_crawling"] = False

                if not results:
                    progress_bar.progress(1.0)
                    if was_stopped:
                        status_text.warning("⏹️ Đã dừng cào theo yêu cầu của người dùng. Chưa có dữ liệu nào được cào.")
                    else:
                        status_text.warning("⚠️ Không tìm thấy hoặc không cào được video Reel nào.")
                else:
                    progress_bar.progress(1.0)
                    saved_path = export_to_excel(results)
                    excel_bytes = get_excel_bytes(results)

                    st.session_state["results"] = results
                    st.session_state["excel_bytes"] = excel_bytes
                    st.session_state["saved_filename"] = saved_path.name

                    if was_stopped:
                        status_text.warning(
                            f"⏹️ Đã dừng cào theo yêu cầu! Đã lưu {len(results)} Reels đã cào được vào `{OUTPUT_DIR / saved_path.name}`."
                        )
                    else:
                        status_text.success(
                            f"🎉 Hoàn thành cào dữ liệu! Đã xử lý {len(results)} Reels. "
                            f"File Excel đã được lưu tự động tại `{OUTPUT_DIR / saved_path.name}`."
                        )
            except Exception as e:
                status_text.error(f"❌ Có lỗi xảy ra trong quá trình cào dữ liệu: {e}")

    # Hiển thị kết quả và nút tải xuống nếu đã có kết quả
    if st.session_state.get("results"):
        st.markdown("---")
        st.subheader("📊 Kết quả trích xuất")
        results = st.session_state["results"]

        col1, col2, col3 = st.columns(3)
        total_reels = len(results)
        links_found = sum(1 for r in results if r.get("target_url"))
        articles_extracted = sum(1 for r in results if r.get("content"))

        col1.metric("Tổng số Reels", total_reels)
        col2.metric("Tìm thấy Link Web", links_found)
        col3.metric("Bài viết trích xuất", articles_extracted)

        display_df = build_display_dataframe(results)
        st.dataframe(display_df, use_container_width=True)

        down_col1, down_col2 = st.columns(2)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with down_col1:
            if st.session_state.get("excel_bytes"):
                st.download_button(
                    label="📥 Tải xuống file Excel (.xlsx)",
                    data=st.session_state["excel_bytes"],
                    file_name=f"reels_content_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="btn_download_excel"
                )
        with down_col2:
            csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 Tải xuống file CSV (.csv)",
                data=csv_bytes,
                file_name=f"reels_content_{timestamp}.csv",
                mime="text/csv",
                use_container_width=True,
                key="btn_download_csv"
            )


if __name__ == "__main__":
    main()
