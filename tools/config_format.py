from typing import Dict, List, Literal
from pydantic import BaseModel


class IngredientAnyFilter(BaseModel):
    kind: Literal["any_match_any", "all_match_any"]
    oredict: List[str]


class IngredientExactFilter(IngredientAnyFilter):
    kind: Literal["exactly_match"]
    # Quantity is number of matches, *not* amount/stack size
    num_matches: List[int]


IngredientListFilter = IngredientAnyFilter | IngredientExactFilter


class RecipeFilter(BaseModel):
    machines: List[str] | None
    inputs: IngredientListFilter | None
    outputs: IngredientListFilter | None


class FilterConfig(BaseModel):
    handler_names: List[str]
    handler_mods: List[str]
    exclude_handler_names: List[str]
    exclude_recipes: List[RecipeFilter]


class Config(BaseModel):
    filter: FilterConfig
