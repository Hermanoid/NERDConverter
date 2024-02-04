from pathlib import Path
import pandas as pd
from tools.config_format import Config, IngredientListFilter, RecipeFilter
from tools.dump_format import RecipeStacks
from tools.nerd_format import Recipe, RecipeFile, Stack

from tools.util import (
    HANDLERS_FILENAME,
    OREDICT_FILENAME,
    RECIPES_FILTERED_FILENAME,
    RECIPES_PREPROCESSED_FILENAME,
    STACKS_FILENAME,
    check_cache_up_to_date,
    get_hash,
    load_config,
    parse_json,
)


def prepare_item_df(stacks: RecipeStacks, oredict: pd.DataFrame):
    item_df = pd.DataFrame.from_records(
        [(k, v.name) for k, v in stacks.items.items()],
        columns=["slug", "name"],
        index="slug",
    )
    # Some items have the damage included in ".damage" notation, which doesn't match with the oredict (and is also inconsistent)
    # Let's remove it
    halves = item_df["name"].str.rsplit(".", n=1, expand=True)
    item_df["name"][halves[1].notna() & halves[1].str.isnumeric()] = halves[0]
    # Add 1x for stack notation
    item_df["stack"] = "1x" + item_df["name"]

    # Wildcard items are ones where damage actually means damage, and not a different item
    # Match them with the items with damage values removed
    wildcard_oredict = oredict[oredict["Wildcard"]]
    wildcard_oredict.index = wildcard_oredict.index.str.rsplit(
        "@", n=1, expand=True
    ).get_level_values(0)
    item_df = item_df.merge(
        wildcard_oredict["Ore Name"], left_on="stack", right_index=True, how="left"
    )

    # For non-wildcard cases, we must add the damage to the stack using @ notation
    item_df["stack"] = (
        item_df["stack"]
        + "@"
        + item_df.index.str.split("d", n=1, expand=True).get_level_values(1)
    )
    item_df = item_df.merge(
        oredict["Ore Name"],
        left_on="stack",
        right_index=True,
        how="left",
        suffixes=("_wild", "_normal"),
    )

    combined_orenames = item_df["Ore Name_normal"].fillna(item_df["Ore Name_wild"])
    item_df["Ore Name"] = combined_orenames
    item_df.drop(columns=["Ore Name_normal", "Ore Name_wild"], inplace=True)

    # Fluids aren't in the oredict, so we'll just use the fluidName
    # item_df.loc[list(stacks.fluids.keys()), "Ore Name"] = [
    #     f.fluidName for f in stacks.fluids.values()
    # ]

    # item_df.loc[list(stacks.fluids.keys())] = [{"Ore Name": f.fluidName} for f in stacks.fluids.values()]

    item_df.add(
        pd.DataFrame.from_records(
            ((f.fluidName,) for f in stacks.fluids.values()),
            index=stacks.fluids.keys(),
            columns=["Ore Name"],
        )
    )

    return item_df


def get_allowed_machines(config: Config, handlers: pd.DataFrame):
    return set(
        handlers[
            (
                (
                    handlers["Overlay Identifier"].apply(
                        lambda x: x in config.filter.handler_names
                    )
                )
                | (
                    handlers["Mod DisplayName"].apply(
                        lambda x: x in config.filter.handler_mods
                    )
                )
            )
            & ~(
                handlers["Overlay Identifier"].apply(
                    lambda x: x in config.filter.exclude_handler_names
                )
            )
        ]["Handler Recipe Name"]
    )


def prepare_matches(config: Config, item_df: pd.DataFrame):
    # Precompute oredict matches for every item
    exclude_recipe_filters = config.filter.exclude_recipes
    slug_to_oredict = item_df["Ore Name"]
    all_filters = set()
    for f in exclude_recipe_filters:
        if f.inputs:
            all_filters.update(f.inputs.oredict)
        if f.outputs:
            all_filters.update(f.outputs.oredict)
    slug_matches = pd.DataFrame(
        index=item_df.index, columns=list(all_filters), dtype=bool
    )

    for filter_regex in all_filters:
        slug_matches[filter_regex] = slug_to_oredict.str.fullmatch(
            filter_regex, case=True
        )

    return slug_matches


missing_slugs_counter = 0


def matches_ingredient_list_filter(
    ingredients: list[Stack], filter: IngredientListFilter, slug_matches: pd.DataFrame
):
    slugs = [i.slug for i in ingredients]
    try:
        matches = slug_matches.loc[slugs]
        if filter.kind == "all_match_any":
            return matches[filter.oredict].any(axis=1).all()
        elif filter.kind == "any_match_any":
            return matches[filter.oredict].any().any()
        elif filter.kind == "exactly_match":
            return (matches[filter.oredict].sum(axis=0) == filter.num_matches).all()
        else:
            raise ValueError("Invalid filter kind")
    except KeyError:
        global missing_slugs_counter
        missing_slugs_counter += 1
        return False


def matches_recipe_filter(
    recipe: Recipe, filter: RecipeFilter, slug_matches: pd.DataFrame
):
    if filter.machines and recipe.machine not in filter.machines:
        return False
    if filter.inputs and not matches_ingredient_list_filter(
        recipe.inputs, filter.inputs, slug_matches
    ):
        return False
    if filter.outputs and not matches_ingredient_list_filter(
        recipe.outputs, filter.outputs, slug_matches
    ):
        return False
    return True


def filter_recipes(data_dir: Path, output_dir: Path) -> bool:
    input_file = data_dir / RECIPES_PREPROCESSED_FILENAME
    stacks_file = data_dir / STACKS_FILENAME
    handlers_file = data_dir / HANDLERS_FILENAME
    oredict_file = data_dir / OREDICT_FILENAME
    output_file = data_dir / RECIPES_FILTERED_FILENAME

    for file in [input_file, stacks_file, handlers_file, oredict_file]:
        if not file.exists():
            print(f"Required input {file} does not exist, cannot filter recipes")
            return False

    sha = get_hash(input_file)
    if check_cache_up_to_date(output_file, sha):
        return True

    print("Loading preprocessed recipes, stacks, config, handlers, and oredict...")
    recipes = parse_json(input_file, RecipeFile, encoding="cp1252")
    stacks = parse_json(stacks_file, RecipeStacks)
    config = load_config()
    handlers = pd.read_csv(handlers_file)
    oredict = pd.read_csv(oredict_file, index_col="ItemStack")

    print("Preparing item data and oredict lookups...")
    item_df = prepare_item_df(stacks, oredict)
    slug_matches = prepare_matches(config, item_df)

    print("Filtering recipes...")
    allowed_machines = get_allowed_machines(config, handlers)
    exclude_recipe_filters = config.filter.exclude_recipes

    def passes_filter(recipe: Recipe):
        return (recipe.machine in allowed_machines) and not any(
            matches_recipe_filter(recipe, filter, slug_matches)
            for filter in exclude_recipe_filters
        )

    counter = 0
    total = len(recipes.recipes)
    filtered_recipes = []
    for recipe in recipes.recipes:
        if counter % 100 == 0:
            print(f"Filtering recipe {counter}/{total}", end="\r")
        counter += 1
        if passes_filter(recipe):
            filtered_recipes.append(recipe)
    print()

    with open(output_file, "w") as f:
        f.write(
            RecipeFile(
                dump_version=recipes.dump_version,
                dump_sha=recipes.dump_sha,
                recipes=filtered_recipes,
            ).model_dump_json()
        )
    return True
