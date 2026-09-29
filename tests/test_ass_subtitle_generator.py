import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.core.ass_subtitle_generator import (
    sec_to_ass_time,
    hex_to_ass_color,
    extract_style_from_capcut_draft,
    generate_ass_subtitles
)


def test_sec_to_ass_time():
    assert sec_to_ass_time(0.0) == "0:00:00.00"
    assert sec_to_ass_time(1.25) == "0:00:01.25"
    assert sec_to_ass_time(65.5) == "0:01:05.50"
    assert sec_to_ass_time(3661.05) == "1:01:01.05"


def test_hex_to_ass_color():
    # ASS format là &HAABBGGRR
    assert hex_to_ass_color("#FFFFFF") == "&H00FFFFFF"
    assert hex_to_ass_color("#FFFF00") == "&H0000FFFF" # Vàng RGB -> BGR
    assert hex_to_ass_color("#FF0000") == "&H000000FF" # Đỏ RGB -> BGR


def test_extract_style_from_capcut_draft():
    draft_path = Path(r"C:\Users\PC\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\template-fb\draft_content.json")
    if draft_path.exists():
        st = extract_style_from_capcut_draft(str(draft_path))
        assert "font_name" in st
        assert "margin_v" in st
        assert st["margin_v"] > 0


def test_generate_ass_subtitles(tmp_path):
    chunks = [
        {
            "start": 1.0,
            "end": 3.0,
            "text": "Xin chào các bạn",
            "words": [
                {"word": "Xin", "start": 1.0, "end": 1.4},
                {"word": "chào", "start": 1.5, "end": 1.9},
                {"word": "các", "start": 2.0, "end": 2.4},
                {"word": "bạn", "start": 2.5, "end": 3.0}
            ]
        }
    ]

    out_file = tmp_path / "test_sub.ass"
    res = generate_ass_subtitles(chunks, str(out_file), karaoke_mode=True)
    assert Path(res).exists()

    content = Path(res).read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    assert "Dialogue: 0,0:00:01.00,0:00:03.00,ReelStyle" in content
    assert r"{\k40}XIN" in content
    assert r"{\k50}BẠN" in content
