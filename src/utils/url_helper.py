import re
from pathlib import Path
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


def extract_channel_id(input_url_or_id: str) -> str:
    """Trích xuất ID hoặc định danh ngắn gọn của Fanpage/Profile từ URL Facebook."""
    text = str(input_url_or_id or "").strip()
    if not text:
        return "channel"

    # Nếu không phải URL hoặc là ID số nguyên thuần túy
    if not text.startswith("http") and "/" not in text:
        clean = re.sub(r'[\\/*?:"<>|\s]', '_', text)
        return clean or "channel"

    parsed = urlparse(text if text.startswith("http") else "https://" + text)
    path = parsed.path.strip("/")
    query = parse_qs(parsed.query)

    # 1. profile.php?id=61593384835679
    if "profile.php" in path.lower() and "id" in query and query["id"]:
        return query["id"][0]

    # 2. Trang dạng /p/Tên-Trang-ID/
    if path.lower().startswith("p/"):
        parts = path.split("/")
        if len(parts) >= 2 and parts[1]:
            clean = re.sub(r'[\\/*?:"<>|\s]', '_', parts[1])
            return clean

    # 3. Dạng username / page slug thông thường (vd: /nhathaofn hoặc /nhathaofn/reels)
    if path:
        first_segment = path.split("/")[0]
        if first_segment.lower() not in {"reel", "reels", "watch", "share", "stories"}:
            clean = re.sub(r'[\\/*?:"<>|\s]', '_', first_segment)
            return clean or "channel"

    # 4. Nếu là link reel đơn lẻ (vd: /reel/1098330379252955)
    if "reel" in path.lower():
        parts = [p for p in path.split("/") if p]
        for idx, part in enumerate(parts):
            if part.lower() in {"reel", "reels"} and idx + 1 < len(parts):
                clean_id = re.sub(r'[\\/*?:"<>|\s]', '_', parts[idx + 1])
                return f"reel_{clean_id}"

    return "reels_list"


def resolve_channel_project_dirs(
    project_root: Path | str,
    channel_url_or_id: str
) -> dict:
    """Xác định hoặc tạo mới thư mục dự án cho kênh theo định dạng {stt}_{channel_id},
    kèm 3 thư mục con: video/, caption/, final/.

    Quy tắc:
    - Nếu kênh đã có folder {stt}_{channel_id} từ trước thì dùng lại folder đó.
    - Nếu chưa có thì lấy số thứ tự tiếp theo: 1_{id}, 2_{id}, ..., n_{id}.
    """
    root = Path(project_root)
    root.mkdir(parents=True, exist_ok=True)

    channel_id = extract_channel_id(channel_url_or_id)

    # Quét tất cả các folder con trong root dạng {stt}_{name}
    existing_dirs = [d for d in root.iterdir() if d.is_dir()]
    pattern = re.compile(r"^(\d+)_(.+)$")

    found_dir = None
    max_stt = 0

    for d in existing_dirs:
        m = pattern.match(d.name)
        if m:
            stt = int(m.group(1))
            name = m.group(2)
            if stt > max_stt:
                max_stt = stt
            if name.lower() == channel_id.lower():
                found_dir = d

    if found_dir is not None:
        channel_dir = found_dir
    else:
        next_stt = max_stt + 1
        channel_dir = root / f"{next_stt}_{channel_id}"

    video_dir = channel_dir / "video"
    caption_dir = channel_dir / "caption"
    final_dir = channel_dir / "final"

    video_dir.mkdir(parents=True, exist_ok=True)
    caption_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    return {
        "channel_dir": channel_dir,
        "video_dir": video_dir,
        "caption_dir": caption_dir,
        "final_dir": final_dir,
        "channel_id": channel_id,
        "folder_name": channel_dir.name
    }


def extract_reel_id(url_or_id: str) -> str:
    """Trích xuất ID video Reel từ link Facebook hoặc ID thuần.
    
    Ví dụ:
    - https://www.facebook.com/reel/1098330379252955 -> '1098330379252955'
    - https://www.facebook.com/watch/?v=1098330379252955 -> '1098330379252955'
    - https://www.facebook.com/page/videos/1098330379252955/ -> '1098330379252955'
    - 1098330379252955 -> '1098330379252955'
    """
    clean_text = str(url_or_id or "").strip()
    if not clean_text:
        return ""

    # 1. Tìm qua tham số ?v=...
    m_v = re.search(r"[?&]v=(\d+)", clean_text)
    if m_v:
        return m_v.group(1)

    # 2. Tìm qua path /reel/12345 hoặc /videos/12345
    m_path = re.search(r"/(?:reel|reels|videos)/(\d+)", clean_text)
    if m_path:
        return m_path.group(1)

    # 3. Lấy số dài >= 5 ký tự bất kỳ trong path hoặc text
    parsed = urlparse(clean_text if clean_text.startswith("http") else "https://" + clean_text)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    for p in reversed(parts):
        if p.isdigit() and len(p) >= 5:
            return p

    # Fallback cho ID thuần không theo path chuẩn
    m_any = re.search(r"(\d{6,})", clean_text)
    if m_any:
        return m_any.group(1)

    return parts[-1] if parts else clean_text


def scan_existing_reels_folder(
    video_dir: Path | str | None,
    caption_dir: Path | str | None = None
) -> tuple[int, dict[str, dict]]:
    """Quét thư mục video/ và caption/ để:
    1. Xác định số thứ tự lớn nhất (max_stt) hiện có để đánh số tiếp theo.
    2. Lập danh sách các video đã tồn tại theo reel_id:
       {reel_id: {"stt": int, "path": Path, "name": str}}
    """
    v_dir = Path(video_dir) if video_dir else None
    c_dir = Path(caption_dir) if caption_dir else None

    max_stt = 0
    existing_reels: dict[str, dict] = {}

    pattern_stt_id = re.compile(r"^(\d+)_(.+)$")
    pattern_stt_only = re.compile(r"^(\d+)$")
    pattern_caption = re.compile(r"^caption_(\d+)\.txt$", re.IGNORECASE)

    # 1. Quét thư mục video
    if v_dir and v_dir.exists():
        for f in v_dir.iterdir():
            if not f.is_file() or f.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
                continue
            stem = f.stem
            stt = 0
            r_id = stem

            m = pattern_stt_id.match(stem)
            if m:
                stt = int(m.group(1))
                r_id = m.group(2)
                if stt > max_stt:
                    max_stt = stt
            else:
                m_only = pattern_stt_only.match(stem)
                if m_only:
                    stt = int(m_only.group(1))
                    if stt > max_stt:
                        max_stt = stt

            existing_reels[r_id] = {"stt": stt, "path": f, "name": f.name}

            # Bóc tách các ID số tiềm năng nếu stem có nhiều dấu gạch
            for part in stem.split("_"):
                if part.isdigit() and len(part) >= 6:
                    existing_reels[part] = {"stt": stt, "path": f, "name": f.name}

    # 2. Quét thư mục caption để đảm bảo max_stt đồng bộ
    if c_dir and c_dir.exists():
        for f in c_dir.iterdir():
            if not f.is_file():
                continue
            m = pattern_caption.match(f.name)
            if m:
                c_stt = int(m.group(1))
                if c_stt > max_stt:
                    max_stt = c_stt

    return max_stt, existing_reels


