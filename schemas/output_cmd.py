import json

from pydantic import BaseModel, Field

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, TypeAdapter


SUPPORTED_CMD_TYPES = Literal["command", "non_command"]
SUPPORTED_LANGUAGES = Literal["ru", "en"]
SUPPORTED_ACTIONS = Literal[
    "pick_object",
    "place_object",
    "move_to",
    "find_object",
    "inspect_object",
    "follow_object",
    "open_gripper",
    "close_gripper",
    "rotate_object",
    "push_object",
    "pull_object",
    "press_button",
    "go_home",
    "stop",
    "cancel",
    "unknown",
]
SUPPORTED_RELATIONS = Literal[
    "left_of",
    "right_of",
    "behind",
    "in_front_of",
    "inside",
    "outside",
    "on_top_of",
    "under",
    "near",
    "next_to",
]
SUPPORTED_SELECTION_TYPES = Literal[
    "nearest",
    "furthest",
    "largest",
    "smallest",
    "leftmost",
    "rightmost",
    "topmost",
    "bottommost",
    "first",
    "last",
    "any",
    "same",
    "null",
]

class ObjectAttributes(BaseModel):
    color: Optional[str] = Field(default=None, description="Object color")
    size: Optional[str] = Field(default=None, description="Object size")
    shape: Optional[str] = Field(default=None, description="Object shape")
    material: Optional[str] = Field(default=None, description="Object material")
    state: Optional[str] = Field(default=None, description="Object state")


class ObjectSchema(BaseModel):
    object_class: str = Field(..., alias="class", description="Object class or type. Normalized object name. Canonical English singular noun.")
    attributes: ObjectAttributes
    prompt: str = Field(..., description="SAM3 Search Prompt")


class SearchSpaceItem(BaseModel):
    relation: SUPPORTED_RELATIONS = Field(..., description="A spatial relationship, for example, 'left_of'")
    reference: ObjectSchema


class SelectionSchema(BaseModel):
    selection_type: SUPPORTED_SELECTION_TYPES = Field(..., alias="type", description="Selection specifies which instance of an object should be chosen when multiple matching objects exist.")


class TargetSchema(BaseModel):
    object: ObjectSchema
    search_space: List[SearchSpaceItem] = Field(default_factory=list)
    selection: Optional[SelectionSchema] = Field(default=None)


class TaskModifiers(BaseModel):
    speed: Optional[str] = None
    precision: Optional[str] = None


class PlacementSchema(BaseModel):
    reference: TargetSchema
    relation: SUPPORTED_RELATIONS


class TaskSchema(BaseModel):
    action: SUPPORTED_ACTIONS = Field(..., description="Action type (from supported actions)")
    target: Optional[TargetSchema] = Field(default=None)
    placement: Optional[PlacementSchema] = Field(default=None)
    modifiers: Optional[TaskModifiers] = Field(default=None)
    confidence: float = Field(..., ge=0.0, le=1.0)


class OutputCommandSchema(BaseModel):
    type: SUPPORTED_CMD_TYPES
    language: SUPPORTED_LANGUAGES = "ru"
    tasks: List[TaskSchema] = Field(default_factory=list)
    text: str = Field(..., description="Original command text")
    confidence: float = Field(..., ge=0.0, le=1.0)


PlacementSchema.model_rebuild()
TaskSchema.model_rebuild()


if __name__ == "__main__":
    adapter = TypeAdapter(OutputCommandSchema)
    flat = adapter.json_schema(mode="serialization")

    print(json.dumps(flat, ensure_ascii=False, indent='\t'))
    # print(json.dumps(OutputCommandSchema.model_json_schema(), ensure_ascii=False, indent='\t'))