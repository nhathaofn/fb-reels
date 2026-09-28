import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config

def test_config_paths_and_defaults():
    assert isinstance(config.BASE_DIR, Path)
    assert isinstance(config.SRC_DIR, Path)
    assert isinstance(config.PROFILE_DIR, Path)
    assert isinstance(config.OUTPUT_DIR, Path)
    assert isinstance(config.EXCEL_DIR, Path)
    assert isinstance(config.VIDEOS_DIR, Path)
    assert isinstance(config.CAPTIONS_DIR, Path)
    assert config.EXCEL_DIR.exists()
    assert config.VIDEOS_DIR.exists()
    assert config.CAPTIONS_DIR.exists()
    assert config.DEFAULT_MAX_REELS > 0
    assert 0 < config.MIN_DELAY <= config.MAX_DELAY
    assert "Mozilla" in config.USER_AGENT
    assert config.BROWSER_CHANNEL in ["msedge", "chrome", "chromium"]
    assert config.BROWSER_LOCALE is not None
    assert "Accept-Language" in config.EXTRA_HTTP_HEADERS
