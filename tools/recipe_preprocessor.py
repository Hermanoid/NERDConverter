from pathlib import Path
from typing import Sequence, Tuple, Optional
import json_stream
import json_stream.base

from tools.dump_format import MinimalItem, MinimalFluid, ItemSlot, QueryDump
from tools.nerd_format import RecipeFile, Stack, Recipe, GregMeta
from tools.util import (
    RECIPES_PREPROCESSED_FILENAME,
    RECIPES_INPUT_FILENAME,
    check_cache_up_to_date,
    get_hash,
)


def intify(amount: float):
    if amount.is_integer():
        return int(amount)
    return amount


def stackify(itemSlot: ItemSlot, chance: float = 10000) -> Stack:
    mult = chance / 10000
    if isinstance(itemSlot, str):
        return Stack(type="item", slug=itemSlot, amount=intify(1 * mult))
    elif isinstance(itemSlot, MinimalItem):
        return Stack(
            type="item", slug=itemSlot.itemSlug, amount=intify(itemSlot.count * mult)
        )
    elif isinstance(itemSlot, MinimalFluid):
        return Stack(
            type="fluid", slug=itemSlot.fluidSlug, amount=intify(itemSlot.amount * mult)
        )
    else:
        raise ValueError(f"Invalid itemSlot: {itemSlot} ({type(itemSlot)})")


def groupify(stacks: list[Stack]) -> list[Stack]:
    if len(stacks) == 1:  # Optimization
        return stacks
    groups = {}
    for i in stacks:
        key = (i.type, i.slug)
        groups[key] = groups.get(key, 0) + i.amount
    return [Stack(type=type, slug=slug, amount=v) for (type, slug), v in groups.items()]


def stackngroup(itemSlots: Sequence[Optional[ItemSlot]]):
    """
    Takes a list of itemSlots and returns a list of stacks, combining stacks with the same type and slug.
    This function throws away specific crafing recipes (e.g. (plank, plank, plank, plank) -> 1 crafting table)
    in favor of a more compact, Satisfactory Tools-compatible format (e.g. 4 planks -> 1 crafting table)
    """
    stacks = [stackify(i) for i in itemSlots if i]
    return groupify(stacks)


def stackngroup_chances(
    itemSlots: Sequence[Optional[ItemSlot]], chances: Optional[Sequence[float]]
):
    if not chances:
        return stackngroup(itemSlots)
    stacks = [stackify(i, chance) for i, chance in zip(itemSlots, chances) if i]
    return groupify(stacks)


def preprocess_recipes(data_dir: Path, output_dir: Path) -> bool:
    input_file = data_dir / RECIPES_INPUT_FILENAME
    output_file = data_dir / RECIPES_PREPROCESSED_FILENAME

    sha = get_hash(input_file)
    if check_cache_up_to_date(output_file, sha):
        return True

    print("Loading recipes...")
    final_recipes_set = set()
    # Generic recipes must be built up before committing to the final recipes se
    # because there can be a separate recipe for each output
    generic_recipes: dict[tuple[Tuple, str], list] = {}
    counter = 0
    version = "unknown"
    with input_file.open("rb") as f:
        recipes_file = json_stream.load(f)
        assert isinstance(recipes_file, json_stream.base.TransientStreamingJSONObject)
        version = recipes_file["version"]
        print("Recipe dumper version:", version)

        for query_json in recipes_file["queries"].persistent():
            # Loading an entire query at once is fine because it's a fairly small amount of data
            query_loaded = json_stream.to_standard_types(query_json)
            assert isinstance(query_loaded, dict)
            query = QueryDump(**query_loaded)
            for handler in query.handlers:
                for recipe in handler.recipes:
                    assert (
                        recipe.generic or recipe.greg_data
                    ), "Recipe has neither generic nor greg_data"
                    if counter % 100 == 0:
                        print(f"Processing recipe {counter}", end="\r")
                    counter += 1
                    inputs = []
                    outputs = []
                    if recipe.generic:
                        # For generic recipes, the otherStacks field is *usually* something like fuel or catalysts that are not consumed
                        # This is a big assumption that is not always true.
                        # However, if the recipe has no output, it's probably a handler that lists outputs in the otherStacks field
                        # This is also a big assumption that is not always true.
                        outputs = (
                            [stackify(recipe.generic.outItem)]
                            if recipe.generic.outItem
                            else stackngroup(recipe.generic.otherStacks)
                        )

                        # Accumulate overlapping ingredients+handlers -> Multiple outputs
                        # This assumes there are no duplicates of recipes that list outputs as otherStacks
                        key = (tuple(recipe.generic.ingredients), handler.tab_name)
                        generic_recipes[key] = generic_recipes.get(key, []) + outputs
                    elif recipe.greg_data:
                        inputs = stackngroup(
                            recipe.greg_data.mInputs + recipe.greg_data.mFluidInputs
                        )
                        outputs = stackngroup_chances(
                            recipe.greg_data.mOutputs, recipe.greg_data.mChances
                        ) + stackngroup(recipe.greg_data.mFluidOutputs)
                        meta = GregMeta(
                            EUt=recipe.greg_data.mEUt, ticks=recipe.greg_data.mDuration
                        )
                        # Greg recipes can be added directly as each copy of a recipe will be the same
                        final_recipes_set.add(
                            Recipe(
                                inputs=inputs,
                                outputs=outputs,
                                machine=handler.tab_name,
                                meta=meta,
                            )
                        )

    print()
    print("Dumping generic recipes...")
    # Add generic recipes to final_recipes_set
    final_recipes_set.update(
        Recipe(inputs=stackngroup(k[0]), outputs=groupify(v), machine=k[1])
        for k, v in generic_recipes.items()
    )
    print(f"Writing {len(final_recipes_set)} preprocessed recipes to output file...")
    with open(output_file, "w") as f:
        f.write(
            RecipeFile(
                dump_version=version,
                dump_sha=sha,
                recipes=list(final_recipes_set),
            ).model_dump_json()
        )
    return True
