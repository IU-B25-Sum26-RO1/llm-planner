import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SceneObject:
    model_name: str
    classes: tuple[str, ...]
    color: str | None = None
    aliases: tuple[str, ...] = ()


SCENE_OBJECTS = (
    SceneObject(
        model_name="pyramid_cube_1",
        classes=("cube",),
        color="green",
        aliases=(
            "pyramid_cube_1",
            "pyramid cube 1",
            "cube 1",
            "first cube",
            "green cube",
            "зеленый куб",
            "зеленый кубик",
            "первый куб",
            "первый кубик",
        ),
    ),
    SceneObject(
        model_name="pyramid_cube_2",
        classes=("cube",),
        color="blue",
        aliases=(
            "pyramid_cube_2",
            "pyramid cube 2",
            "cube 2",
            "second cube",
            "blue cube",
            "синий куб",
            "синий кубик",
            "второй куб",
            "второй кубик",
        ),
    ),
    SceneObject(
        model_name="pyramid_cube_3",
        classes=("cube",),
        color="red",
        aliases=(
            "pyramid_cube_3",
            "pyramid cube 3",
            "cube 3",
            "third cube",
            "last cube",
            "top cube",
            "red cube",
            "красный куб",
            "красный кубик",
            "третий куб",
            "третий кубик",
            "последний куб",
            "верхний куб",
        ),
    ),
    SceneObject(
        model_name="ball",
        classes=("ball", "sphere"),
        color="white",
        aliases=(
            "ball",
            "sphere",
            "white ball",
            "мяч",
            "шар",
            "белый мяч",
            "белый шар",
        ),
    ),
    SceneObject(
        model_name="ramp",
        classes=("ramp",),
        color="orange",
        aliases=("ramp", "orange ramp", "горка", "рампа", "оранжевая горка"),
    ),
    SceneObject(
        model_name="table",
        classes=("table",),
        color=None,
        aliases=("table", "стол"),
    ),
)


CLASS_SYNONYMS = {
    "cube": {"cube", "box", "куб", "кубик", "коробка"},
    "ball": {"ball", "sphere", "мяч", "шар"},
    "sphere": {"ball", "sphere", "мяч", "шар"},
    "ramp": {"ramp", "горка", "рампа"},
    "table": {"table", "стол"},
}

COLOR_SYNONYMS = {
    "green": {"green", "зеленый", "зеленая", "зеленое", "зеленого"},
    "blue": {"blue", "синий", "синяя", "синее", "синего"},
    "red": {"red", "красный", "красная", "красное", "красного"},
    "white": {"white", "белый", "белая", "белое", "белого"},
    "orange": {"orange", "оранжевый", "оранжевая", "оранжевое", "оранжевого"},
}

SELECTION_TO_CUBE = {
    "first": "pyramid_cube_1",
    "nearest": "pyramid_cube_1",
    "leftmost": "pyramid_cube_1",
    "second": "pyramid_cube_2",
    "rightmost": "pyramid_cube_2",
    "furthest": "pyramid_cube_2",
    "third": "pyramid_cube_3",
    "last": "pyramid_cube_3",
    "topmost": "pyramid_cube_3",
}


def resolve_target_model_name(target: dict | None, fallback: str = "") -> str:
    """Resolve an LLM target object into a concrete Gazebo model name."""
    if not isinstance(target, dict):
        return fallback

    obj = target.get("object")
    if not isinstance(obj, dict):
        return fallback

    prompt = _normalize(obj.get("prompt", ""))
    direct = _resolve_direct_alias(prompt)
    if direct:
        return direct

    requested_class = _canonical_class(obj.get("class"), prompt)
    requested_color = _canonical_color(_attributes(obj).get("color"), prompt)

    candidates = _objects_for_class(requested_class)
    if requested_color:
        color_matches = [item for item in candidates if item.color == requested_color]
        if color_matches:
            candidates = color_matches

    if len(candidates) == 1:
        return candidates[0].model_name

    selected = _resolve_selection(target, candidates)
    if selected:
        return selected

    if candidates:
        return candidates[0].model_name

    return fallback or "_".join(prompt.split())


def _attributes(obj: dict) -> dict:
    attrs = obj.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


def _resolve_direct_alias(prompt: str) -> str | None:
    if not prompt:
        return None
    for item in SCENE_OBJECTS:
        aliases = {_normalize(alias) for alias in item.aliases}
        if prompt == _normalize(item.model_name) or prompt in aliases:
            return item.model_name
    return None


def _objects_for_class(class_name: str | None) -> list[SceneObject]:
    if class_name is None:
        return []
    return [item for item in SCENE_OBJECTS if class_name in item.classes]


def _canonical_class(value: object, prompt: str) -> str | None:
    normalized_value = _normalize(str(value or ""))
    for canonical, synonyms in CLASS_SYNONYMS.items():
        normalized_synonyms = {_normalize(item) for item in synonyms}
        if normalized_value in normalized_synonyms:
            return canonical

    prompt_tokens = set(prompt.split())
    for canonical, synonyms in CLASS_SYNONYMS.items():
        normalized_synonyms = {_normalize(item) for item in synonyms}
        if prompt_tokens & normalized_synonyms:
            return canonical
    return None


def _canonical_color(value: object, prompt: str) -> str | None:
    normalized_value = _normalize(str(value or ""))
    for canonical, synonyms in COLOR_SYNONYMS.items():
        normalized_synonyms = {_normalize(item) for item in synonyms}
        if normalized_value in normalized_synonyms:
            return canonical

    prompt_tokens = set(prompt.split())
    for canonical, synonyms in COLOR_SYNONYMS.items():
        normalized_synonyms = {_normalize(item) for item in synonyms}
        if prompt_tokens & normalized_synonyms:
            return canonical
    return None


def _resolve_selection(target: dict, candidates: list[SceneObject]) -> str | None:
    if not candidates:
        return None

    candidate_names = {item.model_name for item in candidates}
    selection = target.get("selection")
    selection_type = None
    if isinstance(selection, dict):
        selection_type = selection.get("type")
    elif isinstance(selection, str):
        selection_type = selection

    selected = SELECTION_TO_CUBE.get(_normalize(str(selection_type or "")))
    if selected in candidate_names:
        return selected
    return None


def _normalize(value: str) -> str:
    value = value.lower().replace("ё", "е").replace("_", " ")
    value = re.sub(r"[^a-zа-я0-9]+", " ", value)
    return " ".join(value.split())
