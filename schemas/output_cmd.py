import json
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from schemas.command_contract import (
    PLACEMENT_REQUIRED_ACTIONS,
    TARGET_REQUIRED_ACTIONS,
)


SUPPORTED_CMD_TYPES = Literal["command", "non_command"]
SUPPORTED_LANGUAGES = Literal["ru", "en"]
SUPPORTED_ACTIONS = Literal[
    "pick",
    "place",
    "open_gripper",
    "close_gripper",
    "go_home",
    "stop",
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
    model_config = ConfigDict(extra="forbid")

    color: Optional[str] = Field(default=None, description="Object color")
    size: Optional[str] = Field(default=None, description="Object size")
    shape: Optional[str] = Field(default=None, description="Object shape")
    material: Optional[str] = Field(default=None, description="Object material")
    state: Optional[str] = Field(default=None, description="Object state")


class ObjectSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    object_class: str = Field(..., alias="class", description="Object class or type. Normalized object name. Canonical English singular noun.")
    attributes: ObjectAttributes
    prompt: str = Field(..., description="SAM3 Search Prompt")


class SearchSpaceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: SUPPORTED_RELATIONS = Field(..., description="A spatial relationship, for example, 'left_of'")
    reference: ObjectSchema


class SelectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    selection_type: SUPPORTED_SELECTION_TYPES = Field(..., alias="type", description="Selection specifies which instance of an object should be chosen when multiple matching objects exist.")


class TargetSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object: ObjectSchema
    search_space: List[SearchSpaceItem] = Field(default_factory=list)
    selection: Optional[SelectionSchema] = Field(default=None)


class TaskModifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speed: Optional[Literal["slow", "normal", "fast"]] = None
    precision: Optional[Literal["low", "normal", "high"]] = None


class PlacementSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: TargetSchema
    relation: SUPPORTED_RELATIONS


class TaskSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: SUPPORTED_ACTIONS = Field(..., description="Action type (from supported actions)")
    target: Optional[TargetSchema] = Field(default=None)
    placement: Optional[PlacementSchema] = Field(default=None)
    modifiers: Optional[TaskModifiers] = Field(default=None)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_required_references(self):
        if self.action in TARGET_REQUIRED_ACTIONS and self.target is None:
            raise ValueError(f"{self.action} requires target")
        if self.action in PLACEMENT_REQUIRED_ACTIONS and self.placement is None:
            raise ValueError(f"{self.action} requires placement")
        return self


class OutputCommandSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: SUPPORTED_CMD_TYPES
    language: SUPPORTED_LANGUAGES = "ru"
    tasks: List[TaskSchema] = Field(default_factory=list)
    text: str = Field(..., description="Original command text")
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_command_tasks(self):
        if self.type == "non_command" and self.tasks:
            raise ValueError("non_command must not contain tasks")
        if self.type == "command" and not self.tasks:
            raise ValueError("command requires at least one task")
        return self


PlacementSchema.model_rebuild()
TaskSchema.model_rebuild()


if __name__ == "__main__":
    adapter = TypeAdapter(OutputCommandSchema)
    flat = adapter.json_schema(mode="serialization")

    print(json.dumps(flat, ensure_ascii=False, indent='\t'))
