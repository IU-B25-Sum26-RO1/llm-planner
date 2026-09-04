import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "decomposer"))

from decomposer.evaluation import (  # noqa: E402
    load_cases,
    score_response,
    summarize_results,
)


MANIFEST = ROOT / "evaluation" / "decomposer_commands.json"


def _response(command_type, actions):
    tasks = []
    for action in actions:
        target = None
        placement = None
        if action == "pick":
            target = {
                "object": {
                    "class": "cube",
                    "attributes": {
                        "color": "green",
                        "size": None,
                        "shape": None,
                        "material": None,
                        "state": None,
                    },
                    "prompt": "green cube",
                },
                "search_space": [],
                "selection": None,
            }
        if action == "place":
            placement = {
                "reference": {
                    "object": {
                        "class": "tray",
                        "attributes": {
                            "color": "white",
                            "size": None,
                            "shape": None,
                            "material": None,
                            "state": None,
                        },
                        "prompt": "white tray",
                    },
                    "search_space": [],
                    "selection": None,
                },
                "relation": "on_top_of",
            }
        tasks.append(
            {
                "action": action,
                "target": target,
                "placement": placement,
                "modifiers": None,
                "confidence": 1.0,
            }
        )
    return {
        "type": command_type,
        "language": "ru",
        "tasks": tasks,
        "text": "test",
        "confidence": 1.0,
    }


def test_versioned_manifest_has_at_least_ten_valid_unique_cases():
    cases = load_cases(MANIFEST)

    assert len(cases) >= 10
    assert len({case["id"] for case in cases}) == len(cases)
    assert {"command", "non_command"} == {case["expected_type"] for case in cases}


def test_exact_scoring_accepts_matching_schema_valid_response():
    case = {
        "utterance": "test",
        "expected_type": "command",
        "expected_actions": ["pick", "place"],
        "expected_fields": {
            "tasks.0.target.object.class": "cube",
            "tasks.1.placement.relation": "on_top_of",
        },
    }
    score = score_response(case, _response("command", ["pick", "place"]))

    assert score == {
        "schema_valid": True,
        "type_match": True,
        "actions_match": True,
        "language_match": True,
        "text_match": True,
        "fields_match": True,
        "passed": True,
        "actual_type": "command",
        "actual_actions": ["pick", "place"],
        "field_mismatches": {},
    }


def test_scoring_rejects_action_order_mismatch_and_summarizes_rates():
    case = {
        "utterance": "test",
        "expected_type": "command",
        "expected_actions": ["pick", "place"],
    }
    score = score_response(case, _response("command", ["place", "pick"]))
    summary = summarize_results([{"score": score}])

    assert score["schema_valid"]
    assert not score["actions_match"]
    assert not score["passed"]
    assert summary["schema_valid_rate"] == 1.0
    assert summary["exact_pass_rate"] == 0.0


def test_scoring_reports_semantic_field_mismatch():
    case = {
        "utterance": "test",
        "expected_type": "command",
        "expected_actions": ["pick"],
        "expected_fields": {"tasks.0.target.object.attributes.color": "red"},
    }
    score = score_response(case, _response("command", ["pick"]))

    assert not score["fields_match"]
    assert score["field_mismatches"] == {
        "tasks.0.target.object.attributes.color": {
            "expected": "red",
            "actual": "green",
        }
    }


def test_manifest_is_plain_json_for_external_tools():
    assert isinstance(json.loads(MANIFEST.read_text(encoding="utf-8")), list)
