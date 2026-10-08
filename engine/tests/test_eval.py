from clipfarm_engine.eval import iou, precision_recall, wer


def test_wer():
    assert wer("c'est vraiment incroyable", "c'est vraiment incroyable") == 0
    assert abs(wer("il a trop de chance", "il a pas de chance") - 0.2) < 1e-9
    assert wer("", "") == 0


def test_precision_recall():
    truth = [(100, 140), (500, 530)]
    pred = [(105, 145), (300, 330), (498, 528)]
    p, r = precision_recall(pred, truth, k=5)
    assert abs(p - 2 / 3) < 1e-9 and r == 1.0


def test_iou():
    assert iou([0, 0, 1, 1], [0, 0, 1, 1]) == 1
    assert iou([0, 0, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]) == 0
