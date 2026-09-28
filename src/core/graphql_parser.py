"""Module phân tích các gói tin GraphQL của Facebook để bóc tách caption và liên kết ngoài."""

import json
from urllib.parse import parse_qs, unquote, urlparse
from src.utils.url_helper import IGNORED_DOMAINS, extract_urls_from_text


def parse_graphql_payload(raw_text: str) -> dict:
    """Phân tích payload NDJSON từ Facebook GraphQL API.
    
    Trích xuất đệ quy:
    - Caption bài đăng/Reel từ `creation_story`
    - Link ngoài trong mô tả hoặc trong bình luận đính kèm (attachment) hoặc nội dung bình luận (body_renderer)
    
    Trả về:
        dict: {
            "caption": str,
            "target_urls": list[str],
            "found_in": str ("Trong mô tả" | "Trong bình luận" | "")
        }
    """
    if not raw_text or not isinstance(raw_text, str):
        return {"caption": "", "target_urls": [], "found_in": ""}

    caption = ""
    target_urls: list[str] = []
    found_in = ""

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except Exception:
            continue

        def walk(obj):
            nonlocal caption, found_in
            if isinstance(obj, dict):
                # 1. Trích xuất mô tả / caption video từ creation_story
                if "creation_story" in obj and isinstance(obj["creation_story"], dict):
                    msg = obj["creation_story"].get("message")
                    if msg and isinstance(msg, dict) and "text" in msg:
                        txt = str(msg["text"]).strip()
                        if len(txt) > len(caption):
                            caption = txt
                            urls = extract_urls_from_text(txt)
                            for u in urls:
                                if u not in target_urls:
                                    target_urls.append(u)
                                    if not found_in:
                                        found_in = "Trong mô tả"

                # 2. Trích xuất text trong bình luận (body_renderer)
                if "body_renderer" in obj and isinstance(obj["body_renderer"], dict):
                    c_txt = str(obj["body_renderer"].get("text", "")).strip()
                    if c_txt:
                        urls = extract_urls_from_text(c_txt)
                        for u in urls:
                            if u not in target_urls:
                                target_urls.append(u)
                                if not found_in:
                                    found_in = "Trong bình luận"

                # 3. Trích xuất liên kết đính kèm trong bình luận (attachment)
                if "attachment" in obj and isinstance(obj["attachment"], dict):
                    att = obj["attachment"]
                    for key in ["url", "target"]:
                        u_val = att.get(key)
                        if isinstance(u_val, dict):
                            u_val = u_val.get("url")
                        if u_val and isinstance(u_val, str):
                            raw_u = u_val.strip()
                            clean_u = ""
                            if "/l.php" in raw_u:
                                qs = parse_qs(urlparse(raw_u).query)
                                if "u" in qs and qs["u"]:
                                    clean_u = unquote(qs["u"][0]).split("?fbclid")[0].split("&fbclid")[0]
                            elif raw_u.startswith("http"):
                                clean_u = raw_u.split("?fbclid")[0].split("&fbclid")[0]

                            if clean_u:
                                parsed = urlparse(clean_u)
                                domain = parsed.netloc.lower()
                                if domain and not any(ign in domain for ign in IGNORED_DOMAINS):
                                    if not clean_u.endswith("…") and not clean_u.endswith("..."):
                                        if clean_u not in target_urls:
                                            target_urls.append(clean_u)
                                            if not found_in:
                                                found_in = "Trong bình luận"

                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(chunk)

    return {
        "caption": caption,
        "target_urls": target_urls,
        "found_in": found_in,
    }
