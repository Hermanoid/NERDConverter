from pathlib import Path
import itertools
from typing import Sequence, Tuple, List, Optional
import hashlib
import json_stream
import json_stream.base

from tools.dump_format import MinimalItem, MinimalFluid, ItemSlot, QueryDump
from tools.nerd_format import RecipeFile, Stack, Recipe, GregMeta

RECIPES_INPUT_FILENAME = "recipes.json"
RECIPES_PREPROCESSED_FILENAME = "recipes_preprocessed.json"


def stackify(itemSlot: ItemSlot) -> Stack:
    if isinstance(itemSlot, str):
        return Stack(type="item", slug=itemSlot, amount=1)
    elif isinstance(itemSlot, MinimalItem):
        return Stack(type="item", slug=itemSlot.itemSlug, amount=itemSlot.count)
    elif isinstance(itemSlot, MinimalFluid):
        return Stack(type="fluid", slug=itemSlot.fluidSlug, amount=itemSlot.amount)
    else:
        raise ValueError(f"Invalid itemSlot: {itemSlot} ({type(itemSlot)})")


def groupify(stacks: Sequence[Stack]) -> List[Stack]:
    groups = itertools.groupby(stacks, lambda stack: (stack.type, stack.slug))
    return [
        Stack(type=type, slug=slug, amount=sum(s.amount for s in stack_group))
        for (type, slug), stack_group in groups
    ]


def stackngroup(itemSlots: Sequence[Optional[ItemSlot]]):
    """
    Takes a list of itemSlots and returns a list of stacks, combining stacks with the same type and slug.
    This function throws away specific crafing recipes (e.g. (plank, plank, plank, plank) -> 1 crafting table)
    in favor of a more compact, Satisfactory Tools-compatible format (e.g. 4 planks -> 1 crafting table)
    """
    stacks = [stackify(i) for i in itemSlots if i]
    return groupify(stacks)


def get_hash(file: Path) -> str:
    with open(file, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def preprocess_recipes(data_dir: Path, output_dir: Path) -> bool:
    input_file = data_dir / RECIPES_INPUT_FILENAME
    output_file = data_dir / RECIPES_PREPROCESSED_FILENAME

    sha = get_hash(input_file)
    if output_file.exists():
        print(
            f"Preprocessed recipe file found at {output_file}, checking if it's up to date"
        )
        # Check if the file is up to date
        with open(output_file, "r") as f:
            file = json_stream.load(f)
            if (
                isinstance(file, json_stream.base.TransientStreamingJSONObject)
                and file["dump_sha"] == sha
            ):
                print("Preprocessed recipe file is up to date!")
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
                        outputs = stackngroup(
                            recipe.greg_data.mOutputs + recipe.greg_data.mFluidOutputs
                        )
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
