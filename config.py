from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "browser_profile"
OUTPUT_DIR = BASE_DIR / "output"

# Đảm bảo các thư mục tồn tại
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MAX_REELS = 20
MIN_DELAY = 2.0
MAX_DELAY = 5.0
REQUEST_TIMEOUT = 15.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)
