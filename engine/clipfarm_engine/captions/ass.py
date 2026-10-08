"""Word-by-word "karaoke" captions as an ASS file (rendered by libass in ffmpeg).

Short chunks (1-3 words), the spoken word highlighted and slightly popped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Word:
    start: float
    end: float
    text: str
    prob: float = 1.0
    speaker: str | None = None


@dataclass
class CaptionStyle:
    font: str = "Arial Black"
    size: int = 72
    color: str = "&H00FFFFFF"          # ASS colours are &HAABBGGRR
    highlight: str = "&H0000FFFF"      # yellow
    outline_color: str = "&H00000000"
    outline: int = 6
    shadow: int = 3
    margin_v: int = 300                # px from the bottom on a 1920px-high frame
    margin_h: int = 80
    alignment: int = 2                 # bottom centre
    uppercase: bool = True
    pop: int = 115                     # % scale of the active word, 100 = off
    max_words: int = 3
    max_chars: int = 18
    max_gap: float = 0.6               # seconds of silence that force a new chunk
    max_word: float = 0.9              # a word is never highlighted longer than this (alignment can stretch words over pauses)


PRESETS: dict[str, CaptionStyle] = {
    "punchy": CaptionStyle(),
    "clean": CaptionStyle(font="Arial", size=64, highlight="&H00FFFFFF", uppercase=False, pop=100, outline=4, shadow=0, max_words=5, max_chars=28),
    "green": CaptionStyle(highlight="&H0000FF7F"),
}


def ts(t: float) -> str:
    t = max(t, 0.0)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(text: str) -> str:
    return text.replace("{", "").replace("}", "").replace("\\", "").strip()


_PUNCT_ONLY = re.compile(r"^[^\w]+$")


def normalize_words(words: list[Word], max_word: float = 0.9) -> list[Word]:
    """Glue punctuation-only tokens (French '!' '?' come as separate words) to the previous word,
    and clamp words that the aligner stretched over a pause."""
    out: list[Word] = []
    for w in words:
        text = _clean(w.text)
        if not text:
            continue
        # French elision: Whisper splits "c'est" into "c" + "'est" (or "c'" + "est")
        if out and (_PUNCT_ONLY.match(text) or text[0] in "'\u2019" or out[-1].text[-1] in "'\u2019"):
            out[-1].text += text
            out[-1].end = max(out[-1].end, min(w.end, out[-1].start + max_word))
            continue
        if _PUNCT_ONLY.match(text):
            continue
        out.append(Word(w.start, min(w.end, w.start + max_word), text, w.prob, w.speaker))
    return out


def chunk_words(words: list[Word], style: CaptionStyle) -> list[list[Word]]:
    chunks: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur:
            joined = " ".join(x.text for x in cur + [w])
            if len(cur) >= style.max_words or len(joined) > style.max_chars or w.start - cur[-1].end > style.max_gap:
                chunks.append(cur)
                cur = []
        cur.append(w)
        if w.text and w.text[-1] in ".?!":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(
    words: list[Word],
    style: CaptionStyle | None = None,
    play_res: tuple[int, int] = (1080, 1920),
    offset: float = 0.0,
    position: str = "bottom",
) -> str:
    """offset is subtracted from every timestamp (use the clip start when words come from the full video).

    position: 'bottom' (default) or 'top' (places captions near top of screen/game area).
    """
    from dataclasses import replace

    st = style or CaptionStyle()
    if position == "top":
        st = replace(st, alignment=8, margin_v=150)

    words = normalize_words([Word(w.start - offset, w.end - offset, w.text, w.prob, w.speaker) for w in words], st.max_word)
    words = [w for w in words if w.end > 0]
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {play_res[0]}\nPlayResY: {play_res[1]}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{st.font},{st.size},{st.color},{st.color},{st.outline_color},&H80000000,1,0,0,0,100,100,0,0,1,"
        f"{st.outline},{st.shadow},{st.alignment},{st.margin_h},{st.margin_h},{st.margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for chunk in chunk_words(words, st):
        for i, w in enumerate(chunk):
            if i + 1 < len(chunk):
                # never overlap the next word, otherwise libass stacks two lines on screen
                end = min(chunk[i + 1].start, w.start + st.max_word)
            else:
                end = max(min(w.end, w.start + st.max_word), w.start + 0.12)
            if end <= w.start:
                continue
            parts = []
            for j, other in enumerate(chunk):
                t = other.text.upper() if st.uppercase else other.text
                if j == i:
                    pop_on = f"\\fscx{st.pop}\\fscy{st.pop}" if st.pop != 100 else ""
                    pop_off = "\\fscx100\\fscy100" if st.pop != 100 else ""
                    parts.append(f"{{\\c{st.highlight}&{pop_on}}}{t}{{\\c{st.color}&{pop_off}}}")
                else:
                    parts.append(t)
            lines.append(f"Dialogue: 0,{ts(w.start)},{ts(end)},Default,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(lines) + "\n"


def to_srt(words: list[Word], style: CaptionStyle | None = None, offset: float = 0.0) -> str:
    """Plain SRT export (for platforms that take a captions file)."""
    st = style or CaptionStyle()
    shifted = normalize_words([Word(w.start - offset, w.end - offset, w.text) for w in words], st.max_word)

    def srt_ts(t: float) -> str:
        ms = int(round(max(t, 0) * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out = []
    for n, chunk in enumerate(chunk_words(shifted, st), 1):
        out.append(f"{n}\n{srt_ts(chunk[0].start)} --> {srt_ts(chunk[-1].end)}\n{' '.join(w.text for w in chunk)}\n")
    return "\n".join(out)
