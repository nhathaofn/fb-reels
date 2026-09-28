import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.cookies import parse_cookie_input

def test_parse_cookie_input_json():
    json_cookie = '[{"name": "c_user", "value": "100012345", "domain": ".facebook.com", "path": "/"}]'
    parsed = parse_cookie_input(json_cookie)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "c_user"
    assert parsed[0]["value"] == "100012345"

def test_parse_cookie_input_raw_string():
    raw_str = "c_user=100012345; xs=abcdef123; fr=0987xyz"
    parsed = parse_cookie_input(raw_str)
    assert len(parsed) == 3
    names = [c["name"] for c in parsed]
    assert "c_user" in names
    assert "xs" in names
    assert "fr" in names

def test_parse_cookie_input_empty():
    assert parse_cookie_input("") == []
    assert parse_cookie_input("   ") == []
