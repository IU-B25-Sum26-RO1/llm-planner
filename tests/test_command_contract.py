import sys
from pathlib import Path
from typing import get_args

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "decomposer"))

from decomposer.json_utils import validate_command_dict  # noqa: E402
from schemas.command_contract import LLM_ACTIONS  # noqa: E402
from schemas.output_cmd import SUPPORTED_ACTIONS  # noqa: E402


def _object(prompt="green cube"):
    return {
        "class": "cube",
        "attributes": {
            "color": "green",
            "size": None,
            "shape": None,
            "material": None,
            "state": None,
        },
        "prompt": prompt,
    }


def _target(prompt="green cube"):
    return {"object": _object(prompt), "search_space": [], "selection": None}


def _command(task):
    return {
        "type": "command",
        "language": "ru",
        "tasks": [task],
        "text": "test",
        "confidence": 0.9,
    }


def test_valid_pick_is_normalized_for_ros_publication():
    command = validate_command_dict(
        _command(
            {
                "action": "pick",
                "target": _target(),
                "placement": None,
                "modifiers": None,
                "confidence": 0.9,
            }
        )
    )

    assert command["tasks"][0]["action"] == "pick"
    assert command["tasks"][0]["target"]["object"]["class"] == "cube"


@pytest.mark.parametrize(
    "task",
    [
        {"action": "press_button", "confidence": 0.9},
        {"action": "move_to", "confidence": 0.9},
        {"action": "pick", "target": None, "confidence": 0.9},
        {"action": "place", "target": None, "placement": None, "confidence": 0.9},
    ],
)
def test_unsafe_or_incomplete_tasks_are_rejected(task):
    with pytest.raises(ValueError):
        validate_command_dict(_command(task))


def test_non_command_cannot_carry_tasks():
    with pytest.raises(ValueError):
        validate_command_dict(
            {
                "type": "non_command",
                "language": "ru",
                "tasks": [{"action": "stop", "confidence": 1.0}],
                "text": "thanks",
                "confidence": 1.0,
            }
        )


def test_unknown_fields_are_rejected():
    task = {
        "action": "go_home",
        "target": None,
        "placement": None,
        "modifiers": None,
        "confidence": 1.0,
        "untrusted_coordinate": [0, 0, 0],
    }
    with pytest.raises(ValueError):
        validate_command_dict(_command(task))


def test_schema_action_literal_matches_canonical_contract():
    assert frozenset(get_args(SUPPORTED_ACTIONS)) == LLM_ACTIONS


def test_task_modifiers_are_restricted_to_supported_values():
    valid = {
        "action": "go_home",
        "target": None,
        "placement": None,
        "modifiers": {"speed": "slow", "precision": "high"},
        "confidence": 1.0,
    }
    assert validate_command_dict(_command(valid))["tasks"][0]["modifiers"] == {
        "speed": "slow",
        "precision": "high",
    }

    invalid = {**valid, "modifiers": {"speed": "maximum", "precision": "high"}}
    with pytest.raises(ValueError):
        validate_command_dict(_command(invalid))
