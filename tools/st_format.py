from typing import Dict, List, Literal, Optional
from pydantic import BaseModel


class RecipeItem(BaseModel):
    item: str
    amount: float


class Recipe(BaseModel):
    slug: str
    name: str
    className: str
    alternate: bool
    time: int
    manualTimeMultiplier: float
    ingredients: List[RecipeItem]
    forBuilding: bool
    inMachine: bool
    inHand: bool
    inWorkshop: bool
    products: List[RecipeItem]
    producedIn: List[str]
    isVariablePower: bool
    minPower: Optional[int] = None
    maxPower: Optional[int] = None


class Color(BaseModel):
    r: int
    g: int
    b: int
    a: int


class Item(BaseModel):
    slug: str
    className: str
    name: str
    sinkPoints: int | None
    description: str
    stackSize: int
    energyValue: float
    radioactiveDecay: float
    liquid: bool
    fluidColor: Color


# leave schematics, generators, and miners unparsed
Schematic = Dict
Generator = Dict
Miner = Dict


class Resource(BaseModel):
    item: str
    pingColor: Color
    speed: float


class BuildingMetadata(BaseModel):
    powerConsumption: int | None
    powerConsumptionExponent: Optional[float] = None
    manufacturingSpeed: Optional[float] = None


class VariableBuildingMetadata(BuildingMetadata):
    isVariablePower: Literal[True]
    minPowerConsumption: int
    maxPowerConsumption: int


class StorageBuildingMetadata(BuildingMetadata):
    storageCapacity: int


class BeamMetadata(BaseModel):
    maxLength: int


class PipelineMetadata(BaseModel):
    flowLimit: float


class ConveyorMetadata(BaseModel):
    beltSpeed: int
    firstPieceCostMultiplier: float
    lengthPerCost: float
    maxLength: int


class Empty(BaseModel):
    ...

    class Config:
        extra = "forbid"


class Building(BaseModel):
    slug: str
    name: str
    className: str
    description: str
    metadata: (
        Empty
        | BuildingMetadata
        | VariableBuildingMetadata
        | StorageBuildingMetadata
        | BeamMetadata
        | PipelineMetadata
        | ConveyorMetadata
    )
    size: Dict  # Leave unparsed


class STDataFile(BaseModel):
    items: Dict[str, Item]
    recipes: Dict[str, Recipe]
    resources: Dict[str, Resource]
    buildings: Dict[str, Building]
    schematics: Dict[str, Schematic]
    generators: Dict[str, Generator]
    miners: Dict[str, Miner]
