import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.graphql_parser import parse_graphql_payload


def test_parse_empty_or_invalid():
    res = parse_graphql_payload("")
    assert res == {"caption": "", "target_urls": [], "found_in": ""}

    res2 = parse_graphql_payload("invalid json string {} {{")
    assert res2 == {"caption": "", "target_urls": [], "found_in": ""}


def test_parse_creation_story_description():
    payload = json.dumps({
        "data": {
            "video": {
                "creation_story": {
                    "message": {
                        "text": "Great story here: https://novelhub.biz/chapter-1 reading now!"
                    }
                }
            }
        }
    })
    res = parse_graphql_payload(payload)
    assert "Great story here" in res["caption"]
    assert "https://novelhub.biz/chapter-1" in res["target_urls"]
    assert res["found_in"] == "Trong mô tả"


def test_parse_comment_attachment():
    # Simulated Facebook NDJSON chunk
    chunk1 = json.dumps({"label": "feedback", "path": ["video", "feedback"]})
    chunk2 = json.dumps({
        "data": {
            "feedback": {
                "comments": {
                    "edges": [
                        {
                            "node": {
                                "body_renderer": {"text": "Part 2 is ready!"},
                                "attachment": {
                                    "target": {
                                        "url": "https://l.facebook.com/l.php?u=https%3A%2F%2Fstoryvault.cafex.biz%2Fpart-2%3Ffbclid%3D123"
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }
    })
    ndjson_payload = f"{chunk1}\n{chunk2}"
    res = parse_graphql_payload(ndjson_payload)
    assert "https://storyvault.cafex.biz/part-2" in res["target_urls"]
    assert res["found_in"] == "Trong bình luận"


def test_parse_comment_text_url():
    payload = json.dumps({
        "data": {
            "feedback": {
                "comments": {
                    "edges": [
                        {
                            "node": {
                                "body_renderer": {
                                    "text": "Đọc tiếp tại https://mystory.top/full-story"
                                }
                            }
                        }
                    ]
                }
            }
        }
    })
    res = parse_graphql_payload(payload)
    assert "https://mystory.top/full-story" in res["target_urls"]
    assert res["found_in"] == "Trong bình luận"


def test_ignore_internal_meta_urls_in_comments():
    payload = json.dumps({
        "data": {
            "feedback": {
                "comments": {
                    "edges": [
                        {
                            "node": {
                                "body_renderer": {
                                    "text": "Check profile https://facebook.com/reel/999 or https://instagram.com/p/123"
                                }
                            }
                        }
                    ]
                }
            }
        }
    })
    res = parse_graphql_payload(payload)
    assert res["target_urls"] == []
    assert res["found_in"] == ""
