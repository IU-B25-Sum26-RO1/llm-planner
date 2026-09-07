import json
import re


COLOR_WORDS = {
    "green": ("green", "зеленый", "зеленая", "зеленое", "зеленого"),
    "blue": ("blue", "синий", "синяя", "синее", "синего"),
    "red": ("red", "красный", "красная", "красное", "красного"),
    "white": ("white", "белый", "белая", "белое", "белого"),
    "orange": ("orange", "оранжевый", "оранжевая", "оранжевое", "оранжевого"),
}

CLASS_WORDS = {
    "cube": ("cube", "box", "куб", "кубик", "коробка"),
    "ball": ("ball", "sphere", "мяч", "шар"),
    "ramp": ("ramp", "горка", "рампа"),
    "table": ("table", "стол"),
}


def parse_target_message(data: str) -> dict | None:
    try:
        target = json.loads(data)
    except json.JSONDecodeError:
        return None
    return target if isinstance(target, dict) else None


def target_prompts(target: dict | None) -> list[str]:
    if not isinstance(target, dict):
        return []

    obj = target.get("object")
    if not isinstance(obj, dict):
        return []

    prompt = _normalize(obj.get("prompt"))
    class_name = _canonical(CLASS_WORDS, obj.get("class"), prompt)
    attrs = obj.get("attributes") if isinstance(obj.get("attributes"), dict) else {}
    color = _canonical(COLOR_WORDS, attrs.get("color"), prompt)

    prompts = []
    if color and class_name:
        prompts.append(f"{color} {class_name}")
    if prompt:
        prompts.append(prompt)
    if class_name:
        prompts.append(class_name)
    if color and class_name == "cube":
        prompts.append(f"{color} box")

    return _unique(prompts)


def target_prompt(target: dict | None) -> str:
    prompts = target_prompts(target)
    return prompts[0] if prompts else ""


def target_color(target: dict | None) -> str | None:
    if not isinstance(target, dict):
        return None

    obj = target.get("object")
    if not isinstance(obj, dict):
        return None

    prompt = _normalize(obj.get("prompt"))
    attrs = obj.get("attributes") if isinstance(obj.get("attributes"), dict) else {}
    return _canonical(COLOR_WORDS, attrs.get("color"), prompt)


def target_class(target: dict | None) -> str | None:
    if not isinstance(target, dict):
        return None

    obj = target.get("object")
    if not isinstance(obj, dict):
        return None

    prompt = _normalize(obj.get("prompt"))
    return _canonical(CLASS_WORDS, obj.get("class"), prompt)


def _canonical(vocabulary: dict[str, tuple[str, ...]], value: object, prompt: str) -> str | None:
    value = _normalize(value)
    for canonical, words in vocabulary.items():
        normalized_words = {_normalize(word) for word in words}
        if value in normalized_words:
            return canonical

    tokens = set(prompt.split())
    for canonical, words in vocabulary.items():
        normalized_words = {_normalize(word) for word in words}
        if tokens & normalized_words:
            return canonical
    return None


def _normalize(value: object) -> str:
    value = str(value or "").lower().replace("ё", "е").replace("_", " ")
    value = re.sub(r"[^a-zа-я0-9]+", " ", value)
    return " ".join(value.split())


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
