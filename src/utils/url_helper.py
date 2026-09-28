import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse, unquote

URL_PATTERN = (
    r'(?:'
    r'https?://[^\s<>"\'“”‘’)]+|'
    r'www\.[^\s<>"\'“”‘’)]+|'
    r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24}(?:/[^\s<>"\'“”‘’)]*)?'
    r')'
)
URL_REGEX = re.compile(URL_PATTERN, re.IGNORECASE)

IGNORED_DOMAINS = [
    "facebook.com",
    "fb.com",
    "fb.watch",
    "fb.me",
    "m.facebook.com",
    "l.facebook.com",
    "instagram.com",
    "threads.net",
    "meta.com",
    "whatsapp.com",
    "messenger.com"
]


def normalize_reels_url(input_url: str) -> str:
    """Chuẩn hóa mọi định dạng URL trang Facebook thành link tab Reels."""
    clean_url = input_url.strip()
    if not clean_url:
        return ""
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url

    parsed = urlparse(clean_url)
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    query = parse_qs(parsed.query)

    # 1. Dạng ID: profile.php?id=...
    if "profile.php" in path_lower and "id" in query:
        query["sk"] = ["reels_tab"]
        new_query = urlencode(query, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", new_query, ""))

    # 2. Dạng đã có /reels
    if path_lower.endswith("/reels"):
        return f"{parsed.scheme}://{parsed.netloc}{path}/"
    if "/reels/" in path_lower:
        return clean_url

    # 3. Dạng username thông thường (facebook.com/username)
    if path and not path_lower.endswith("/reels"):
        return f"{parsed.scheme}://{parsed.netloc}{path}/reels/"

    return clean_url


# Set of common + major gTLDs/ccTLDs for validating bare domains without path
COMMON_TLDS = {
    "com", "org", "net", "edu", "gov", "mil", "int",
    "vn", "us", "uk", "ca", "de", "jp", "fr", "au", "ru", "ch", "it", "nl", "se", "no", "es", "in", "cn", "br",
    "biz", "top", "xyz", "site", "online", "store", "club", "vip", "info", "tech", "pro", "link", "live",
    "io", "ai", "co", "me", "cc", "tv", "dev", "app", "mobi", "asia", "blog", "news", "story", "icu",
    "space", "click", "fun", "press", "host", "website", "cloud", "digital", "agency", "today", "life",
    "world", "global", "zone", "work", "group", "company", "center", "solutions", "media", "network"
}


def extract_urls_from_text(text: str) -> list[str]:
    """Tìm tất cả các link web hợp lệ trong văn bản, bỏ qua link nội bộ Facebook/Meta, từ viết tắt và từ bị kiểm duyệt."""
    if not text:
        return []
    matches = URL_REGEX.findall(text)
    external_urls = []
    for raw_u in matches:
        u = raw_u.rstrip(")]}>\"'”’….,:;!?")
        if not u:
            continue
        had_scheme = u.startswith("http://") or u.startswith("https://")
        had_www = u.startswith("www.")
        if not had_scheme:
            full_u = "https://" + u
        else:
            full_u = u

        try:
            parsed = urlparse(full_u)
            domain = parsed.netloc.lower()
            if ":" in domain:
                domain = domain.split(":")[0]

            # Bóc tách các nhãn domain
            parts = domain.split(".")
            if len(parts) < 2:
                continue

            # Kiểm tra: loại bỏ các từ bị kiểm duyệt / viết tắt có từ 2 nhãn 1 ký tự trở lên (k.i.c.ked, c.r.a.c.ked, v.v., e.g., a.m.)
            single_letter_labels = [p for p in parts if len(p) == 1]
            if len(single_letter_labels) >= 2:
                continue

            # Nhãn TLD (đuôi tên miền)
            tld = parts[-1]
            if not tld.isalpha():
                continue

            # Nếu không có scheme và không có www:
            if not had_scheme and not had_www:
                has_path = bool(parsed.path and parsed.path != "/")
                # Nếu không có path (/...), TLD phải nằm trong COMMON_TLDS và nhãn trước TLD phải >= 2 ký tự
                if not has_path:
                    if tld not in COMMON_TLDS:
                        continue
                    if len(parts[-2]) < 2:
                        continue

            # Giải mã link redirect của Facebook (l.facebook.com/l.php?u=...) nếu có
            if "facebook.com" in domain and "/l.php" in parsed.path:
                qs = parse_qs(parsed.query)
                if "u" in qs and qs["u"]:
                    full_u = unquote(qs["u"][0])
                    parsed = urlparse(full_u)
                    domain = parsed.netloc.lower()
                    if ":" in domain:
                        domain = domain.split(":")[0]

            # Bỏ tham số tracking fbclid
            if "?fbclid" in full_u or "&fbclid" in full_u:
                full_u = full_u.split("?fbclid")[0].split("&fbclid")[0]

            if domain and not any(ign in domain for ign in IGNORED_DOMAINS):
                if full_u not in external_urls and not full_u.endswith("…") and not full_u.endswith("..."):
                    external_urls.append(full_u)
        except Exception:
            continue

    return external_urls

