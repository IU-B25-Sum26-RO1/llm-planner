from scene_analyzer.target_utils import (
    parse_target_message,
    target_class,
    target_color,
    target_prompt,
    target_prompts,
)


def test_extracts_prompt_and_semantic_classes():
    target = {
        "object": {
            "class": "cube",
            "attributes": {"color": "green"},
            "prompt": "green cube",
        }
    }

    assert target_prompt(target) == "green cube"
    assert target_prompts(target) == ["green cube", "cube", "green box"]


def test_extracts_russian_prompt_into_english_class_prompt():
    target = {
        "object": {
            "class": "кубик",
            "attributes": {"color": "зеленый"},
            "prompt": "зеленый кубик",
        }
    }

    assert target_prompts(target) == ["green cube", "зеленый кубик", "cube", "green box"]
    assert target_color(target) == "green"
    assert target_class(target) == "cube"


def test_parse_target_message_rejects_invalid_json():
    assert parse_target_message("{") is None
