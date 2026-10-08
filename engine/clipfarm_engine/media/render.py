"""Final clip render: layout + burned-in ASS captions, with multi-segment timeline support."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import ffmpeg, layouts


def render_clip(
    raw: str | Path,
    out: str | Path,
    layout: str = "center",
    fmt: str = "9:16",
    ass: str | Path | None = None,
    cam: layouts.Rect | None = None,
    crf: int = 18,
    **layout_kw,
) -> Path:
    """Render a cut clip into its final format.

    ffmpeg runs from the folder of the .ass file so the subtitle path needs no
    escaping (Windows drive letters break the ass= filter otherwise).
    """
    raw, out = Path(raw).resolve(), Path(out).resolve()
    info = ffmpeg.probe(raw)
    graph, _, _ = layouts.build(layout, info.width, info.height, fmt, cam=cam, **layout_kw)
    cwd = None
    if ass:
        ass = Path(ass).resolve()
        cwd = ass.parent
        graph = graph[: -len("[v]")] + f"[pre];[pre]ass={ass.name}[v]"
    args = ["-i", str(raw), "-filter_complex", graph, "-map", "[v]"]
    if info.has_audio:
        args += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"]
    args += [
        "-dn",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
    ]
    if ffmpeg.has_nvenc():
        args += ["-c:v", "h264_nvenc", "-preset", "fast", "-cq", str(crf)]
    else:
        args += ["-c:v", "libx264", "-preset", "fast", "-crf", str(crf)]

    args += [
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out),
    ]

    try:
        ffmpeg.run(args, cwd=cwd)
    except ffmpeg.FFmpegError:
        if ffmpeg.has_nvenc():
            # Repli de secours sur libx264 si NVENC échoue
            idx = args.index("-c:v")
            args[idx : idx + 4] = ["-c:v", "libx264", "-preset", "fast", "-crf", str(crf)]
            ffmpeg.run(args, cwd=cwd)
        else:
            raise
    return out


def render_timeline_clip(
    raw: str | Path,
    out: str | Path,
    clip_start: float,
    clip_end: float,
    timeline: list[dict[str, Any]] | None = None,
    cam: layouts.Rect | None = None,
    default_layout: str = "center",
    fmt: str = "9:16",
    ass: str | Path | None = None,
    crf: int = 18,
    **layout_kw,
) -> Path:
    """Render a clip according to the timeline: overlay -> facecam_top, fullscreen/gameplay -> center.

    If segment type changes midway through the clip, renders each sub-segment then concatenates.
    """
    raw, out = Path(raw).resolve(), Path(out).resolve()

    # Garde-fou recouvrement : interdiction absolue que la bande caméra et la bande jeu montrent la même zone (> 20%)
    if cam:
        from .layouts import FORMATS, check_cam_game_overlap
        info_v = ffmpeg.probe(raw)
        ow, oh = FORMATS.get(fmt, (1080, 1920))
        overlap = check_cam_game_overlap(info_v.width, info_v.height, ow, oh, cam)
        if overlap > 0.20:
            cam = None
            default_layout = "center"

    # 1. Identifier les tranches temporelles du clip dans la timeline
    active_segments = []
    if timeline:
        for seg in timeline:
            s_start = max(clip_start, float(seg["start"]))
            s_end = min(clip_end, float(seg["end"]))
            if s_end - s_start > 0.4:
                active_segments.append((s_start, s_end, seg["type"]))

    # Garde-fou transitions : maximum 2 changements de mise en page par clip
    if len(active_segments) > 1:
        from ..vision.facecam import limit_clip_transitions
        active_segments = limit_clip_transitions(active_segments, max_transitions=2)

    types = {s[2] for s in active_segments}

    # Si pas de changement au sein du clip (ou timeline vide)
    if len(types) <= 1:
        chosen_type = list(types)[0] if types else "gameplay"
        seg_layout = default_layout
        if chosen_type == "overlay" and cam:
            seg_layout = "facecam_top"
        elif chosen_type in ("fullscreen", "gameplay"):
            seg_layout = "center"
        return render_clip(
            raw,
            out,
            layout=seg_layout,
            fmt=fmt,
            ass=ass,
            cam=cam if seg_layout != "center" else None,
            crf=crf,
            **layout_kw,
        )

    # 2. Multi-segments : rendu de chaque partie au même format puis concaténation
    tmp_dir = out.parent / f"tmp_concat_{out.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    part_files: list[Path] = []

    try:
        for idx, (s_start, s_end, s_type) in enumerate(active_segments):
            sub_raw = tmp_dir / f"sub_{idx:02d}.raw.mp4"
            cut_start = max(0.0, s_start - clip_start)
            cut_end = max(cut_start + 0.1, s_end - clip_start)
            ffmpeg.cut(raw, sub_raw, cut_start, cut_end)

            sub_layout = "facecam_top" if s_type == "overlay" and cam else "center"
            sub_rendered = tmp_dir / f"sub_{idx:02d}.mp4"
            render_clip(
                sub_raw,
                sub_rendered,
                layout=sub_layout,
                fmt=fmt,
                ass=None,
                cam=cam if sub_layout != "center" else None,
                crf=crf,
                **layout_kw,
            )
            part_files.append(sub_rendered)

        # Assemblage par concat demuxer
        assembled = tmp_dir / "assembled.mp4"
        concat_txt = tmp_dir / "concat_list.txt"
        lines = [f"file '{p.name}'" for p in part_files]
        concat_txt.write_text("\n".join(lines), encoding="utf-8")

        ffmpeg.run(["-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-c", "copy", str(assembled)], cwd=tmp_dir)

        # 3. Incrustation du sous-titre sur la vidéo finale assemblée
        if ass:
            ass = Path(ass).resolve()
            ffmpeg.run([
                "-i", str(assembled),
                "-vf", f"ass={ass.name}",
                "-c:v", "libx264", "-preset", "fast", "-crf", str(crf), "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-movflags", "+faststart", str(out)
            ], cwd=ass.parent)
        else:
            if out.exists():
                out.unlink()
            shutil.copyfile(assembled, out)
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass

    return out
