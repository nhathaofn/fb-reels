import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.core.video_renderer import (
    find_ffmpeg_exe,
    has_nvenc_support,
    escape_ffmpeg_filter_path,
    build_reels_filtergraph,
    render_reels_video
)


def test_find_ffmpeg_exe():
    exe = find_ffmpeg_exe()
    assert exe is not None
    assert Path(exe).exists()


def test_has_nvenc_support():
    nvenc = has_nvenc_support()
    assert isinstance(nvenc, bool)
    assert nvenc is True  # Máy tính có card NVIDIA


def test_escape_ffmpeg_filter_path():
    raw_p = r"C:\Users\Test User\video.ass"
    escaped = escape_ffmpeg_filter_path(raw_p)
    assert r"\:" in escaped
    assert "\\" not in escaped.replace(r"\:", "")


def test_build_reels_filtergraph():
    fg = build_reels_filtergraph(
        ass_subtitle_path="output/test.ass",
        zoom_ratio=1.1,
        layout_mode="crop_fill",
        enable_noise=True,
        enable_color_grade=True,
        enable_vignette=True,
        check_exists=False
    )
    assert "scale=" in fg
    assert "crop=" in fg
    assert "noise=" in fg
    assert "eq=" in fg
    assert "vignette=" in fg
    assert "ass=" in fg


def test_render_reels_video_dummy(tmp_path):
    import subprocess
    ffmpeg_bin = find_ffmpeg_exe()

    # Tạo video mẫu 1 giây
    dummy_in = tmp_path / "dummy_in.mp4"
    gen_cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=duration=1:frequency=1000",
        "-c:v", "libx264", "-c:a", "aac",
        str(dummy_in)
    ]
    subprocess.run(gen_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    dummy_out = tmp_path / "dummy_out.mp4"
    out_file, elapsed = render_reels_video(
        input_video_path=str(dummy_in),
        output_video_path=str(dummy_out),
        zoom_ratio=1.0,
        layout_mode="crop_fill",
        enable_noise=True,
        enable_color_grade=True
    )

    assert Path(out_file).exists()
    assert Path(out_file).stat().st_size > 0
    assert elapsed > 0
