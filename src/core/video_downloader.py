import tempfile
import time
from pathlib import Path
import yt_dlp

from src.config import VIDEOS_DIR
from src.utils.logger import logger


def cookies_to_netscape_format(cookies: list[dict]) -> str:
    """Chuyển đổi danh sách cookies sang định dạng Netscape cookie file cho yt-dlp."""
    lines = [
        "# Netscape HTTP Cookie File",
        "# http://curl.haxx.se/rfc/cookie_spec.html",
        "# This is a generated file!  Do not edit.",
        ""
    ]
    now = int(time.time()) + 86400 * 30  # Default 30 days expiry
    for c in cookies:
        domain = c.get("domain", ".facebook.com")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure", False) else "FALSE"
        exp_val = c.get("expires")
        if exp_val is None or int(exp_val) <= 0:
            exp_val = now
        expires = str(int(exp_val))
        name = c.get("name", "")
        value = c.get("value", "")
        if name and value:
            lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
    return "\n".join(lines) + "\n"


def download_reel_video(
    reel_url: str,
    output_dir: Path | str | None = None,
    cookies_data: list[dict] | None = None,
    filename_template: str = "%(id)s.%(ext)s"
) -> tuple[bool, str, str]:
    """Tải video Facebook Reels bằng yt-dlp và lưu trực tiếp thành file .mp4.
    
    Returns:
        (success: bool, saved_filepath: str, message: str)
    """
    clean_url = (reel_url or "").strip()
    if not clean_url:
        return False, "", "URL Reel không hợp lệ hoặc rỗng."

    target_dir = Path(output_dir) if output_dir else VIDEOS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    temp_cookie_file = None
    try:
        ydl_opts = {
            "outtmpl": str(target_dir / filename_template),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 30,
        }

        if cookies_data:
            cookie_text = cookies_to_netscape_format(cookies_data)
            temp_cookie_file = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt")
            temp_cookie_file.write(cookie_text)
            temp_cookie_file.flush()
            temp_cookie_file.close()
            ydl_opts["cookiefile"] = temp_cookie_file.name

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            if not info:
                return False, "", "Không trích xuất được thông tin video từ Facebook."

            filename = ydl.prepare_filename(info)
            # Nếu đã merge thành .mp4
            p = Path(filename)
            mp4_path = p.with_suffix(".mp4")
            final_path = mp4_path if mp4_path.exists() else p

            if not final_path.exists():
                return False, "", f"Tải hoàn tất nhưng không tìm thấy file tại {final_path}."

            logger.info(f"Đã tải thành công video Reel: {final_path.name}")
            return True, str(final_path), f"Thành công: Đã lưu vào {final_path.name}"

    except Exception as e:
        logger.warning(f"Lỗi khi tải video Reel {clean_url}: {e}")
        return False, "", f"Lỗi tải video: {e}"
    finally:
        if temp_cookie_file:
            try:
                Path(temp_cookie_file.name).unlink(missing_ok=True)
            except Exception:
                pass
