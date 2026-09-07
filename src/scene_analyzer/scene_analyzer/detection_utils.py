def select_best_detection(detections: list[dict], min_confidence: float = 0.0) -> dict | None:
    candidates = [
        detection for detection in detections
        if float(detection.get("confidence", 0.0)) >= min_confidence
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: float(item.get("confidence", 0.0)))


def detections_from_yolo_result(result) -> list[dict]:
    detections = []
    names = getattr(result, "names", {}) or {}
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return detections

    for box in boxes:
        xyxy = box.xyxy[0].detach().cpu().numpy().astype(float).tolist()
        cls_id = int(box.cls[0].detach().cpu().item()) if box.cls is not None else -1
        confidence = float(box.conf[0].detach().cpu().item()) if box.conf is not None else 0.0
        detections.append(
            {
                "class": str(names.get(cls_id, cls_id)),
                "class_id": cls_id,
                "confidence": confidence,
                "bbox": xyxy,
            }
        )
    return detections
