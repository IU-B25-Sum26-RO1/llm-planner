"""Deterministic scoring helpers for the decomposer command corpus."""

import json
from pathlib import Path

from decomposer.json_utils import validate_command_dict
from schemas.command_contract import LLM_ACTIONS


EXPECTED_TYPES = frozenset({"command", "non_command"})
_MISSING = object()


def load_cases(path: str | Path) -> list[dict]:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation manifest must be a non-empty JSON list")

    seen_ids = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"Case {index} must be an object")
        required = {"id", "utterance", "expected_type", "expected_actions"}
        missing = required - case.keys()
        if missing:
            raise ValueError(f"Case {index} is missing fields: {sorted(missing)}")
        if not isinstance(case["id"], str) or not case["id"].strip():
            raise ValueError(f"Case {index} has an invalid id")
        if case["id"] in seen_ids:
            raise ValueError(f"Duplicate case id: {case['id']}")
        seen_ids.add(case["id"])
        if not isinstance(case["utterance"], str) or not case["utterance"].strip():
            raise ValueError(f"Case {case['id']} has an empty utterance")
        if case["expected_type"] not in EXPECTED_TYPES:
            raise ValueError(f"Case {case['id']} has an invalid expected_type")
        actions = case["expected_actions"]
        if not isinstance(actions, list) or any(
            action not in LLM_ACTIONS for action in actions
        ):
            raise ValueError(f"Case {case['id']} has invalid expected_actions")
        if case["expected_type"] == "command" and not actions:
            raise ValueError(f"Command case {case['id']} must expect at least one action")
        if case["expected_type"] == "non_command" and actions:
            raise ValueError(f"Non-command case {case['id']} must expect no actions")
        expected_fields = case.get("expected_fields", {})
        if not isinstance(expected_fields, dict) or any(
            not isinstance(path, str) or not path for path in expected_fields
        ):
            raise ValueError(f"Case {case['id']} has invalid expected_fields")
    return cases


def _value_at_path(value, path):
    current = value
    for component in path.split("."):
        if isinstance(current, list):
            if not component.isdigit():
                return _MISSING
            index = int(component)
            if index >= len(current):
                return _MISSING
            current = current[index]
        elif isinstance(current, dict) and component in current:
            current = current[component]
        else:
            return _MISSING
    return current


def score_response(case: dict, response: dict) -> dict:
    """Score only externally observable planner requirements, without fuzzy grading."""
    if not isinstance(response, dict):
        return {
            "schema_valid": False,
            "type_match": False,
            "actions_match": False,
            "passed": False,
            "error": "Response is not a JSON object",
        }
    if "error" in response:
        return {
            "schema_valid": False,
            "type_match": False,
            "actions_match": False,
            "passed": False,
            "error": response["error"],
        }

    try:
        normalized = validate_command_dict(response)
    except ValueError as exc:
        return {
            "schema_valid": False,
            "type_match": False,
            "actions_match": False,
            "passed": False,
            "error": str(exc),
        }

    actual_actions = [task["action"] for task in normalized["tasks"]]
    type_match = normalized["type"] == case["expected_type"]
    actions_match = actual_actions == case["expected_actions"]
    language_match = normalized["language"] == case.get("expected_language", "ru")
    text_match = normalized["text"] == case["utterance"]
    field_mismatches = {}
    for path, expected in case.get("expected_fields", {}).items():
        actual = _value_at_path(normalized, path)
        if actual != expected:
            field_mismatches[path] = {
                "expected": expected,
                "actual": "<missing>" if actual is _MISSING else actual,
            }
    fields_match = not field_mismatches
    return {
        "schema_valid": True,
        "type_match": type_match,
        "actions_match": actions_match,
        "language_match": language_match,
        "text_match": text_match,
        "fields_match": fields_match,
        "passed": (
            type_match
            and actions_match
            and language_match
            and text_match
            and fields_match
        ),
        "actual_type": normalized["type"],
        "actual_actions": actual_actions,
        "field_mismatches": field_mismatches,
    }


def summarize_results(results: list[dict]) -> dict:
    total = len(results)

    def count(key):
        return sum(bool(result["score"].get(key)) for result in results)

    def rate(value):
        return value / total if total else 0.0

    schema_valid = count("schema_valid")
    type_matches = count("type_match")
    action_matches = count("actions_match")
    language_matches = count("language_match")
    text_matches = count("text_match")
    field_matches = count("fields_match")
    passed = count("passed")
    return {
        "total_trials": total,
        "schema_valid": schema_valid,
        "schema_valid_rate": rate(schema_valid),
        "type_matches": type_matches,
        "type_match_rate": rate(type_matches),
        "action_matches": action_matches,
        "action_match_rate": rate(action_matches),
        "language_matches": language_matches,
        "language_match_rate": rate(language_matches),
        "text_matches": text_matches,
        "text_match_rate": rate(text_matches),
        "field_matches": field_matches,
        "field_match_rate": rate(field_matches),
        "passed": passed,
        "exact_pass_rate": rate(passed),
    }
