from scene_analyzer.detection_utils import select_best_detection


def test_select_best_detection_by_confidence():
    detections = [
        {"class": "cube", "confidence": 0.2},
        {"class": "cube", "confidence": 0.8},
        {"class": "cube", "confidence": 0.4},
    ]

    assert select_best_detection(detections, min_confidence=0.15)["confidence"] == 0.8


def test_select_best_detection_returns_none_below_threshold():
    detections = [{"class": "cube", "confidence": 0.2}]

    assert select_best_detection(detections, min_confidence=0.5) is None
