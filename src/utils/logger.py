import logging
import sys


def setup_logger(name: str = "reels_fb", level: int = logging.INFO) -> logging.Logger:
    """Khởi tạo logger chuẩn cho toàn bộ ứng dụng hỗ trợ tiếng Việt trên Windows."""
    l = logging.getLogger(name)
    if not l.handlers:
        l.setLevel(level)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        stream = sys.stdout or sys.stderr
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        handler = logging.StreamHandler(stream) if stream else logging.NullHandler()
        handler.setFormatter(formatter)
        l.addHandler(handler)

        try:
            from src.config import OUTPUT_DIR
            log_path = OUTPUT_DIR / "crawler.log"
            file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
            file_handler.setFormatter(formatter)
            l.addHandler(file_handler)
        except Exception:
            pass
    return l


logger = setup_logger()
