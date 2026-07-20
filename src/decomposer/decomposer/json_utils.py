import json
import re
from typing import Any


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_json_text(raw: str) -> str:
    """Extract a JSON object string from raw LLM output."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("Empty LLM response")

    block_match = _JSON_BLOCK_RE.search(text)
    if block_match:
        return block_match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse JSON from LLM output, tolerating markdown fences and extra prose."""
    candidate = extract_json_text(raw)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")

    return parsed


def is_valid_command_dict(data: dict[str, Any]) -> bool:
    """Minimal structural check before downstream processing."""
    if "error" in data:
        return False

    cmd_type = data.get("type")
    if cmd_type not in ("command", "non_command"):
        return False

    if "tasks" not in data or not isinstance(data["tasks"], list):
        return False

    if cmd_type == "non_command":
        return True

    for task in data["tasks"]:
        if not isinstance(task, dict) or "action" not in task:
            return False

    return True
