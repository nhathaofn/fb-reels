import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

def test_config_paths_and_defaults():
    assert isinstance(config.BASE_DIR, Path)
    assert isinstance(config.PROFILE_DIR, Path)
    assert isinstance(config.OUTPUT_DIR, Path)
    assert config.DEFAULT_MAX_REELS > 0
    assert 0 < config.MIN_DELAY <= config.MAX_DELAY
    assert "Mozilla" in config.USER_AGENT
