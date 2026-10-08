"""Vertical (or other ratio) layouts expressed as ffmpeg filter graphs.

Everything is computed in absolute pixels from the probed source size, so the
graph never depends on ffmpeg expression parsing and always yields even sizes.

Input label is [0:v], output label is [v].
"""

from __future__ import annotations

from dataclasses import dataclass

FORMATS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}


@dataclass
class Rect:
    """Rectangle in relative coordinates (0..1) of the source frame."""

    x: float
    y: float
    w: float
    h: float

    def to_px(self, sw: int, sh: int) -> tuple[int, int, int, int]:
        x, y = int(self.x * sw), int(self.y * sh)
        w, h = _even(self.w * sw), _even(self.h * sh)
        w, h = min(w, sw - x - (sw - x) % 2), min(h, sh - y - (sh - y) % 2)
        return x, y, w, h


def _even(v: float) -> int:
    i = int(round(v))
    return max(2, i - (i % 2))


def _crop_to_aspect(x: int, y: int, w: int, h: int, aspect: float, focus_x: float = 0.5) -> tuple[int, int, int, int]:
    """Largest crop of aspect (w/h) inside the box, centred on focus_x (relative to the box)."""
    if w / h > aspect:
        nw = _even(h * aspect)
        nx = x + int(min(max(focus_x * w - nw / 2, 0), w - nw))
        return nx, y, nw, h
    nh = _even(w / aspect)
    ny = y + (h - nh) // 2
    return x, ny, w, nh


def center(sw: int, sh: int, ow: int, oh: int, focus_x: float = 0.5) -> str:
    x, y, w, h = _crop_to_aspect(0, 0, sw, sh, ow / oh, focus_x)
    return f"[0:v]crop={w}:{h}:{x}:{y},scale={ow}:{oh}:flags=lanczos,setsar=1[v]"


def blur(sw: int, sh: int, ow: int, oh: int) -> str:
    return (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={ow}:{oh}:force_original_aspect_ratio=increase,crop={ow}:{oh},boxblur=30:5[bgb];"
        f"[fg]scale={ow}:-2:flags=lanczos[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
    )


def facecam_split(
    sw: int, sh: int, ow: int, oh: int, cam: Rect,
    cam_position: str = "top", max_cam_ratio: float = 0.40, focus_x: float = 0.5,
) -> str:
    """Streamer facecam on one band, gameplay on the other."""
    cx, cy, cw, ch = cam.to_px(sw, sh)
    cam_h = min(_even(ow * ch / cw), _even(oh * max_cam_ratio))
    game_h = oh - cam_h
    cx, cy, cw, ch = _crop_to_aspect(cx, cy, cw, ch, ow / cam_h)
    gx, gy, gw, gh = _crop_to_aspect(0, 0, sw, sh, ow / game_h, focus_x)
    cam_chain = f"[a]crop={cw}:{ch}:{cx}:{cy},scale={ow}:{cam_h}:flags=lanczos,setsar=1[c]"
    game_chain = f"[b]crop={gw}:{gh}:{gx}:{gy},scale={ow}:{game_h}:flags=lanczos,setsar=1[g]"
    order = "[c][g]" if cam_position == "top" else "[g][c]"
    return f"[0:v]split=2[a][b];{cam_chain};{game_chain};{order}vstack=inputs=2[v]"


def check_cam_game_overlap(
    sw: int, sh: int, ow: int, oh: int, cam: Rect,
    max_cam_ratio: float = 0.40, focus_x: float = 0.5,
) -> float:
    """Calculate the overlap ratio between the camera crop and the gameplay crop in the source frame.

    Returns the intersection area divided by the camera area (0.0 to 1.0).
    """
    cx, cy, cw, ch = cam.to_px(sw, sh)
    cam_h = min(_even(ow * ch / cw), _even(oh * max_cam_ratio))
    game_h = oh - cam_h
    cx, cy, cw, ch = _crop_to_aspect(cx, cy, cw, ch, ow / cam_h)
    gx, gy, gw, gh = _crop_to_aspect(0, 0, sw, sh, ow / game_h, focus_x)

    inter_x1 = max(cx, gx)
    inter_y1 = max(cy, gy)
    inter_x2 = min(cx + cw, gx + gw)
    inter_y2 = min(cy + ch, gy + gh)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    cam_area = max(1, cw * ch)

    return inter_area / cam_area


def build(layout: str, sw: int, sh: int, fmt: str = "9:16", cam: Rect | None = None, **kw) -> tuple[str, int, int]:
    ow, oh = FORMATS[fmt]
    if layout == "center":
        return center(sw, sh, ow, oh, kw.get("focus_x", 0.5)), ow, oh
    if layout == "blur":
        return blur(sw, sh, ow, oh), ow, oh
    if layout in ("facecam_top", "facecam_bottom"):
        if cam is None:
            raise ValueError("layout facecam: il faut la zone de la camera (cam=Rect)")
        pos = "top" if layout == "facecam_top" else "bottom"
        return facecam_split(sw, sh, ow, oh, cam, pos, kw.get("max_cam_ratio", 0.40), kw.get("focus_x", 0.5)), ow, oh
    raise ValueError(f"layout inconnu: {layout}")
