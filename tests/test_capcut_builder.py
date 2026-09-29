import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock, patch
from src.core.capcut_builder import (
    find_capcut_draft_dir,
    get_capcut_templates,
    get_video_metadata,
    clone_and_apply_template,
    batch_clone_from_folder
)


def test_find_capcut_draft_dir():
    draft_dir = find_capcut_draft_dir()
    assert draft_dir is not None
    assert draft_dir.exists()


def test_get_capcut_templates():
    templates = get_capcut_templates(filter_template_keyword=True)
    assert len(templates) > 0
    names = [t["name"] for t in templates]
    assert "template-fb" in names
    for n in names:
        assert "template" in n.lower()


def test_get_video_metadata():
    video_path = Path(r"D:\nhathao\gehihi 2.0\reels_fb\output\videos\1_1098330379252955.mp4")
    if video_path.exists():
        meta = get_video_metadata(str(video_path))
        assert meta["width"] == 720
        assert meta["height"] == 1280
        assert meta["duration_sec"] > 0


def test_clone_and_apply_template():
    video_path = Path(r"D:\nhathao\gehihi 2.0\reels_fb\output\videos\1_1098330379252955.mp4")
    if video_path.exists():
        proj_dir, draft_id = clone_and_apply_template(
            template_name="template-fb",
            new_project_name="Test_Auto_Reel",
            new_video_path=str(video_path),
            scale_mode="scale_all",
            use_whisper_subtitles=False
        )
        assert proj_dir.exists()
        assert (proj_dir / "draft_content.json").exists()
        assert draft_id != ""


def test_inject_whisper_subtitles():
    from src.core.capcut_builder import inject_whisper_subtitles
    import json
    
    draft_file = Path(r"C:\Users\PC\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\template-fb\draft_content.json")
    if draft_file.exists():
        with open(draft_file, "r", encoding="utf-8") as f:
            d = json.load(f)
        subs = [
            {"start": 0.0, "end": 2.0, "text": "Hello world!"},
            {"start": 2.5, "end": 4.5, "text": "This is a test subtitle."}
        ]
        ok = inject_whisper_subtitles(d, subs)
        assert ok is True
        text_track = next((t for t in d["tracks"] if t["type"] == "text"), None)
        assert len(text_track["segments"]) == 2
        assert text_track["segments"][0]["target_timerange"]["start"] == 0
        assert text_track["segments"][0]["target_timerange"]["duration"] == 2000000


def test_render_reels_from_template(tmp_path):
    from unittest.mock import patch
    from src.core.capcut_builder import render_reels_from_template

    # Tạo mock dummy video
    dummy_in = tmp_path / "dummy_reel.mp4"
    dummy_out = tmp_path / "rendered_reel.mp4"

    import subprocess
    from src.core.video_renderer import find_ffmpeg_exe
    ffmpeg_bin = find_ffmpeg_exe()
    gen_cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=duration=1:frequency=1000",
        "-c:v", "libx264", "-c:a", "aac",
        str(dummy_in)
    ]
    subprocess.run(gen_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Mock transcribe để test nhanh không cần load model whisper
    mock_subs = [
        {"start": 0.0, "end": 0.8, "text": "Free Fire", "words": [{"word": "Free", "start": 0.0, "end": 0.4}, {"word": "Fire", "start": 0.4, "end": 0.8}]}
    ]
    with patch("src.core.capcut_builder.transcribe_video_subtitles", return_value=mock_subs):
        res = render_reels_from_template(
            template_name="template-fb",
            new_video_path=str(dummy_in),
            output_video_path=str(dummy_out),
            zoom_ratio=1.0,
            enable_noise=False,
            enable_color_grade=False,
            use_capcut_pc=False
        )

    assert res["status"] == "success"
    assert Path(res["output_video"]).exists()
    assert Path(res["output_video"]).stat().st_size > 0
    assert res["subtitles_count"] == 1


def test_find_subtitle_text_track_multi_track():
    from src.core.capcut_builder import find_subtitle_text_track

    # Mock tracks: Track 0 là Header tiêu đề (1 segment, y=0.8), Track 1 là Subtitle (3 segments, y=-0.7)
    tracks = [
        {
            "type": "text",
            "segments": [
                {"material_id": "HEADER_MAT", "clip": {"transform": {"y": 0.8}}}
            ]
        },
        {
            "type": "text",
            "segments": [
                {"material_id": "SUB_MAT_1", "clip": {"transform": {"y": -0.7}}},
                {"material_id": "SUB_MAT_2", "clip": {"transform": {"y": -0.7}}},
                {"material_id": "SUB_MAT_3", "clip": {"transform": {"y": -0.7}}},
            ]
        }
    ]

    best_track, idx = find_subtitle_text_track(tracks)
    assert idx == 1
    assert len(best_track["segments"]) == 3


def test_inject_whisper_subtitles_plain_text():
    """Kiểm tra inject subtitle với template dùng text thuần (không qua text_templates)."""
    import json
    from src.core.capcut_builder import inject_whisper_subtitles

    mock_draft = {
        "materials": {
            "texts": [
                {
                    "id": "TEXT_BASE_1",
                    "content": json.dumps({"text": "Old Template Text", "styles": []}),
                    "font_size": 12,
                    "text_color": "#FFFFFF"
                }
            ],
            "text_templates": []
        },
        "tracks": [
            {
                "type": "text",
                "segments": [
                    {
                        "id": "SEG_OLD_1",
                        "material_id": "TEXT_BASE_1",
                        "clip": {"transform": {"y": -0.75}},
                        "extra_material_refs": []
                    }
                ]
            }
        ]
    }

    whisper_subs = [
        {"start": 0.5, "end": 2.0, "text": "Câu thoại mới 1"},
        {"start": 2.5, "end": 4.0, "text": "Câu thoại mới 2"}
    ]

    ok = inject_whisper_subtitles(mock_draft, whisper_subs)
    assert ok is True
    track = mock_draft["tracks"][0]
    assert len(track["segments"]) == 2
    # Vật liệu text mới được tạo
    created_texts = mock_draft["materials"]["texts"]
    assert any(t.get("recognize_text") == "Câu thoại mới 1" for t in created_texts)
    assert any(t.get("recognize_text") == "Câu thoại mới 2" for t in created_texts)


def test_inject_whisper_subtitles_empty_when_no_voice():
    """Khi video không có giọng nói (whisper_subs=[]), track subtitle cũ bị làm sạch."""
    import json
    from src.core.capcut_builder import inject_whisper_subtitles

    mock_draft = {
        "materials": {
            "texts": [{"id": "T1", "content": json.dumps({"text": "Hello"})}]
        },
        "tracks": [
            {
                "type": "text",
                "segments": [{"material_id": "T1"}]
            }
        ]
    }

    ok = inject_whisper_subtitles(mock_draft, [])
    assert ok is True
    assert len(mock_draft["tracks"][0]["segments"]) == 0


def test_find_main_video_material_multi_video():
    """Kiểm tra tìm đúng video chính khi template có video intro ngắn và video chính dài."""
    from src.core.capcut_builder import find_main_video_material

    mock_draft = {
        "materials": {
            "videos": [
                {"id": "INTRO_VID", "duration": 2_000_000, "material_name": "intro.mp4"},
                {"id": "MAIN_VID", "duration": 30_000_000, "material_name": "main.mp4"},
            ]
        },
        "tracks": [
            {
                "type": "video",
                "segments": [
                    {"material_id": "INTRO_VID", "target_timerange": {"duration": 2_000_000}},
                    {"material_id": "MAIN_VID", "target_timerange": {"duration": 30_000_000}}
                ]
            }
        ]
    }

    main_v = find_main_video_material(mock_draft)
    assert main_v is not None
    assert main_v["id"] == "MAIN_VID"


def test_batch_render_reuses_capcut_session(tmp_path):
    """Kiểm tra batch_render_reels_from_folder chỉ tạo duy nhất 1 CapCutExportSession cho nhiều video."""
    from src.core.capcut_builder import batch_render_reels_from_folder
    
    v1 = tmp_path / "v1.mp4"
    v2 = tmp_path / "v2.mp4"
    v1.write_bytes(b"123")
    v2.write_bytes(b"456")

    with patch("src.core.capcut_exporter.find_capcut_exe", return_value=Path("C:/CapCut/CapCut.exe")), \
         patch("src.core.capcut_exporter.CapCutExportSession") as mock_session_cls, \
         patch("src.core.capcut_builder.render_reels_from_template") as mock_render:

        mock_session_instance = MagicMock()
        mock_session_cls.return_value = mock_session_instance

        mock_render.side_effect = [
            {"output_video": str(tmp_path / "out1.mp4"), "elapsed_sec": 1.0, "status": "success"},
            {"output_video": str(tmp_path / "out2.mp4"), "elapsed_sec": 1.0, "status": "success"}
        ]

        results = batch_render_reels_from_folder(
            template_name="template-fb",
            video_folder=str(tmp_path),
            output_folder=str(tmp_path / "out"),
            use_capcut_pc=True
        )

        assert len(results) == 2
        # Kiểm tra CapCutExportSession chỉ được khởi tạo đúng 1 lần cho cả 2 video
        mock_session_cls.assert_called_once()
        assert mock_render.call_count == 2
        # Cả 2 lần render đều được truyền cùng 1 session instance
        assert mock_render.call_args_list[0][1]["session"] == mock_session_instance
        assert mock_render.call_args_list[1][1]["session"] == mock_session_instance




