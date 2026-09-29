import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.core.dialogue_cleaner import (
    is_screaming_or_noise,
    clean_sentence_text,
    clean_whisper_subtitles,
    chunk_subtitles_for_reels
)


def test_is_screaming_or_noise():
    # Tiếng thét / rên / hự / aaaaa
    assert is_screaming_or_noise("AAAAAAAAHHHHH!") is True
    assert is_screaming_or_noise("aaaaa") is True
    assert is_screaming_or_noise("hự") is True
    assert is_screaming_or_noise("HỰỰỰ") is True
    assert is_screaming_or_noise("Ughhh") is True
    assert is_screaming_or_noise("á") is True
    assert is_screaming_or_noise("hây") is True
    assert is_screaming_or_noise("grrr") is True
    assert is_screaming_or_noise("...") is True

    # Lời thoại người bình thường
    assert is_screaming_or_noise("chào") is False
    assert is_screaming_or_noise("bạn") is False
    assert is_screaming_or_noise("Free") is False
    assert is_screaming_or_noise("Fire!") is False
    assert is_screaming_or_noise("chiến") is False
    assert is_screaming_or_noise("đấu") is False


def test_clean_sentence_text():
    raw1 = "AAAAAAAAHHHHH! Hãy dừng lại ngay!"
    assert clean_sentence_text(raw1) == "Hãy dừng lại ngay!"

    raw2 = "Hự... đau quá... á á á..."
    assert clean_sentence_text(raw2) == "đau quá..."

    raw3 = "AAAAAAAAHHHHH!"
    assert clean_sentence_text(raw3) == ""


def test_clean_whisper_subtitles():
    sample_segments = [
        {
            "start": 0.0,
            "end": 1.74,
            "text": "AAAAAAAAHHHHH!",
            "words": [
                {"word": "AAAAAAAAHHHHH!", "start": 0.0, "end": 1.74}
            ]
        },
        {
            "start": 2.0,
            "end": 4.5,
            "text": "Hự! Đừng làm vậy!",
            "words": [
                {"word": "Hự!", "start": 2.0, "end": 2.4},
                {"word": "Đừng", "start": 2.5, "end": 2.9},
                {"word": "làm", "start": 3.0, "end": 3.4},
                {"word": "vậy!", "start": 3.5, "end": 4.5}
            ]
        },
        {
            "start": 5.0,
            "end": 7.0,
            "text": "Free Fire chiến nào!",
            "words": [
                {"word": "Free", "start": 5.0, "end": 5.4},
                {"word": "Fire", "start": 5.5, "end": 6.0},
                {"word": "chiến", "start": 6.1, "end": 6.5},
                {"word": "nào!", "start": 6.6, "end": 7.0}
            ]
        }
    ]

    cleaned = clean_whisper_subtitles(sample_segments)
    # Đoạn 1 (AAAAAAAAHHHHH!) bị loại bỏ hoàn toàn
    assert len(cleaned) == 2

    # Đoạn 2 loại bỏ "Hự!", chỉ còn "Đừng làm vậy!", start dịch từ 2.5
    assert cleaned[0]["text"] == "Đừng làm vậy!"
    assert cleaned[0]["start"] == 2.5
    assert cleaned[0]["end"] == 4.5

    # Đoạn 3 giữ nguyên
    assert cleaned[1]["text"] == "Free Fire chiến nào!"


def test_chunk_subtitles_for_reels():
    long_segment = [
        {
            "start": 0.0,
            "end": 10.0,
            "text": "Hôm nay tôi sẽ hướng dẫn cho các bạn một mẹo làm video cực hay",
            "words": [
                {"word": "Hôm", "start": 0.0, "end": 0.3},
                {"word": "nay", "start": 0.3, "end": 0.6},
                {"word": "tôi", "start": 0.6, "end": 0.9},
                {"word": "sẽ", "start": 0.9, "end": 1.2},
                {"word": "hướng", "start": 1.2, "end": 1.5},
                {"word": "dẫn", "start": 1.5, "end": 1.8},
                {"word": "cho", "start": 1.8, "end": 2.1},
                {"word": "các", "start": 2.1, "end": 2.4},
                {"word": "bạn", "start": 2.4, "end": 2.7},
                {"word": "một", "start": 2.7, "end": 3.0},
                {"word": "mẹo", "start": 3.0, "end": 3.3},
                {"word": "làm", "start": 3.3, "end": 3.6},
                {"word": "video", "start": 3.6, "end": 4.0},
                {"word": "cực", "start": 4.0, "end": 4.3},
                {"word": "hay", "start": 4.3, "end": 4.7}
            ]
        }
    ]

    chunks = chunk_subtitles_for_reels(long_segment, max_words_per_chunk=4)
    assert len(chunks) == 4
    assert len(chunks[0]["words"]) == 4
    assert chunks[0]["text"] == "Hôm nay tôi sẽ"
    assert chunks[0]["start"] == 0.0
    assert chunks[0]["end"] == 1.2
