import json
import re
from typing import Any

from pydantic import ValidationError

from schemas.output_cmd import OutputCommandSchema


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_json_text(raw: str) -> str:
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
    candidate = extract_json_text(raw)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")

    return parsed


def validate_command_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize an LLM response at the system boundary."""
    if "error" in data:
        raise ValueError("LLM response contains an error field")

    try:
        command = OutputCommandSchema.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON violates command schema: {exc}") from exc

    return command.model_dump(by_alias=True)


def is_valid_command_dict(data: dict[str, Any]) -> bool:
    try:
        validate_command_dict(data)
    except ValueError:
        return False
    return True
