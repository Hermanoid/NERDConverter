# Pydantic model definitions
from typing import List, Dict, Optional, Union
from pydantic import BaseModel


class Item(BaseModel):
    id: int
    regName: str
    name: str
    displayName: str
    nbt: Optional[dict]


class Fluid(BaseModel):
    fluidName: str
    unlocalizedName: str
    luminosity: int
    density: int
    temperature: int
    viscosity: int
    isGaseous: bool
    rarity: str
    id: int


class GTFluid(Fluid):
    colorRGBA: List[int]
    localizedName: str
    fluidState: str


class RecipeStacks(BaseModel):
    items: Dict[str, Item]
    fluids: Dict[str, Union[Fluid, GTFluid]]


class MinimalItem(BaseModel):
    itemSlug: str
    count: int
    NBT: Optional[dict] = None

    def __hash__(self):
        return hash(self.itemSlug + str(self.count) + str(self.NBT))


class MinimalFluid(BaseModel):
    fluidSlug: str
    amount: int
    NBT: Optional[dict] = None

    def __hash__(self):
        return hash(self.fluidSlug + str(self.amount) + str(self.NBT))


# An item can be: a minimal item, minimal fluid (for FluidDisplays), or str
ItemSlot = Union[MinimalItem, MinimalFluid, str]
FluidSlot = MinimalFluid


class GenericRecipe(BaseModel):
    ingredients: List[ItemSlot]
    otherStacks: List[ItemSlot]
    outItem: Optional[ItemSlot] = None


class GregtechRecipe(BaseModel):
    # All items here should be nullable because some items are left as null to leave a space in the UI
    # Example: Cooking stuff (e.g. iron) in the primitive blast furnace.
    # It's (I think) safe to ignore them
    mInputs: List[Optional[ItemSlot]]
    mOutputs: List[Optional[ItemSlot]]
    mFluidInputs: List[Optional[FluidSlot]]
    mFluidOutputs: List[Optional[FluidSlot]]
    mChances: List[int]
    mDuration: int
    mEUt: int
    mSpecialValue: int
    mEnabled: bool
    mHidden: bool
    mFakeRecipe: bool
    mCanBeBuffered: bool
    mNeedsEmptyOutput: bool
    isNBTSensitive: bool
    metadataStorage: dict


class DumpedRecipe(BaseModel):
    generic: Optional[GenericRecipe] = None
    greg_data: Optional[GregtechRecipe] = None


class HandlerDump(BaseModel):
    recipes: List[DumpedRecipe]
    id: str
    name: str
    tab_name: str


class QueryDump(BaseModel):
    handlers: List[HandlerDump]
    query_item: ItemSlot


class DumpFile(BaseModel):
    version: str
    queries: List[QueryDump]
