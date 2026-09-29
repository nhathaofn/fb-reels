"""Module làm sạch hội thoại và xử lý phụ đề (Dialogue Cleaner).

Chuyên biệt cho video ngắn (Reels/TikTok):
- Loại bỏ âm thanh la hét chiến đấu, tiếng rên, tiếng hự, ho, aaaaaaa...
- Lọc bỏ từ cảm thán, tiếng thở, từ đệm vô nghĩa.
- Gom nhóm phụ đề thành các cụm từ ngắn (3 - 5 từ/câu) hiển thị nhanh và bắt mắt.
"""

import re
from typing import Dict, List, Optional

# Danh sách các từ cảm thán, tiếng rên, tiếng hự, tiếng động vật, âm thanh chiến đấu vô nghĩa
BANNED_ISOLATED_WORDS = {
    # Tiếng hét / rên / tiếng va chạm / chiến đấu
    "hự", "hừ", "hừm", "hây", "ặc", "á", "ớ", "ối", "oái", "úi", "hơ", "hở",
    "ugh", "argh", "grrr", "grr", "ooh", "ahh", "ah", "ha", "haha", "haizz",
    "ya", "yaa", "yaaa", "yea", "yeah", "hic", "huhu", "hu hu", "hihi", "hi hi",
    "omg", "wow", "oh", "woah", "shh", "suỵt", "chậc", "chẹp", "tsk"
}

# Regex phát hiện các ký tự lặp kéo dài đặc trưng của tiếng thét / rên / hú
REPEATED_CHAR_REGEX = re.compile(r"([a-zA-Zà-ỹÀ-Ỹ])\1{2,}", re.IGNORECASE)

# Regex phát hiện các chuỗi thét phổ biến
SCREAM_REGEX = re.compile(
    r"\b(a+|á+|ơ+|ô+|u+|o+|e+|i+|hự+|hừ+|hơ+|ặc+|hây+|ha+|ugh+|grr+|brr+|ah+|oh+|uh+)\b",
    re.IGNORECASE
)


def is_screaming_or_noise(word: str) -> bool:
    """Kiểm tra một từ đơn lẻ có phải là tiếng la hét, rên, hự hoặc tạp âm không."""
    clean = re.sub(r"[^\w\s]", "", word).strip().lower()
    if not clean:
        return True

    # 1. Trùng với danh sách từ cảm thán bị cấm
    if clean in BANNED_ISOLATED_WORDS:
        return True

    # 2. Chứa từ 3 ký tự liên tiếp giống nhau (ví dụ: aaaa, hựựự, ơơơ)
    if REPEATED_CHAR_REGEX.search(clean):
        return True

    # 3. Khớp regex tiếng thét ngắn
    if SCREAM_REGEX.fullmatch(clean):
        return True

    # 4. Chỉ chứa phụ âm vô nghĩa (ví dụ: hhh, sss, grr)
    vowels = set("aáàảãạăắằẳẵặâấầẩẫậeéèẻẽẹêếềểễệiíìỉĩịoóòỏõọôốồổỗộơớờởỡợuúùủũụưứừửữựyýỳỷỹỵ" + "aeiouyAEIOUY")
    if len(clean) >= 3 and not any(c in vowels for c in clean):
        return True

    return False


def clean_sentence_text(text: str) -> str:
    """Làm sạch câu văn: loại bỏ các từ hét/hự, dọn dẹp dấu câu rác."""
    if not text:
        return ""

    # Tách từ và lọc
    words = text.split()
    valid_words = []
    for w in words:
        raw_word = re.sub(r"[^\w\s]", "", w).strip()
        if raw_word and not is_screaming_or_noise(raw_word):
            valid_words.append(w)

    cleaned = " ".join(valid_words).strip()

    # Dọn dẹp dấu câu thừa thãi hoặc lặp vô nghĩa
    cleaned = re.sub(r"\.{2,}", "...", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Nếu chỉ còn dấu câu thì coi như rỗng
    if not re.search(r"[\w]", cleaned):
        return ""

    return cleaned


def clean_whisper_subtitles(
    segments: List[Dict[str, any]],
    min_word_duration: float = 0.05
) -> List[Dict[str, any]]:
    """Lọc sạch các đoạn phụ đề từ Whisper:
    - Loại bỏ các từ la hét, hự, aaaaa...
    - Đồng bộ lại start/end time của segment theo các từ còn lại.
    - Bỏ qua các segment không còn lời thoại hợp lệ.
    """
    if not segments:
        return []

    cleaned_segments = []

    for seg in segments:
        words = seg.get("words", [])
        if not words:
            # Fallback nếu không có word-level timestamps
            raw_text = seg.get("text", "")
            clean_txt = clean_sentence_text(raw_text)
            if clean_txt:
                s_copy = dict(seg)
                s_copy["text"] = clean_txt
                s_copy["start"] = float(seg["start"])
                s_copy["end"] = float(seg["end"])
                cleaned_segments.append(s_copy)
            continue

        # Lọc từng từ trong segment
        valid_words = []
        for w in words:
            w_text = w.get("word", "").strip()
            w_start = float(w.get("start", 0))
            w_end = float(w.get("end", 0))

            # Bỏ qua từ quá ngắn hoặc là tiếng hét
            if (w_end - w_start) < min_word_duration and len(w_text) <= 2:
                continue

            if not is_screaming_or_noise(w_text):
                valid_words.append({
                    "word": w_text,
                    "start": w_start,
                    "end": w_end
                })

        if not valid_words:
            continue

        new_start = valid_words[0]["start"]
        new_end = valid_words[-1]["end"]
        new_text = " ".join(w["word"] for w in valid_words).strip()

        if new_text and (new_end > new_start):
            cleaned_segments.append({
                "start": new_start,
                "end": new_end,
                "text": new_text,
                "words": valid_words
            })

    return cleaned_segments


def chunk_subtitles_for_reels(
    segments: List[Dict[str, any]],
    max_words_per_chunk: int = 4,
    max_duration_sec: float = 2.2,
    max_pause_gap: float = 0.45
) -> List[Dict[str, any]]:
    """Chia nhỏ các đoạn phụ đề thành các câu ngắn (3 - 5 từ/dòng).
    
    Tối ưu cho hiển thị dạng Reels/TikTok:
    - Chữ nhảy nhanh, bắt mắt theo từng cụm thoại.
    - Giữ trọn vẹn mốc thời gian start/end chính xác từng từ.
    - Tự động ngắt khi có khoảng lặng giữa các câu (> 0.45s) để không bao giờ bị lệch tiếng.
    """
    if not segments:
        return []

    all_words = []
    for s in segments:
        for w in s.get("words", []):
            all_words.append(w)

    if not all_words:
        # Nếu không có words, dùng segments nguyên bản
        return segments

    chunks = []
    current_chunk = []

    for w in all_words:
        # Kiểm tra khoảng ngắt giọng giữa 2 từ liên tiếp: nếu speaker ngừng nói > max_pause_gap -> ngắt cụm ngay
        if current_chunk:
            pause = w["start"] - current_chunk[-1]["end"]
            if pause >= max_pause_gap:
                c_start = current_chunk[0]["start"]
                c_end = current_chunk[-1]["end"]
                c_text = " ".join(cw["word"] for cw in current_chunk).strip()
                if c_text:
                    chunks.append({
                        "start": c_start,
                        "end": c_end,
                        "text": c_text,
                        "words": list(current_chunk)
                    })
                current_chunk = []

        current_chunk.append(w)

        chunk_duration = current_chunk[-1]["end"] - current_chunk[0]["start"]
        is_word_count_reached = len(current_chunk) >= max_words_per_chunk
        is_duration_reached = chunk_duration >= max_duration_sec

        # Nếu gặp dấu câu kết thúc câu (. , ! ?) hoặc đủ số từ/thời lượng
        last_word = current_chunk[-1]["word"]
        has_punctuation = bool(re.search(r"[,.!?]$", last_word))

        if is_word_count_reached or is_duration_reached or (has_punctuation and len(current_chunk) >= 2):
            c_start = current_chunk[0]["start"]
            c_end = current_chunk[-1]["end"]
            c_text = " ".join(cw["word"] for cw in current_chunk).strip()

            chunks.append({
                "start": c_start,
                "end": c_end,
                "text": c_text,
                "words": list(current_chunk)
            })
            current_chunk = []

    # Xử lý các từ còn lại cuối cùng
    if current_chunk:
        c_start = current_chunk[0]["start"]
        c_end = current_chunk[-1]["end"]
        c_text = " ".join(cw["word"] for cw in current_chunk).strip()
        chunks.append({
            "start": c_start,
            "end": c_end,
            "text": c_text,
            "words": list(current_chunk)
        })

    return chunks
