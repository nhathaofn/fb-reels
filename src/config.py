import os
import sys
from pathlib import Path

# Đảm bảo đường dẫn luôn là tương đối, chính xác dù chạy mã nguồn .py hay chạy file đóng gói .exe
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

SRC_DIR = BASE_DIR / "src"
PROFILE_DIR = BASE_DIR / "browser_profile"
PROFILES_DIR = PROFILE_DIR / "profiles"
OUTPUT_DIR = BASE_DIR / "output"
EXCEL_DIR = OUTPUT_DIR / "excel"
VIDEOS_DIR = OUTPUT_DIR / "videos"
CAPTIONS_DIR = OUTPUT_DIR / "captions"

# Đảm bảo các thư mục tồn tại
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
EXCEL_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
CAPTIONS_DIR.mkdir(parents=True, exist_ok=True)

# Cấu hình có thể ghi đè qua biến môi trường hoặc dùng giá trị mặc định tối ưu
DEFAULT_MAX_REELS = int(os.getenv("DEFAULT_MAX_REELS", "20"))
MIN_DELAY = float(os.getenv("MIN_DELAY", "2.0"))
MAX_DELAY = float(os.getenv("MAX_DELAY", "5.0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15.0"))

USER_AGENT = os.getenv(
    "USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
)

BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "msedge")
BROWSER_LOCALE = os.getenv("BROWSER_LOCALE", "en-US")
EXTRA_HTTP_HEADERS = {
    "Accept-Language": f"{BROWSER_LOCALE},en;q=0.9",
}

