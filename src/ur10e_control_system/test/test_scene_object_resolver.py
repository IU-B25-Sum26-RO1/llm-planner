from ur10e_control_system.scene_object_resolver import resolve_target_model_name


def target(prompt, class_name="cube", color=None, selection=None):
    return {
        "object": {
            "class": class_name,
            "attributes": {
                "color": color,
                "size": None,
                "shape": None,
                "material": None,
                "state": None,
            },
            "prompt": prompt,
        },
        "search_space": [],
        "selection": selection,
    }


def test_resolves_english_color_attribute():
    assert resolve_target_model_name(target("green cube", color="green")) == "pyramid_cube_1"


def test_resolves_russian_prompt_color():
    assert resolve_target_model_name(target("зеленый куб", color=None)) == "pyramid_cube_1"


def test_resolves_existing_model_prompt():
    assert resolve_target_model_name(target("pyramid cube 2", color=None)) == "pyramid_cube_2"


def test_resolves_selection_when_color_is_missing():
    assert (
        resolve_target_model_name(target("cube", color=None, selection={"type": "topmost"}))
        == "pyramid_cube_3"
    )


def test_falls_back_to_slug_for_unknown_object():
    unknown = target("yellow cylinder", class_name="cylinder", color="yellow")
    assert resolve_target_model_name(unknown, fallback="yellow_cylinder") == "yellow_cylinder"
