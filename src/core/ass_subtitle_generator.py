"""Module biên dịch phụ đề sang định dạng Advanced SubStation Alpha (.ass).

Hỗ trợ:
- Trích xuất thông số thiết kế từ template CapCut (Font, Cỡ chữ, Màu, Viền, Bóng, Vị trí Y).
- Tạo hiệu ứng Karaoke nhảy chữ theo từng từ ({\\k<duration>}) khớp 100% với giọng nói.
- Render tối ưu cho khung hình dọc 1080x1920 của Reels/TikTok/Shorts.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def sec_to_ass_time(sec: float) -> str:
    """Chuyển đổi giây thành định dạng thời gian ASS: H:MM:SS.cs (centiseconds)."""
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def hex_to_ass_color(hex_color: str, default: str = "&H00FFFFFF") -> str:
    """Chuyển đổi mã màu hex (#RRGGBB hoặc #RGB) sang định dạng ASS (&HAABBGGRR)."""
    clean = hex_color.replace("#", "").strip()
    if len(clean) == 6:
        r = clean[0:2]
        g = clean[2:4]
        b = clean[4:6]
        return f"&H00{b.upper()}{g.upper()}{r.upper()}"
    elif len(clean) == 3:
        r = clean[0] * 2
        g = clean[1] * 2
        b = clean[2] * 2
        return f"&H00{b.upper()}{g.upper()}{r.upper()}"
    return default


def get_font_family_from_ttf(ttf_path: str) -> Optional[str]:
    """Trích xuất tên font family thực tế từ file TrueType (.ttf)."""
    import struct
    try:
        with open(ttf_path, "rb") as f:
            data = f.read()
        pos = 12
        num_tables = struct.unpack(">H", data[4:6])[0]
        for _ in range(num_tables):
            tag = data[pos:pos+4].decode("latin1", errors="ignore")
            offset, length = struct.unpack(">II", data[pos+8:pos+16])
            if tag == "name":
                num_records = struct.unpack(">H", data[offset+2:offset+4])[0]
                strings_offset = offset + struct.unpack(">H", data[offset+4:offset+6])[0]
                rec_pos = offset + 6
                for _ in range(num_records):
                    p_id, e_id, l_id, n_id, str_len, str_off = struct.unpack(">HHHHHH", data[rec_pos:rec_pos+12])
                    rec_pos += 12
                    if n_id in (1, 4):  # Family name or Full name
                        raw_str = data[strings_offset+str_off:strings_offset+str_off+str_len]
                        try:
                            if p_id == 3 or b"\x00" in raw_str:
                                name_str = raw_str.decode("utf-16-be").strip()
                            else:
                                name_str = raw_str.decode("utf-8", errors="ignore").strip() or raw_str.decode("latin1", errors="ignore").strip()
                        except Exception:
                            name_str = raw_str.decode("latin1", errors="ignore").strip()
                        if name_str and not any(ord(c) > 0x2E80 and ord(c) < 0x9FFF for c in name_str):
                            return name_str
            pos += 16
    except Exception:
        pass
    return None


def extract_style_from_capcut_draft(
    draft_content_path: str,
    canvas_w: int = 1080,
    canvas_h: int = 1920
) -> Dict[str, any]:
    """Đọc và trích xuất cấu hình style phụ đề từ file draft_content.json của CapCut template.
    
    Returns:
        Dict: Chứa font_name, font_file, font_size, primary_color, secondary_color, outline_color,
              outline_w, shadow_w, margin_v, alignment, uppercase.
    """
    default_style = {
        "font_name": "Arial",
        "font_file": None,
        "font_size": 65,
        "primary_color": "&H0018FD1C",     # Xanh Neon / Vàng sáng khi đọc tới
        "secondary_color": "&H00FFFFFF",   # Trắng chờ đọc
        "outline_color": "&H00000000",     # Viền đen dày dặn
        "outline_w": 4.5,
        "shadow_color": "&H90000000",
        "shadow_w": 2.5,
        "margin_v": 260,                   # Khoảng cách từ đáy
        "alignment": 2,                    # Bottom-center
        "uppercase": True
    }

    p = Path(draft_content_path)
    if not p.exists():
        return default_style

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        mats = data.get("materials", {})
        texts = mats.get("texts", [])
        tracks = data.get("tracks", [])

        # Tự động đọc kích thước Canvas từ template nếu có
        canvas = data.get("canvas_config", {})
        t_w = canvas.get("width")
        t_h = canvas.get("height")
        if t_w and t_h and int(t_w) > 0 and int(t_h) > 0:
            canvas_w = int(t_w)
            canvas_h = int(t_h)
        else:
            videos = mats.get("videos", [])
            if videos and videos[0].get("width") and videos[0].get("height"):
                canvas_w = int(videos[0]["width"])
                canvas_h = int(videos[0]["height"])

        default_style["canvas_w"] = canvas_w
        default_style["canvas_h"] = canvas_h

        if texts:
            t0 = texts[0]
            # 1. Tìm đường dẫn file TTF thực tế
            font_path = t0.get("font_path")
            if not font_path or not Path(font_path).exists():
                fonts_list = t0.get("fonts", [])
                if fonts_list and isinstance(fonts_list, list):
                    cand = fonts_list[0].get("path")
                    if cand and Path(cand).exists():
                        font_path = cand

            if not font_path or not Path(font_path).exists():
                try:
                    c_obj = json.loads(t0.get("content", "{}"))
                    styles = c_obj.get("styles", [])
                    if styles and "font" in styles[0]:
                        cand = styles[0]["font"].get("path")
                        if cand and Path(cand).exists():
                            font_path = cand
                except Exception:
                    pass

            if font_path and Path(font_path).exists():
                default_style["font_file"] = str(Path(font_path).resolve())
                real_name = get_font_family_from_ttf(font_path)
                if real_name:
                    default_style["font_name"] = real_name

            # Nếu không tìm thấy ttf, fallback sang font_title/font_name nếu khác "none"
            if default_style["font_name"] in ("Arial", "none"):
                font_title = t0.get("font_title") or t0.get("font_name")
                if font_title and font_title.lower() != "none":
                    default_style["font_name"] = font_title

            # 2. Màu chữ & Highlight Karaoke
            raw_color = t0.get("text_color")
            if raw_color and isinstance(raw_color, str) and raw_color.startswith("#"):
                ass_c = hex_to_ass_color(raw_color)
                if ass_c.upper() != "&H00FFFFFF":
                    default_style["primary_color"] = ass_c
                    default_style["secondary_color"] = "&H00FFFFFF"
                else:
                    default_style["secondary_color"] = "&H00FFFFFF"
                    default_style["primary_color"] = "&H0018FD1C"  # Neon lime green

            # 3. Viền chữ
            border_w = t0.get("border_width", 0)
            if border_w > 0:
                default_style["outline_w"] = max(3.5, float(border_w) * 0.5)
            border_c = t0.get("border_color")
            if border_c and isinstance(border_c, str) and border_c.startswith("#"):
                default_style["outline_color"] = hex_to_ass_color(border_c)

            # 4. Cỡ chữ (tự động co giãn theo tỉ lệ chiều cao khung hình canvas_h)
            size_val = t0.get("font_size") or 11
            scale_factor = (canvas_h / 1920.0)
            base_size = int(size_val * 6.0 * scale_factor)
            default_style["font_size"] = max(int(35 * scale_factor), min(int(90 * scale_factor), base_size))

        # 5. Tọa độ Y từ subtitle track segment clip
        text_tracks = [t for t in tracks if t.get("type") == "text" and t.get("segments")]
        if text_tracks:
            # Chọn track có nhiều segments nhất (đặc trưng của subtitle track)
            text_track = max(text_tracks, key=lambda t: len(t.get("segments", [])))
            seg0 = text_track["segments"][0]
            clip = seg0.get("clip", {})
            trans_y = clip.get("transform", {}).get("y", -0.74)
            pixel_from_bottom = int((1.0 + trans_y) * (canvas_h / 2))
            default_style["margin_v"] = max(int(canvas_h * 0.05), min(canvas_h - int(canvas_h * 0.05), pixel_from_bottom))

    except Exception:
        pass

    return default_style


def generate_ass_subtitles(
    chunks: List[Dict[str, any]],
    output_ass_path: str,
    style: Optional[Dict[str, any]] = None,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    karaoke_mode: bool = True
) -> str:
    """Biên dịch danh sách subtitle chunks thành file phụ đề chuẩn .ass.

    Args:
        chunks: Danh sách các đoạn phụ đề kèm danh sách từ (start, end, word).
        output_ass_path: Đường dẫn lưu file .ass.
        style: Cấu hình style (tự động lấy mặc định nếu None).
        canvas_w: Chiều rộng khung hình (tự động lấy theo template nếu có).
        canvas_h: Chiều cao khung hình (tự động lấy theo template nếu có).
        karaoke_mode: Có áp dụng hiệu ứng nhảy sáng từng từ hay không.

    Returns:
        str: Đường dẫn file .ass đã tạo.
    """
    st = style or {}
    # Ưu tiên lấy kích thước canvas đã trích xuất từ template
    if "canvas_w" in st and st["canvas_w"]:
        canvas_w = int(st["canvas_w"])
    if "canvas_h" in st and st["canvas_h"]:
        canvas_h = int(st["canvas_h"])

    font_name = st.get("font_name", "Arial")
    font_size = st.get("font_size", 65)
    primary_color = st.get("primary_color", "&H0000FFFF")     # Vàng sáng (active word)
    secondary_color = st.get("secondary_color", "&H00FFFFFF") # Trắng chờ (inactive)
    outline_color = st.get("outline_color", "&H00000000")     # Viền đen
    shadow_color = st.get("shadow_color", "&H80000000")
    outline_w = st.get("outline_w", 3.5)
    shadow_w = st.get("shadow_w", 2.0)
    margin_v = st.get("margin_v", int(canvas_h * 0.135))
    alignment = st.get("alignment", 2)

    header = f"""[Script Info]
Title: Auto Reels Subtitles
ScriptType: v4.00+
PlayResX: {canvas_w}
PlayResY: {canvas_h}
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ReelStyle,{font_name},{font_size},{primary_color},{secondary_color},{outline_color},{shadow_color},-1,0,0,0,100,100,0,0,1,{outline_w},{shadow_w},{alignment},50,50,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines = []

    for c in chunks:
        c_start = float(c["start"])
        c_end = float(c["end"])
        if c_end <= c_start:
            c_end = c_start + 0.5

        ass_start = sec_to_ass_time(c_start)
        ass_end = sec_to_ass_time(c_end)
        words = c.get("words", [])

        is_upper = st.get("uppercase", True)
        if karaoke_mode and words:
            # Tạo chuỗi thẻ karaoke {\k<centiseconds>}
            k_parts = []
            prev_time = c_start

            for i, w in enumerate(words):
                w_start = float(w["start"])
                w_end = float(w["end"])
                
                # Bù khoảng lặng trước từ nếu có
                if w_start > prev_time:
                    gap_cs = int(round((w_start - prev_time) * 100))
                    if gap_cs > 0:
                        k_parts.append(f"{{\\k{gap_cs}}}")

                dur_cs = max(10, int(round((w_end - w_start) * 100)))
                raw_w = w["word"].strip()
                clean_word = raw_w.upper() if is_upper else raw_w
                k_parts.append(f"{{\\k{dur_cs}}}{clean_word}")

                if i < len(words) - 1:
                    k_parts.append(" ")

                prev_time = w_end

            text_content = "".join(k_parts)
        else:
            # Hiển thị chữ tĩnh (không karaoke)
            raw_t = c.get("text", "").strip()
            text_content = raw_t.upper() if is_upper else raw_t

        line = f"Dialogue: 0,{ass_start},{ass_end},ReelStyle,,0,0,0,,{text_content}"
        dialogue_lines.append(line)

    full_ass = header + "\n".join(dialogue_lines) + "\n"

    out_p = Path(output_ass_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(full_ass)

    return str(out_p)
