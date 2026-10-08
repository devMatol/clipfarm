"""Quality metrics against a hand-annotated "golden" set (see docs/04-plan-de-test.md).

python -m clipfarm_engine.eval tests/golden/<nom>.json data/projects/<id>

Golden file format:
{
  "source": "chemin ou lien",
  "moments": [{"start": 545, "end": 585, "why": "reaction au braquage"}],
  "transcript_ref": [{"start": 550.0, "end": 556.0, "text": "texte exact entendu"}],
  "cam": [0.739, 0.083, 0.246, 0.245]
}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def overlap_ratio(a: tuple[float, float], b: tuple[float, float]) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    return inter / max(1e-6, min(a[1] - a[0], b[1] - b[0]))


def precision_recall(pred: list[tuple[float, float]], truth: list[tuple[float, float]], k: int = 5, thr: float = 0.5) -> tuple[float, float]:
    """precision@k: share of the top-k clips that hit a human moment; recall: share of moments found."""
    top = pred[:k]
    if not top or not truth:
        return 0.0, 0.0
    hits = sum(1 for p in top if any(overlap_ratio(p, t) >= thr for t in truth))
    found = sum(1 for t in truth if any(overlap_ratio(p, t) >= thr for p in pred))
    return hits / len(top), found / len(truth)


def _norm(text: str) -> list[str]:
    return re.sub(r"[^\w' ]", " ", text.lower()).split()


def wer(ref: str, hyp: str) -> float:
    r, h = _norm(ref), _norm(hyp)
    if not r:
        return 0.0 if not h else 1.0
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / len(r)


def iou(a: list[float], b: list[float]) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    inter = max(0.0, min(ax2, bx2) - max(a[0], b[0])) * max(0.0, min(ay2, by2) - max(a[1], b[1]))
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union else 0.0


def evaluate(golden_path: Path, project_dir: Path) -> dict:
    g = json.loads(golden_path.read_text(encoding="utf-8"))
    report: dict = {}
    hl = project_dir / "highlights.json"
    if hl.exists() and g.get("moments"):
        pred = [(c["start"], c["end"]) for c in json.loads(hl.read_text(encoding="utf-8"))]
        truth = [(m["start"], m["end"]) for m in g["moments"]]
        report["precision@5"], report["recall"] = precision_recall(pred, truth)
    wp = project_dir / "words.json"
    if wp.exists() and g.get("transcript_ref"):
        words = json.loads(wp.read_text(encoding="utf-8"))
        scores = []
        for ref in g["transcript_ref"]:
            hyp = " ".join(w["text"] for w in words if w["start"] >= ref["start"] - 0.5 and w["end"] <= ref["end"] + 0.5)
            scores.append(wer(ref["text"], hyp))
        report["wer"] = sum(scores) / len(scores)
    cam = project_dir / "cam.json"
    if cam.exists() and g.get("cam"):
        cam_data = json.loads(cam.read_text(encoding="utf-8"))
        cam_box = cam_data.get("cam") if isinstance(cam_data, dict) else cam_data
        if cam_box:
            report["cam_iou"] = iou(cam_box, g["cam"])
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(Path(sys.argv[1]), Path(sys.argv[2])), indent=1))
