# Target Format
from typing import List, Optional, Literal
from pydantic import BaseModel


class Stack(BaseModel):
    type: Literal["item", "fluid"]
    slug: str
    amount: int | float  # Count (items) or amount (fluids). Can be partial in the case of chances

    @property
    def comboslug(self):
        return self.type + self.slug

    # Fricking awesome decorator
    # Obviously assumes you won't go changing recipe data around after loading (shouldn't be an issue?)
    # @cached_property
    def __hash__(self):
        # Intentionally do not hash amount so we can combine items with different amounts later
        return hash((self.type, self.slug))


class GregMeta(BaseModel):
    EUt: int
    ticks: int


class Recipe(BaseModel):
    inputs: List[Stack]
    outputs: List[Stack]
    machine: str  # aka crafing method/handler, includes e.g. Asemblers but also e.g. Shaped Crafting, etc.
    meta: Optional[GregMeta] = None

    # @cached_property
    def __hash__(self):
        # Intentionally leaving out meta stuff
        # TODO: Do recipes with same inputs/outputs but different processing times exist? If so, is it just overclocking (same recipe?)
        return hash((tuple(self.inputs), tuple(self.outputs), self.machine))


class RecipeFile(BaseModel):
    dump_version: str
    dump_sha: str
    recipes: List[Recipe]
