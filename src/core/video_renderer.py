"""Module render video tự động chất lượng cao bằng FFmpeg (Video Renderer).

Tối ưu cho định dạng Reels / TikTok / Shorts:
- Phóng to (Zoom / Scale) & căn chỉnh khung hình dọc 1080x1920 (Crop Fill hoặc Blur Padding).
- Áp dụng hiệu ứng video (Hạt nhiễu điện ảnh/film grain, Chỉnh màu tương phản tươi, Viền tối góc vignette).
- Ép phụ đề Karaoke nhảy chữ trực tiếp bằng thư viện libass siêu nét.
- Tự động phát hiện GPU NVIDIA (NVENC) để tăng tốc độ render (3-5 giây/video).
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from src.utils.logger import logger

KNOWN_FFMPEG_PATHS = [
    r"C:\Program Files\PySceneDetect\ffmpeg.EXE",
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
]

_NVENC_CACHE: Optional[bool] = None


def find_ffmpeg_exe() -> str:
    """Tìm đường dẫn thực thi của ffmpeg trên hệ thống."""
    # 1. Tìm ngay trong thư mục ứng dụng hoặc thư mục con bin/tools (hỗ trợ portable không cần cài đặt)
    try:
        from src.config import BASE_DIR
        app_candidates = [
            BASE_DIR / "ffmpeg.exe",
            BASE_DIR / "bin" / "ffmpeg.exe",
            BASE_DIR / "tools" / "ffmpeg.exe",
            BASE_DIR / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
        for c in app_candidates:
            if c.exists() and c.is_file():
                return str(c.resolve())
    except Exception:
        pass

    # 2. Tìm trong PATH hệ thống
    in_path = shutil.which("ffmpeg")
    if in_path and Path(in_path).exists():
        return str(Path(in_path).resolve())

    # 3. Tìm trong các đường dẫn cài đặt phổ biến trên Windows
    for p in KNOWN_FFMPEG_PATHS:
        if Path(p).exists():
            return str(Path(p).resolve())

    raise FileNotFoundError(
        "Không tìm thấy công cụ FFmpeg trên hệ thống! Vui lòng đặt file ffmpeg.exe vào cùng thư mục ứng dụng hoặc cài đặt FFmpeg vào PATH."
    )


def has_nvenc_support() -> bool:
    """Kiểm tra máy có hỗ trợ bộ mã hóa GPU NVIDIA NVENC hay không."""
    global _NVENC_CACHE
    if _NVENC_CACHE is not None:
        return _NVENC_CACHE

    try:
        ffmpeg_bin = find_ffmpeg_exe()
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=640x360:rate=30",
            "-c:v", "h264_nvenc",
            "-f", "null", "-"
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _NVENC_CACHE = (res.returncode == 0)
    except Exception:
        _NVENC_CACHE = False

    return _NVENC_CACHE


def escape_ffmpeg_filter_path(path_str: str) -> str:
    """Chuẩn hóa đường dẫn file trên Windows để dùng an toàn trong FFmpeg filter."""
    clean = str(Path(path_str).resolve()).replace("\\", "/")
    # Escape dấu hai chấm trong ổ đĩa (ví dụ C: -> C\:)
    clean = clean.replace(":", r"\:")
    return clean


def build_reels_filtergraph(
    ass_subtitle_path: Optional[str] = None,
    fontsdir: Optional[str] = None,
    zoom_ratio: float = 1.0,
    layout_mode: str = "crop_fill",
    enable_noise: bool = True,
    enable_color_grade: bool = True,
    enable_vignette: bool = False,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    check_exists: bool = True
) -> str:
    """Xây dựng chuỗi filtergraph hoàn chỉnh cho FFmpeg."""
    filters = []

    # 1. Phóng to và định dạng khung hình
    zoom = max(1.0, min(2.5, float(zoom_ratio)))
    if layout_mode == "blur_pad":
        # Nền mờ phía sau + video ở giữa
        scale_w = int(canvas_w * zoom)
        scale_h = int(canvas_h * zoom)
        fg_scale = f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=decrease"
        bg_scale = f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,crop={canvas_w}:{canvas_h},boxblur=25:5"
        filter_base = f"split[main][bg];[bg]{bg_scale}[bg_blur];[main]{fg_scale}[fg];[bg_blur][fg]overlay=(W-w)/2:(H-h)/2"
        filters.append(filter_base)
    else:
        # Mặc định: Phóng to và Crop giữa (Center Zoom & Crop vừa 1080x1920)
        target_w = int(canvas_w * zoom)
        target_h = int(canvas_h * zoom)
        filter_scale = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h}:(in_w-{canvas_w})/2:(in_h-{canvas_h})/2"
        )
        filters.append(filter_scale)

    # 2. Hiệu ứng chỉnh màu (Color grading tươi và tương phản)
    if enable_color_grade:
        filters.append("eq=contrast=1.06:saturation=1.12:brightness=0.01")

    # 3. Hiệu ứng hạt nhiễu cổ điển (Film grain / Noise)
    if enable_noise:
        filters.append("noise=alls=12:allf=t+u")

    # 4. Hiệu ứng viền tối góc (Vignette)
    if enable_vignette:
        filters.append("vignette=PI/4.5")

    # 5. Ép phụ đề ASS (Karaoke Subtitles)
    if ass_subtitle_path:
        p = Path(ass_subtitle_path)
        if not check_exists or p.exists():
            escaped_sub = escape_ffmpeg_filter_path(ass_subtitle_path)
            if fontsdir and Path(fontsdir).exists():
                esc_fontsdir = escape_ffmpeg_filter_path(fontsdir)
                filters.append(f"ass='{escaped_sub}':fontsdir='{esc_fontsdir}'")
            else:
                filters.append(f"ass='{escaped_sub}'")

    return ",".join(filters)


def render_reels_video(
    input_video_path: str,
    output_video_path: str,
    ass_subtitle_path: Optional[str] = None,
    fontsdir: Optional[str] = None,
    zoom_ratio: float = 1.0,
    layout_mode: str = "crop_fill",
    enable_noise: bool = True,
    enable_color_grade: bool = True,
    enable_vignette: bool = False,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    use_gpu: bool = True,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[str, float]:
    """Render video hoàn chỉnh bằng FFmpeg.
    
    Returns:
        Tuple[str, float]: (Đường dẫn file video thành phẩm, Thời gian render tính bằng giây).
    """
    in_p = Path(input_video_path)
    if not in_p.exists():
        raise FileNotFoundError(f"Không tìm thấy video đầu vào: {input_video_path}")

    out_p = Path(output_video_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = find_ffmpeg_exe()
    filtergraph = build_reels_filtergraph(
        ass_subtitle_path=ass_subtitle_path,
        fontsdir=fontsdir,
        zoom_ratio=zoom_ratio,
        layout_mode=layout_mode,
        enable_noise=enable_noise,
        enable_color_grade=enable_color_grade,
        enable_vignette=enable_vignette,
        canvas_w=canvas_w,
        canvas_h=canvas_h
    )

    # Chọn encoder GPU hoặc CPU
    can_gpu = use_gpu and has_nvenc_support()
    if can_gpu:
        v_codec = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "22", "-b:v", "0"]
    else:
        v_codec = ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p"]

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(in_p),
        "-vf", filtergraph,
        *v_codec,
        "-c:a", "aac", "-b:a", "192k",
        str(out_p)
    ]

    logger.info(f"Bắt đầu render video: {in_p.name} -> {out_p.name} (GPU: {can_gpu})...")
    if progress_callback:
        progress_callback(10.0, f"Đang render video {in_p.name}...")

    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    elapsed = time.time() - t0

    if res.returncode != 0:
        err_msg = res.stderr[-800:] if res.stderr else "Lỗi không xác định từ FFmpeg"
        logger.error(f"Render video thất bại: {err_msg}")
        raise RuntimeError(f"FFmpeg render failed:\n{err_msg}")

    if not out_p.exists() or out_p.stat().st_size == 0:
        raise RuntimeError("File video xuất ra không tồn tại hoặc có dung lượng 0 byte!")

    logger.info(f"Render video thành công: {out_p.name} trong {elapsed:.2f}s!")
    if progress_callback:
        progress_callback(100.0, f"Hoàn thành trong {elapsed:.2f}s")

    return str(out_p), elapsed
