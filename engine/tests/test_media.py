from clipfarm_engine.media import ffmpeg, layouts, render
from clipfarm_engine.captions.ass import Word, build_ass

from media_samples import TMP, sample_video, short_clip


def test_probe_reads_real_video_stream():
    info = ffmpeg.probe(sample_video())
    assert (info.width, info.height) == (1280, 720)
    assert 89 < info.duration < 91
    assert info.has_audio


def test_cut_is_frame_accurate():
    info = ffmpeg.probe(short_clip())
    assert abs(info.duration - 6) < 0.2


def test_every_layout_renders_exact_output_size():
    cam = layouts.Rect(0.74, 0.08, 0.25, 0.25)
    cases = [("center", "9:16", None), ("blur", "9:16", None), ("facecam_top", "9:16", cam),
             ("facecam_bottom", "9:16", cam), ("center", "1:1", None), ("center", "4:5", None)]
    for layout, fmt, rect in cases:
        out = TMP / f"layout_{layout}_{fmt.replace(':', 'x')}.mp4"
        render.render_clip(short_clip(), out, layout, fmt, cam=rect)
        info = ffmpeg.probe(out)
        assert (info.width, info.height) == layouts.FORMATS[fmt], (layout, fmt, info)


def test_facecam_split_sizes_add_up():
    graph, ow, oh = layouts.build("facecam_top", 1920, 1080, "9:16", cam=layouts.Rect(0.739, 0.083, 0.246, 0.245))
    assert "vstack" in graph and (ow, oh) == (1080, 1920)
    # cam band height + game band height == 1920
    import re
    heights = [int(h) for h in re.findall(r"scale=1080:(\d+)", graph)]
    assert sum(heights) == 1920


def test_render_with_captions_burns_ass():
    words = [Word(44.5, 44.9, "Putain,"), Word(44.9, 45.2, "oh"), Word(45.2, 45.6, "non"), Word(46.0, 46.6, "incroyable!")]
    ass = TMP / "cap.ass"
    ass.write_text(build_ass(words, offset=44), encoding="utf-8")
    out = TMP / "captioned.mp4"
    render.render_clip(short_clip(), out, "center", "9:16", ass=ass)
    assert ffmpeg.probe(out).height == 1920
