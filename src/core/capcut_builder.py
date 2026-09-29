"""Module tự động hóa sao chép thuộc tính và cấu hình dự án CapCut (Auto CapCut Builder).

Hỗ trợ sao chép toàn bộ thuộc tính từ template CapCut:
- Tỉ lệ khung hình (Canvas, Aspect Ratio)
- Video setup: scale, transform x/y, rotation, flip, crop
- Hiệu ứng hình ảnh (Video Effects & Filters)
- Hiệu ứng chuyển cảnh (Transitions)
- Chữ & Phụ đề (Text, Subtitles, Fonts, Styles, Animations)
- Trích xuất giọng nói và phụ đề chuẩn bằng faster-whisper, giữ nguyên 100% style của template
- Âm thanh (Audio effects, volume, fades)
- Tự động căn chỉnh timeline & duration tương thích với video mới
- Đăng ký vào root_meta_info.json để CapCut nhận diện ngay lập tức.
"""

import copy
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2

from src.core.whisper_manager import get_whisper_manager, setup_cuda_environment
from src.core.ass_subtitle_generator import (
    extract_style_from_capcut_draft,
    generate_ass_subtitles
)
from src.core.dialogue_cleaner import (
    clean_whisper_subtitles,
    chunk_subtitles_for_reels
)
from src.core.video_renderer import (
    render_reels_video,
    find_ffmpeg_exe,
    has_nvenc_support
)
from src.utils.logger import logger

# Đường dẫn mặc định của CapCut PC trên Windows
DEFAULT_CAPCUT_DRAFT_DIRS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft",
    Path(os.environ.get("LOCALAPPDATA", "")) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft",
    Path("D:/CapCut/User Data/Projects/com.lveditor.draft"),
    Path("D:/JianyingPro/User Data/Projects/com.lveditor.draft"),
    Path("E:/CapCut/User Data/Projects/com.lveditor.draft"),
    Path(os.environ.get("USERPROFILE", "")) / "Documents" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft",
]

SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def find_capcut_draft_dir() -> Optional[Path]:
    """Tìm thư mục chứa các dự án CapCut Draft trên hệ thống."""
    for p in DEFAULT_CAPCUT_DRAFT_DIRS:
        if p.exists() and p.is_dir():
            return p
    return None


def find_subtitle_text_track(tracks: list[dict]) -> tuple[Optional[dict], int]:
    """Tìm track text có khả năng cao nhất là track phụ đề thoại.
    
    Quy tắc phân loại thông minh:
    1. Ưu tiên track text có nhiều segments nhất (phụ đề thường có từ vài đến hàng chục câu).
    2. Nếu số segment bằng nhau, ưu tiên track có tọa độ Y ở nửa dưới màn hình (transform.y <= 0).
    """
    text_tracks = [(idx, t) for idx, t in enumerate(tracks) if t.get("type") == "text" and t.get("segments")]
    if not text_tracks:
        return None, -1

    def score_track(item):
        idx, t = item
        segs = t.get("segments", [])
        seg_count = len(segs)
        y_bonus = 0
        if segs:
            seg0 = segs[0]
            clip = seg0.get("clip", {})
            y = clip.get("transform", {}).get("y", 0.0)
            if y < 0:
                y_bonus = 10
        return seg_count * 2 + y_bonus

    best_idx, best_track = max(text_tracks, key=score_track)
    return best_track, best_idx


def find_main_video_material(draft_content: dict) -> Optional[dict]:
    """Tìm video material chính trong dự án để thay thế.
    
    Quy tắc:
    1. Quét track video đầu tiên có duration dài nhất (main video track).
    2. Nếu không tìm thấy qua track, lấy video có duration lớn nhất trong materials['videos'].
    """
    mats = draft_content.get("materials", {})
    videos = mats.get("videos", [])
    if not videos:
        return None

    video_tracks = [t for t in draft_content.get("tracks", []) if t.get("type") == "video"]
    if video_tracks:
        longest_mat_id = None
        max_dur = -1
        for track in video_tracks:
            for seg in track.get("segments", []):
                tr = seg.get("target_timerange", {})
                dur = tr.get("duration", 0)
                if dur > max_dur:
                    max_dur = dur
                    longest_mat_id = seg.get("material_id")
        if longest_mat_id:
            for v in videos:
                if v.get("id") == longest_mat_id:
                    return v

    return max(videos, key=lambda v: v.get("duration", 0))


def get_project_canvas_dimensions(draft_content: dict, default_w: int = 1080, default_h: int = 1920) -> tuple[int, int]:
    """Lấy kích thước khung hình Canvas thực tế từ template (hoặc video)."""
    canvas = draft_content.get("canvas_config", {})
    w = canvas.get("width")
    h = canvas.get("height")
    if w and h and int(w) > 0 and int(h) > 0:
        return int(w), int(h)

    videos = draft_content.get("materials", {}).get("videos", [])
    if videos:
        vw = videos[0].get("width")
        vh = videos[0].get("height")
        if vw and vh and int(vw) > 0 and int(vh) > 0:
            return int(vw), int(vh)

    return default_w, default_h


def get_capcut_templates(
    draft_dir: Optional[Path] = None,
    filter_template_keyword: bool = True
) -> List[Dict[str, str]]:
    """Liệt kê danh sách các dự án CapCut có sẵn làm template.
    
    Yêu cầu: CHỈ để đúng những project CapCut trong tên CÓ từ 'template' (không phân biệt hoa thường)
    thì mới được hiển thị. Không hiển thị các dự án bình thường khác.
    """
    base_dir = draft_dir or find_capcut_draft_dir()
    if not base_dir or not base_dir.exists():
        return []

    raw_templates = []
    root_meta_path = base_dir / "root_meta_info.json"

    # Ưu tiên đọc từ root_meta_info.json
    if root_meta_path.exists():
        try:
            with open(root_meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("all_draft_store", []):
                name = item.get("draft_name")
                proj_path = Path(item.get("draft_fold_path", base_dir / name))
                if name and proj_path.exists():
                    raw_templates.append({
                        "name": name,
                        "path": str(proj_path),
                        "id": item.get("draft_id", ""),
                        "duration_sec": item.get("tm_duration", 0) / 1_000_000
                    })
        except Exception as e:
            logger.warning(f"Lỗi khi đọc root_meta_info.json: {e}")

    # Fallback duyệt thư mục con nếu root_meta_info rỗng
    if not raw_templates:
        for item in base_dir.iterdir():
            if item.is_dir() and (item / "draft_content.json").exists():
                raw_templates.append({
                    "name": item.name,
                    "path": str(item),
                    "id": "",
                    "duration_sec": 0
                })

    # Khử trùng lặp tên dự án
    seen = set()
    unique_templates = []
    for t in raw_templates:
        if t["name"] not in seen:
            seen.add(t["name"])
            unique_templates.append(t)

    def template_priority(t: dict) -> tuple[int, str]:
        name = t.get("name", "").lower()
        if "template" in name and any(k in name for k in ["fb", "reel", "tiktok", "short", "doc"]):
            return (0, name)
        if name == "template-fb":
            return (1, name)
        if name == "template":
            return (2, name)
        if "template" in name:
            return (3, name)
        return (4, name)

    # Lọc CHẶT CHẼ: Chỉ lấy các dự án có chứa từ khóa 'template' trong tên
    if filter_template_keyword:
        matched = [t for t in unique_templates if "template" in t.get("name", "").lower()]
        return sorted(matched, key=template_priority)

    return sorted(unique_templates, key=template_priority)


def get_video_metadata(video_path: str) -> Dict[str, any]:
    """Trích xuất metadata (width, height, fps, duration) của video bằng OpenCV."""
    v_path = Path(video_path)
    if not v_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

    cap = cv2.VideoCapture(str(v_path))
    if not cap.isOpened():
        raise ValueError(f"Không thể mở file video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    duration_sec = frame_count / fps if fps > 0 else 0
    duration_us = int(duration_sec * 1_000_000)

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": int(frame_count),
        "duration_sec": duration_sec,
        "duration_us": duration_us,
        "aspect_ratio": f"{width}:{height}"
    }


def setup_cuda_environment():
    """Tự động thêm đường dẫn thư viện CUDA DLL (cublas, cudnn) vào search path của Windows."""
    import site
    try:
        site_dirs = site.getsitepackages() if hasattr(site, "getsitepackages") else []
        try:
            import site as user_site
            if hasattr(user_site, "getusersitepackages"):
                site_dirs.append(user_site.getusersitepackages())
        except Exception:
            pass

        for s_dir in site_dirs:
            nv_dir = Path(s_dir) / "nvidia"
            if nv_dir.exists():
                for sub in nv_dir.iterdir():
                    bin_dir = sub / "bin"
                    if bin_dir.exists():
                        try:
                            os.add_dll_directory(str(bin_dir))
                        except Exception:
                            pass
                        cur_path = os.environ.get("PATH", "")
                        if str(bin_dir) not in cur_path:
                            os.environ["PATH"] = str(bin_dir) + os.pathsep + cur_path
    except Exception as e:
        logger.debug(f"Không thể cấu hình tự động CUDA DLL: {e}")


def transcribe_video_subtitles(
    video_path: str,
    model_size: str = "large-v3-turbo",
    language: Optional[str] = None,
    filter_screams: bool = True,
    chunk_for_reels: bool = True,
    max_words_per_chunk: int = 4
) -> List[Dict[str, any]]:
    """Trích xuất phụ đề từ âm thanh của video bằng faster-whisper với model tối ưu GPU (large-v3-turbo).

    Sử dụng WhisperModelManager để tái sử dụng model đã nạp sẵn trên GPU (CUDA NVIDIA),
    tránh việc nạp/tắt nhiều lần gây gián đoạn và hao phí tài nguyên.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.warning("Thư viện 'faster-whisper' chưa được cài đặt. Bỏ qua trích xuất phụ đề giọng nói.")
        return []

    manager = get_whisper_manager()
    model = manager.get_model(model_name=model_size)
    if not model:
        logger.error(f"Không thể lấy model Whisper '{model_size}'!")
        return []

    info_dict = manager.get_loaded_info()
    device_desc = f"{info_dict.get('device', 'unknown').upper()} ({info_dict.get('compute_type', '')})"
    lang_desc = language if language else "Tự động theo Voice"
    logger.info(f"🎤 Bắt đầu nhận diện giọng nói cho {Path(video_path).name} bằng faster-whisper [{device_desc}, model={model_size}, ngôn ngữ={lang_desc}]...")
    try:

        # Prompt tiếng Anh chuẩn, không thiết lập fallback tiếng Việt, không cố định ngôn ngữ
        prompt = "Clear speech and dialogue, accurate transcription with natural punctuation."

        segments, info = model.transcribe(
            video_path,
            language=language,
            initial_prompt=prompt,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300, threshold=0.35),
            beam_size=5,
            word_timestamps=True,
            condition_on_previous_text=False
        )

        raw_subtitles = []
        for s in segments:
            if not s.words:
                continue
            words_clean = [w for w in s.words if w.word.strip()]
            if not words_clean:
                continue

            p_start = float(words_clean[0].start)
            p_end = float(words_clean[-1].end)
            text = s.text.strip()

            raw_subtitles.append({
                "start": p_start,
                "end": p_end,
                "text": text,
                "words": [
                    {"word": w.word.strip(), "start": float(w.start), "end": float(w.end)}
                    for w in words_clean
                ]
            })

        logger.info(f"Đã nhận diện thô {len(raw_subtitles)} đoạn phụ đề (Ngôn ngữ: {info.language}).")

        # 1. Lọc bỏ các từ la hét chiến đấu, rên, hự, aaaaa...
        if filter_screams:
            subtitles = clean_whisper_subtitles(raw_subtitles)
            logger.info(f"Sau khi lọc âm thanh la hét/hự/ho: còn {len(subtitles)} đoạn lời thoại sạch.")
        else:
            subtitles = raw_subtitles

        # 2. Chia nhỏ thành cụm từ chuẩn Reels (3 - 5 từ/dòng)
        if chunk_for_reels and subtitles:
            subtitles = chunk_subtitles_for_reels(subtitles, max_words_per_chunk=max_words_per_chunk)
            logger.info(f"Đã chia thành {len(subtitles)} cụm phụ đề ngắn chuẩn Reels/TikTok.")

        return subtitles
    except Exception as e:
        logger.error(f"Lỗi khi chạy faster-whisper: {e}")
        return []


def inject_whisper_subtitles(
    draft_content: dict,
    whisper_segments: List[Dict[str, any]]
) -> bool:
    """Tạo mới toàn bộ track phụ đề từ kết quả whisper, giữ nguyên 100% font/style/animation/vị trí của template.
    
    Hỗ trợ đa dạng và thông minh:
    - Tự động nhận diện đúng track phụ đề (không xóa nhầm track Tiêu đề/Header/Watermark).
    - Hỗ trợ cả 2 kiến trúc CapCut: Mẫu chữ nghệ thuật ('text_templates') VÀ Chữ thường/Auto Captions ('texts' trực tiếp).
    - Tự động dọn dẹp track phụ đề nếu video không có lời thoại (tránh rác chữ template cũ).
    """
    mats = draft_content.get("materials", {})
    tracks = draft_content.get("tracks", [])

    text_track, _ = find_subtitle_text_track(tracks)
    if not text_track or not text_track.get("segments"):
        return False

    # Nếu không có đoạn thoại nào, xóa sạch subtitle cũ của template để video mới không bị dính chữ cũ
    if not whisper_segments:
        text_track["segments"] = []
        return True

    # Lấy mẫu master prototype từ segment đầu tiên của track phụ đề
    master_seg = copy.deepcopy(text_track["segments"][0])
    master_mat_id = master_seg["material_id"]

    # Kiểm tra xem segment đang dùng 'text_templates' hay trỏ trực tiếp vào 'texts'
    master_tmpl = copy.deepcopy(
        next((item for item in mats.get("text_templates", []) if item.get("id") == master_mat_id), None)
    )
    is_template_mode = master_tmpl is not None

    if is_template_mode:
        master_text_id = master_tmpl["text_info_resources"][0]["text_material_id"]
        master_text = copy.deepcopy(
            next((item for item in mats.get("texts", []) if item.get("id") == master_text_id), None)
        )
    else:
        # Cấu trúc Chữ thông thường hoặc Auto Captions của CapCut
        master_text = copy.deepcopy(
            next((item for item in mats.get("texts", []) if item.get("id") == master_mat_id), None)
        )

    if not master_text:
        return False

    master_anim_id = next(
        (r for r in master_seg.get("extra_material_refs", [])
         if any(a.get("id") == r for a in mats.get("material_animations", []))),
        None
    )
    master_anim = copy.deepcopy(
        next((item for item in mats.get("material_animations", []) if item.get("id") == master_anim_id), None)
    ) if master_anim_id else None

    master_effect_id = next(
        (r for r in master_seg.get("extra_material_refs", [])
         if any(e.get("id") == r for e in mats.get("effects", []))),
        None
    )
    master_effect = copy.deepcopy(
        next((item for item in mats.get("effects", []) if item.get("id") == master_effect_id), None)
    ) if master_effect_id else None

    # Dọn dẹp các text templates hoặc texts cũ của subtitle track
    old_mat_ids = {s["material_id"] for s in text_track["segments"]}
    if is_template_mode:
        mats["text_templates"] = [t for t in mats.get("text_templates", []) if t.get("id") not in old_mat_ids]
    else:
        mats["texts"] = [t for t in mats.get("texts", []) if t.get("id") not in old_mat_ids]

    new_segments = []
    new_texts = []
    new_tmpls = []
    new_anims = []
    new_effects = []

    for idx, sub in enumerate(whisper_segments):
        raw_text = sub["text"]
        start_sec = sub["start"]
        end_sec = sub["end"]
        dur_sec = max(end_sec - start_sec, 0.4)

        start_us = int(start_sec * 1_000_000)
        dur_us = int(dur_sec * 1_000_000)

        seg_id = str(uuid.uuid4()).upper()
        text_id = str(uuid.uuid4()).upper()
        tmpl_id = str(uuid.uuid4()).upper() if is_template_mode else ""
        anim_id = str(uuid.uuid4()).upper() if master_anim else ""
        effect_id = str(uuid.uuid4()).upper() if master_effect else ""

        # Xây dựng mảng words chi tiết cho CapCut text animation
        words_data = sub.get("words", [])
        word_texts = []
        word_starts = []
        word_ends = []

        if words_data:
            for i, w in enumerate(words_data):
                rel_s = max(0, int((w["start"] - start_sec) * 1000))
                rel_e = min(int(dur_sec * 1000), int((w["end"] - start_sec) * 1000))
                if rel_e <= rel_s:
                    rel_e = rel_s + 150
                word_texts.append(w["word"])
                word_starts.append(rel_s)
                word_ends.append(rel_e)
                if i < len(words_data) - 1:
                    word_texts.append(" ")
                    word_starts.append(rel_e)
                    word_ends.append(rel_e)
        else:
            word_texts = [raw_text]
            word_starts = [0]
            word_ends = [int(dur_sec * 1000)]

        capcut_words = {
            "start_time": word_starts,
            "end_time": word_ends,
            "text": word_texts
        }

        # 1. Text material (sao chép font, style, màu, viền, hiệu ứng chữ)
        cur_text = copy.deepcopy(master_text)
        cur_text["id"] = text_id
        cur_text["recognize_text"] = raw_text
        cur_text["words"] = capcut_words
        try:
            content_obj = json.loads(cur_text["content"])
            content_obj["text"] = raw_text
            if "styles" in content_obj and len(content_obj["styles"]) > 0:
                content_obj["styles"][0]["range"] = [0, len(raw_text)]
            cur_text["content"] = json.dumps(content_obj, ensure_ascii=False)
        except Exception:
            pass
        new_texts.append(cur_text)

        extra_refs = []
        if effect_id:
            extra_refs.append(effect_id)
        if anim_id:
            extra_refs.append(anim_id)

        # 2. Text template (nếu dùng chế độ template nghệ thuật)
        if is_template_mode:
            cur_tmpl = copy.deepcopy(master_tmpl)
            cur_tmpl["id"] = tmpl_id
            res0 = cur_tmpl["text_info_resources"][0]
            res0["id"] = str(uuid.uuid4()).upper()
            res0["text_material_id"] = text_id
            res0["attach_info"]["duration"] = dur_us
            res0["attach_info"]["start_time"] = 0
            res0["extra_material_refs"] = extra_refs
            new_tmpls.append(cur_tmpl)

        # 3. Animation
        if master_anim:
            cur_anim = copy.deepcopy(master_anim)
            cur_anim["id"] = anim_id
            for sub_a in cur_anim.get("animations", []):
                sub_a["duration"] = dur_us
            new_anims.append(cur_anim)

        # 4. Effect
        if master_effect:
            cur_eff = copy.deepcopy(master_effect)
            cur_eff["id"] = effect_id
            new_effects.append(cur_eff)

        # 5. Segment trong Text Track (sao chép vị trí y, scale, transform)
        cur_seg = copy.deepcopy(master_seg)
        cur_seg["id"] = seg_id
        cur_seg["material_id"] = tmpl_id if is_template_mode else text_id
        cur_seg["target_timerange"] = {
            "start": start_us,
            "duration": dur_us
        }
        cur_seg["extra_material_refs"] = extra_refs
        new_segments.append(cur_seg)

    # Đưa vào cấu trúc dự án
    if is_template_mode:
        mats["texts"] = new_texts
        mats["text_templates"].extend(new_tmpls)
    else:
        mats["texts"].extend(new_texts)

    if master_anim:
        mats["material_animations"].extend(new_anims)
    if master_effect:
        mats["effects"].extend(new_effects)

    text_track["segments"] = new_segments
    return True


def clone_and_apply_template(
    template_name: str,
    new_project_name: str,
    new_video_path: str,
    draft_dir: Optional[Path] = None,
    scale_mode: str = "scale_all",
    use_whisper_subtitles: bool = True,
    whisper_model: str = "large-v3-turbo",
    whisper_language: Optional[str] = None,
    precomputed_subtitles: Optional[List[Dict[str, any]]] = None
) -> Tuple[Path, str]:
    """Nhân bản cấu hình dự án CapCut từ template cho video mới mà KHÔNG mang theo media cũ.

    Quy chuẩn nghiêm ngặt:
    1. Lấy cấu hình từ template: Canvas (tỉ lệ, kích thước), Hiệu ứng video (Effects & Filters),
       Video setup (scale, transform x/y, rotation), Hiệu ứng chữ & Phụ đề (font, size, color, animation).
    2. TUYỆT ĐỐI KHÔNG mang theo media cũ của template (video, ảnh, audio cũ) để tránh lỗi 'Media Not Found'.
    3. Đổi mới toàn bộ ID (Draft ID, Timeline ID, Material IDs, Segment IDs) để tránh xung đột bộ nhớ trong CapCut.
    4. Đồng bộ 100% thư mục Timelines/ và dọn dẹp các file cache binary rác (.locked, draft.extra, *.bak)
       nhằm giải quyết triệt để hiện tượng CapCut bị lag treo, không chạy được hoặc không tắt được.
    """
    base_dir = draft_dir or find_capcut_draft_dir()
    if not base_dir or not base_dir.exists():
        raise FileNotFoundError("Không tìm thấy thư mục CapCut Draft trên máy!")

    if Path(template_name).is_dir():
        template_dir = Path(template_name)
    else:
        template_dir = base_dir / template_name

    if not template_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy dự án template: {template_dir}")

    # 1. Đọc metadata video mới
    v_info = get_video_metadata(new_video_path)
    new_duration_us = v_info["duration_us"]
    new_w = v_info["width"]
    new_h = v_info["height"]
    normalized_video_path = str(Path(new_video_path).resolve()).replace("\\", "/")
    video_filename = Path(new_video_path).name

    # 2. Chuẩn bị thư mục dự án mới sạch sẽ
    new_project_dir = base_dir / new_project_name
    if new_project_dir.exists():
        try:
            shutil.rmtree(new_project_dir)
        except Exception:
            pass
    new_project_dir.mkdir(parents=True, exist_ok=True)

    # Copy các tài nguyên hợp lệ từ template (fonts, cover, textures nếu có)
    for item in template_dir.iterdir():
        if item.name in [".locked", "draft.extra", "Timelines", "adjust_mask", "matting", "smart_crop", "qr_upload", "subdraft"]:
            continue
        if item.suffix.lower() in [".bak", ".tmp"]:
            continue
        dest = new_project_dir / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        except Exception as ce:
            logger.debug(f"Bỏ qua copy file {item.name}: {ce}")

    # 3. Đọc template draft_content.json gốc
    orig_draft_content_path = template_dir / "draft_content.json"
    with open(orig_draft_content_path, "r", encoding="utf-8") as f:
        draft_content = json.load(f)

    # 4. Trích xuất Cấu hình & Prototypes từ template
    # A. Video clip setup prototype (scale, transform x/y, rotation, canvas_style)
    clip_prototype = {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}}
    video_extra_refs = []
    main_video_found = find_main_video_material(draft_content)
    main_mat_id = main_video_found.get("id") if main_video_found else ""

    orig_video_tracks = [t for t in draft_content.get("tracks", []) if t.get("type") == "video"]
    if orig_video_tracks:
        for t in orig_video_tracks:
            for s in t.get("segments", []):
                if s.get("material_id") == main_mat_id or not main_mat_id:
                    if "clip" in s and isinstance(s["clip"], dict):
                        clip_prototype = copy.deepcopy(s["clip"])
                    video_extra_refs = copy.deepcopy(s.get("extra_material_refs", []))
                    break
            if video_extra_refs or clip_prototype.get("scale") != {"x": 1.0, "y": 1.0}:
                break

    # B. Canvas Config
    canvas_cfg = draft_content.get("canvas_config") or {}
    cw = int(canvas_cfg.get("width") or 0)
    ch = int(canvas_cfg.get("height") or 0)
    if new_h > new_w and cw > ch and cw > 0 and ch > 0:
        logger.info(f"Video đầu vào là video dọc ({new_w}x{new_h}) nhưng template có Canvas ngang ({cw}x{ch}). Tự động điều chỉnh Canvas dự án CapCut về 9:16 (1080x1920)!")
        draft_content["canvas_config"] = {
            "ratio": "9:16",
            "width": 1080,
            "height": 1920,
            "background": canvas_cfg.get("background")
        }

    # 5. Sinh ID mới toanh cho toàn bộ dự án
    new_timeline_id = str(uuid.uuid4()).upper()
    new_draft_id = str(uuid.uuid4()).upper()
    new_video_mat_id = str(uuid.uuid4()).upper()
    new_video_seg_id = str(uuid.uuid4()).upper()
    current_time_us = int(time.time() * 1_000_000)

    draft_content["id"] = new_timeline_id
    draft_content["name"] = new_project_name
    draft_content["duration"] = new_duration_us
    draft_content["create_time"] = current_time_us
    draft_content["update_time"] = current_time_us

    # 6. DỌN SẠCH TOÀN BỘ MEDIA CŨ - CHỈ GIỮ DUY NHẤT VIDEO MỚI
    mats = draft_content.setdefault("materials", {})

    # A. Tạo mới materials["videos"] CHỈ CHỨA DUY NHẤT VIDEO MỚI
    mats["videos"] = [{
        "aigc_type": "none",
        "audio_fade": None,
        "category_id": "",
        "category_name": "local",
        "check_flag": 63487,
        "crop": {
            "lower_left_x": 0.0,
            "lower_left_y": 1.0,
            "lower_right_x": 1.0,
            "lower_right_y": 1.0,
            "upper_left_x": 0.0,
            "upper_left_y": 0.0,
            "upper_right_x": 1.0,
            "upper_right_y": 0.0
        },
        "crop_ratio": "free",
        "crop_scale": 1.0,
        "duration": new_duration_us,
        "extra_type_option": 0,
        "formula_id": "",
        "freeze": None,
        "gameplay": None,
        "has_audio": True,
        "height": new_h,
        "id": new_video_mat_id,
        "intensifies_audio_path": "",
        "intensifies_path": "",
        "is_ai_generate_content": False,
        "is_unified_beauty_mode": False,
        "local_id": "",
        "local_material_id": "",
        "material_id": "",
        "material_name": video_filename,
        "material_url": "",
        "matting": {
            "flag": 0,
            "has_handled": False,
            "interactive_matting": None,
            "path": "",
            "sky_matting": None,
            "strokes": []
        },
        "media_path": "",
        "object_locked": None,
        "origin_material_id": "",
        "path": normalized_video_path,
        "picture_from": "none",
        "picture_set_category_id": "",
        "picture_set_category_name": "",
        "request_id": "",
        "reverse_intensifies_path": "",
        "reverse_path": "",
        "smart_motion": None,
        "source": 0,
        "source_platform": 0,
        "team_id": "",
        "type": "video",
        "video_algorithm": {
            "algorithms": [],
            "deflicker": None,
            "motion_blur_config": None,
            "noise_reduction": None,
            "path": "",
            "quality_enhance": None,
            "time_range": None
        },
        "width": new_w
    }]

    # B. Xóa sạch toàn bộ audio cũ của template (để video mới tự phát tiếng gốc, không lẫn thoại cũ & không media not found)
    mats["audios"] = []

    # 7. Xây dựng lại Tracks
    raw_tracks = draft_content.get("tracks", [])
    new_tracks = []

    # A. Tạo Track Video duy nhất cho video mới
    video_seg = {
        "id": new_video_seg_id,
        "material_id": new_video_mat_id,
        "source_timerange": {
            "start": 0,
            "duration": new_duration_us
        },
        "target_timerange": {
            "start": 0,
            "duration": new_duration_us
        },
        "speed": 1.0,
        "volume": 1.0,
        "clip": clip_prototype,
        "enable_adjust": True,
        "enable_color_curves": True,
        "enable_color_match_adjust": False,
        "enable_color_wheels": True,
        "enable_lut": True,
        "enable_smart_color_adjust": False,
        "extra_material_refs": video_extra_refs
    }
    new_tracks.append({
        "id": str(uuid.uuid4()).upper(),
        "type": "video",
        "flag": 0,
        "segments": [video_seg]
    })

    # B. Giữ lại các track Effect & Filter (kéo dài độ phủ bằng đúng thời lượng video mới)
    for t in raw_tracks:
        if t.get("type") == "effect":
            eff_track = copy.deepcopy(t)
            eff_track["id"] = str(uuid.uuid4()).upper()
            for s in eff_track.get("segments", []):
                tr = s.get("target_timerange")
                if tr:
                    tr["start"] = 0
                    tr["duration"] = new_duration_us
            new_tracks.append(eff_track)

    # C. Giữ lại track text phụ đề từ template (hoặc các text track khác)
    orig_sub_track, _ = find_subtitle_text_track(raw_tracks)
    if orig_sub_track:
        sub_track_copy = copy.deepcopy(orig_sub_track)
        sub_track_copy["id"] = str(uuid.uuid4()).upper()
        new_tracks.append(sub_track_copy)

    # Gán tracks mới vào dự án
    draft_content["tracks"] = new_tracks

    # 8. Xử lý Subtitles bằng Whisper (nạp 1 lần trên GPU CUDA, tái sử dụng xuyên suốt)
    subtitles_applied = False
    if use_whisper_subtitles:
        if precomputed_subtitles is not None:
            whisper_subs = precomputed_subtitles
        else:
            whisper_subs = transcribe_video_subtitles(
                new_video_path,
                model_size=whisper_model,
                language=whisper_language
            )
        if whisper_subs:
            subtitles_applied = inject_whisper_subtitles(draft_content, whisper_subs)
        else:
            # Video không có thoại -> xóa rỗng segments phụ đề để không giữ chữ template cũ
            sub_tr, _ = find_subtitle_text_track(draft_content["tracks"])
            if sub_tr:
                sub_tr["segments"] = []
                subtitles_applied = True

    # 9. Ghi file draft_content.json tại thư mục gốc của dự án mới
    draft_content_path = new_project_dir / "draft_content.json"
    with open(draft_content_path, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, ensure_ascii=False, indent=2)

    # 10. TẠO VÀ ĐỒNG BỘ CẤU TRÚC TIMELINES/ (Giải quyết triệt để lỗi CapCut bị treo/lag)
    timelines_dir = new_project_dir / "Timelines"
    if timelines_dir.exists():
        try:
            shutil.rmtree(timelines_dir)
        except Exception:
            pass
    timelines_dir.mkdir(parents=True, exist_ok=True)

    timeline_sub_dir = timelines_dir / new_timeline_id
    timeline_sub_dir.mkdir(parents=True, exist_ok=True)

    # Bản draft_content trong Timelines/{new_timeline_id} phải đồng bộ 100% với root
    shutil.copy2(draft_content_path, timeline_sub_dir / "draft_content.json")

    # Ghi Timelines/project.json chuẩn xác cho CapCut
    timelines_project_json = {
        "config": {
            "color_space": -1,
            "hdr_vivid": False,
            "mixed_track_mode_on": False,
            "render_index_track_mode_on": False,
            "use_float_render": False
        },
        "create_time": current_time_us,
        "id": str(uuid.uuid4()).upper(),
        "main_timeline_id": new_timeline_id,
        "timelines": [
            {
                "create_time": current_time_us,
                "id": new_timeline_id,
                "is_marked_delete": False,
                "name": "Dòng thời gian 01",
                "update_time": current_time_us
            }
        ],
        "update_time": current_time_us,
        "version": 0
    }
    with open(timelines_dir / "project.json", "w", encoding="utf-8") as f:
        json.dump(timelines_project_json, f, ensure_ascii=False, indent=2)

    # 11. Xây dựng draft_meta_info.json SẠCH SẼ (CHỈ CHỨA VIDEO MỚI, KHÔNG CHỨA MEDIA CŨ)
    new_meta_material_id = str(uuid.uuid4()).lower()
    root_none_id = str(uuid.uuid4()).lower()

    clean_draft_materials = [
        {
            "type": 0,
            "value": [
                {
                    "ai_group_type": "",
                    "create_time": int(time.time()),
                    "duration": 33333,
                    "enter_from": 0,
                    "extra_info": "",
                    "file_Path": "",
                    "height": 0,
                    "id": root_none_id,
                    "import_time": int(time.time()),
                    "import_time_ms": current_time_us,
                    "item_source": 1,
                    "material_color_tag": "",
                    "md5": "",
                    "metetype": "none",
                    "roughcut_time_range": {"duration": 33333, "start": 0},
                    "sub_time_range": {"duration": -1, "start": -1},
                    "type": 0,
                    "width": 0
                },
                {
                    "ai_group_type": "",
                    "create_time": int(time.time()),
                    "duration": new_duration_us,
                    "enter_from": 0,
                    "extra_info": video_filename,
                    "file_Path": normalized_video_path,
                    "height": new_h,
                    "id": new_meta_material_id,
                    "import_time": int(time.time()),
                    "import_time_ms": current_time_us,
                    "item_source": 1,
                    "material_color_tag": "",
                    "md5": "",
                    "metetype": "video",
                    "roughcut_time_range": {"duration": -1, "start": -1},
                    "sub_time_range": {"duration": -1, "start": -1},
                    "type": 0,
                    "width": new_w
                }
            ]
        },
        {"type": 1, "value": []},
        {"type": 2, "value": []},
        {"type": 3, "value": []},
        {"type": 6, "value": []},
        {"type": 7, "value": []}
    ]

    meta_info_path = new_project_dir / "draft_meta_info.json"
    meta_info = {}
    orig_meta_path = template_dir / "draft_meta_info.json"
    if orig_meta_path.exists():
        try:
            with open(orig_meta_path, "r", encoding="utf-8") as f:
                meta_info = json.load(f)
        except Exception:
            meta_info = {}

    meta_info["draft_id"] = new_draft_id
    meta_info["draft_name"] = new_project_name
    meta_info["draft_fold_path"] = str(new_project_dir).replace("\\", "/")
    meta_info["draft_json_file"] = str(draft_content_path).replace("\\", "/")
    meta_info["draft_root_path"] = str(base_dir).replace("\\", "/")
    meta_info["draft_cover"] = "draft_cover.jpg"
    meta_info["tm_duration"] = new_duration_us
    meta_info["tm_draft_create"] = current_time_us
    meta_info["tm_draft_modified"] = current_time_us
    meta_info["tm_draft_removed"] = 0
    meta_info["draft_materials"] = clean_draft_materials

    with open(meta_info_path, "w", encoding="utf-8") as f:
        json.dump(meta_info, f, ensure_ascii=False, indent=2)

    # 12. Ghi draft_virtual_store.json SẠCH SẼ
    virtual_store_path = new_project_dir / "draft_virtual_store.json"
    virtual_store_data = {
        "draft_materials": [],
        "draft_virtual_store": [
            {
                "type": 0,
                "value": [
                    {
                        "creation_time": 0,
                        "display_name": "",
                        "filter_type": 0,
                        "id": "",
                        "import_time": 0,
                        "import_time_us": 0,
                        "material_color_tag": "",
                        "sort_sub_type": 0,
                        "sort_type": 0,
                        "subdraft_filter_type": 0
                    }
                ]
            },
            {
                "type": 1,
                "value": [
                    {"child_id": root_none_id, "parent_id": ""},
                    {"child_id": new_meta_material_id, "parent_id": ""}
                ]
            },
            {"type": 2, "value": []}
        ]
    }
    with open(virtual_store_path, "w", encoding="utf-8") as f:
        json.dump(virtual_store_data, f, ensure_ascii=False, indent=2)

    # 13. Dọn dẹp sạch sẽ các file rác có thể gây lag/khóa CapCut
    for garbage in [".locked", "draft.extra", "template-2.tmp", "template.tmp", "draft_content.json.bak"]:
        gp = new_project_dir / garbage
        if gp.exists():
            try:
                if gp.is_dir():
                    shutil.rmtree(gp)
                else:
                    gp.unlink()
            except Exception:
                pass

    # 14. Đăng ký vào root_meta_info.json
    root_meta_path = base_dir / "root_meta_info.json"
    if root_meta_path.exists():
        try:
            with open(root_meta_path, "r", encoding="utf-8") as f:
                root_meta = json.load(f)

            all_draft_store = root_meta.get("all_draft_store", [])
            draft_ids = root_meta.get("draft_ids", 0)

            all_draft_store = [d for d in all_draft_store if d.get("draft_name") != new_project_name]

            sample_store = next((d for d in all_draft_store if d.get("draft_name") == template_name), None)
            new_store_entry = dict(sample_store) if sample_store else {}

            new_store_entry.update({
                "draft_id": new_draft_id,
                "draft_name": new_project_name,
                "draft_fold_path": str(new_project_dir).replace("\\", "/"),
                "draft_json_file": str(draft_content_path).replace("\\", "/"),
                "draft_cover": str(new_project_dir / "draft_cover.jpg").replace("\\", "/"),
                "draft_root_path": str(base_dir).replace("\\", "/"),
                "tm_duration": new_duration_us,
                "tm_draft_create": current_time_us,
                "tm_draft_modified": current_time_us,
                "tm_draft_removed": 0
            })

            all_draft_store.insert(0, new_store_entry)
            if isinstance(draft_ids, list):
                if new_draft_id not in draft_ids:
                    draft_ids.insert(0, new_draft_id)
            elif isinstance(draft_ids, int):
                draft_ids += 1

            root_meta["all_draft_store"] = all_draft_store
            root_meta["draft_ids"] = draft_ids

            with open(root_meta_path, "w", encoding="utf-8") as f:
                json.dump(root_meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Lỗi khi cập nhật root_meta_info.json: {e}")

    logger.info(f"✨ Đã tạo thành công dự án CapCut sạch hoàn toàn: {new_project_name} (ID: {new_draft_id})")
    return new_project_dir, new_draft_id


def batch_clone_from_folder(
    template_name: str,
    video_folder: str,
    scale_mode: str = "scale_all",
    use_whisper_subtitles: bool = True,
    whisper_model: str = "large-v3-turbo",
    whisper_language: Optional[str] = None,
    name_prefix: str = "Auto_",
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, any]]:
    """Xử lý nhân bản hàng loạt từ thư mục hoặc 1 file video chỉ định."""
    v_path = Path(video_folder)
    if not v_path.exists():
        raise FileNotFoundError(f"Đường dẫn video không tồn tại: {video_folder}")

    if v_path.is_file():
        video_files = [v_path] if v_path.suffix.lower() in SUPPORTED_VIDEO_EXTS else []
    else:
        video_files = [f for f in v_path.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_VIDEO_EXTS]

    total = len(video_files)
    if total == 0:
        return []

    results = []
    for idx, v_file in enumerate(video_files, start=1):
        clean_stem = v_file.stem.replace(" ", "_")
        proj_name = f"{name_prefix}{clean_stem}"

        msg = f"Đang xử lý ({idx}/{total}): {v_file.name} -> {proj_name}"
        logger.info(msg)
        if progress_callback:
            progress_callback(idx, total, msg)

        try:
            proj_dir, draft_id = clone_and_apply_template(
                template_name=template_name,
                new_project_name=proj_name,
                new_video_path=str(v_file),
                scale_mode=scale_mode,
                use_whisper_subtitles=use_whisper_subtitles,
                whisper_model=whisper_model,
                whisper_language=whisper_language
            )
            results.append({
                "video_name": v_file.name,
                "project_name": proj_name,
                "project_dir": str(proj_dir),
                "draft_id": draft_id,
                "status": "success",
                "error": None
            })
        except Exception as e:
            logger.error(f"Lỗi khi xử lý {v_file.name}: {e}")
            results.append({
                "video_name": v_file.name,
                "project_name": proj_name,
                "project_dir": "",
                "draft_id": "",
                "status": "failed",
                "error": str(e)
            })

    return results


def render_reels_from_template(
    template_name: str,
    new_video_path: str,
    output_video_path: Optional[str] = None,
    draft_dir: Optional[Path] = None,
    zoom_ratio: float = 1.0,
    layout_mode: str = "crop_fill",
    enable_noise: bool = True,
    enable_color_grade: bool = True,
    enable_vignette: bool = False,
    whisper_model: str = "large-v3-turbo",
    whisper_language: Optional[str] = None,
    filter_screams: bool = True,
    use_capcut_pc: bool = True,
    session: Optional[Any] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, any]:
    """Tự động hóa toàn bộ quy trình: Ưu tiên xuất chuẩn 100% bằng CapCut PC, tự động fallback sang FFmpeg."""
    if not output_video_path:
        out_dir = Path("output") / "rendered_videos"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"Rendered_{Path(new_video_path).stem}.mp4"
    else:
        out_file = Path(output_video_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

    # 0. Trích xuất phụ đề giọng nói 1 lần duy nhất bằng faster-whisper trên GPU CUDA
    subtitles = []
    if progress_callback:
        progress_callback(5.0, "Đang nhận diện giọng nói & lọc tiếng hét...")
    try:
        subtitles = transcribe_video_subtitles(
            new_video_path,
            model_size=whisper_model,
            language=whisper_language,
            filter_screams=filter_screams,
            chunk_for_reels=True
        )
    except Exception as we:
        logger.warning(f"Lỗi khi trích xuất phụ đề video: {we}")

    # 1. Ưu tiên: Tự động nhân bản và xuất trực tiếp bằng CapCut PC (100% chuẩn template)
    if use_capcut_pc:
        try:
            from src.core.capcut_exporter import find_capcut_exe, export_capcut_draft_to_video
            if session is not None or find_capcut_exe():
                clean_stem = Path(new_video_path).stem.replace(" ", "_")
                draft_name = f"Auto_{clean_stem}"
                logger.info(f"Đang chuẩn bị dự án CapCut '{draft_name}' theo mẫu '{template_name}'...")
                if progress_callback:
                    progress_callback(15.0, f"Đang tạo dự án CapCut Draft '{draft_name}'...")

                new_project_dir, new_draft_id = clone_and_apply_template(
                    template_name=template_name,
                    new_project_name=draft_name,
                    new_video_path=new_video_path,
                    draft_dir=draft_dir,
                    use_whisper_subtitles=True,
                    whisper_model=whisper_model,
                    whisper_language=whisper_language,
                    precomputed_subtitles=subtitles
                )

                t0 = time.time()
                final_video = export_capcut_draft_to_video(
                    draft_name=draft_name,
                    target_output_path=str(out_file),
                    timeout_sec=45,
                    progress_callback=progress_callback,
                    session=session
                )
                elapsed = time.time() - t0
                return {
                    "output_video": final_video,
                    "elapsed_sec": elapsed,
                    "subtitles_count": len(subtitles),
                    "draft_id": new_draft_id,
                    "method": "capcut_pc",
                    "status": "success"
                }
        except Exception as e:
            logger.warning(f"CapCut PC Auto-Export chưa sẵn sàng hoặc gặp lỗi ({e}). Chuyển sang FFmpeg Engine...")

    # 2. Phương án Fallback: Render tự động bằng FFmpeg Engine nâng cấp (tái sử dụng 100% phụ đề đã nhận diện)
    if Path(template_name).is_dir():
        template_dir = Path(template_name)
    else:
        base_dir = draft_dir or find_capcut_draft_dir()
        template_dir = (base_dir / template_name) if base_dir else None

    style = None
    if template_dir and (template_dir / "draft_content.json").exists():
        style = extract_style_from_capcut_draft(str(template_dir / "draft_content.json"))

    ass_path = None
    fonts_dir = None
    if subtitles:
        temp_ass = Path("output") / "temp_subs" / f"{Path(new_video_path).stem}.ass"
        ass_path = generate_ass_subtitles(subtitles, str(temp_ass), style=style, karaoke_mode=True)
        if style and style.get("font_file"):
            fonts_dir = str(Path(style["font_file"]).parent)

    v_meta = get_video_metadata(new_video_path)
    in_w = v_meta.get("width", 1080)
    in_h = v_meta.get("height", 1920)

    canvas_w = style.get("canvas_w", 1080) if style else 1080
    canvas_h = style.get("canvas_h", 1920) if style else 1920

    # BẢO VỆ TỈ LỆ KHUNG HÌNH (ORIENTATION GUARD):
    # Nếu video đầu vào là DỌC (in_h > in_w) mà Canvas template lại là NGANG (canvas_w > canvas_h):
    # Tuyệt đối không crop ép video dọc thành khung ngang 16:9! Đổi canvas về 1080x1920 dọc chuẩn Reels.
    if in_h > in_w and canvas_w > canvas_h:
        logger.warning(
            f"Video đầu vào là video dọc ({in_w}x{in_h}) nhưng template có canvas ngang ({canvas_w}x{canvas_h}). "
            f"Tự động chuyển Canvas xuất thành 1080x1920 (Dọc chuẩn Reels) để bảo toàn 100% hình ảnh không bị cắt xén!"
        )
        canvas_w, canvas_h = 1080, 1920

    actual_zoom = zoom_ratio
    actual_layout = layout_mode
    # Nếu cả video và canvas cùng là dọc, giữ nguyên trọn vẹn khung hình không bị xén mép
    if in_h > in_w and canvas_h > canvas_w:
        in_ratio = in_h / in_w if in_w > 0 else 1.777
        can_ratio = canvas_h / canvas_w if canvas_w > 0 else 1.777
        if abs(in_ratio - can_ratio) < 0.2:
            actual_zoom = 1.0
            actual_layout = "fit"

    if progress_callback:
        progress_callback(50.0, "Đang render video với FFmpeg...")
    final_video, elapsed = render_reels_video(
        input_video_path=new_video_path,
        output_video_path=str(out_file),
        ass_subtitle_path=ass_path,
        fontsdir=fonts_dir,
        zoom_ratio=actual_zoom,
        layout_mode=actual_layout,
        enable_noise=enable_noise,
        enable_color_grade=enable_color_grade,
        enable_vignette=enable_vignette,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        progress_callback=progress_callback
    )

    return {
        "output_video": final_video,
        "elapsed_sec": elapsed,
        "subtitles_count": len(subtitles),
        "ass_path": ass_path,
        "method": "ffmpeg",
        "status": "success"
    }


def batch_render_reels_from_folder(
    template_name: str,
    video_folder: str,
    output_folder: Optional[str] = None,
    zoom_ratio: float = 1.0,
    layout_mode: str = "crop_fill",
    enable_noise: bool = True,
    enable_color_grade: bool = True,
    enable_vignette: bool = False,
    whisper_model: str = "large-v3",
    whisper_language: Optional[str] = None,
    filter_screams: bool = True,
    use_capcut_pc: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, any]]:
    """Xử lý render hàng loạt toàn bộ video trong thư mục hoặc 1 file video đơn lẻ."""
    v_path = Path(video_folder)
    if not v_path.exists():
        raise FileNotFoundError(f"Đường dẫn video không tồn tại: {video_folder}")

    if v_path.is_file():
        video_files = [v_path] if v_path.suffix.lower() in SUPPORTED_VIDEO_EXTS else []
    else:
        video_files = [f for f in v_path.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_VIDEO_EXTS]

    total = len(video_files)
    if total == 0:
        return []

    target_out_dir = Path(output_folder) if output_folder else (Path("output") / "rendered_videos")
    target_out_dir.mkdir(parents=True, exist_ok=True)

    session = None
    if use_capcut_pc:
        try:
            from src.core.capcut_exporter import find_capcut_exe, CapCutExportSession
            if find_capcut_exe():
                session = CapCutExportSession()
                session.start()
        except Exception as e:
            logger.warning(f"Không thể khởi tạo CapCutExportSession cho batch render: {e}")
            session = None

    try:
        results = []
        for idx, v_file in enumerate(video_files, start=1):
            msg = f"Đang render ({idx}/{total}): {v_file.name}"
            logger.info(msg)
            if progress_callback:
                progress_callback(idx, total, msg)

            out_path = target_out_dir / f"Reel_{v_file.stem}.mp4"
            try:
                res = render_reels_from_template(
                    template_name=template_name,
                    new_video_path=str(v_file),
                    output_video_path=str(out_path),
                    zoom_ratio=zoom_ratio,
                    layout_mode=layout_mode,
                    enable_noise=enable_noise,
                    enable_color_grade=enable_color_grade,
                    enable_vignette=enable_vignette,
                    whisper_model=whisper_model,
                    whisper_language=whisper_language,
                    filter_screams=filter_screams,
                    use_capcut_pc=use_capcut_pc,
                    session=session
                )
                results.append({
                    "video_name": v_file.name,
                    "output_video": res["output_video"],
                    "elapsed_sec": res["elapsed_sec"],
                    "subtitles_count": res.get("subtitles_count", 0),
                    "status": "success",
                    "error": None
                })
            except Exception as e:
                logger.error(f"Lỗi khi render {v_file.name}: {e}")
                results.append({
                    "video_name": v_file.name,
                    "output_video": "",
                    "elapsed_sec": 0,
                    "subtitles_count": 0,
                    "status": "failed",
                    "error": str(e)
                })

        return results
    finally:
        if session:
            try:
                session.close()
            except Exception:
                pass
