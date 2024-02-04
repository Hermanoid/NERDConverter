"""
    Main Command-line script for the NERD Converter
"""

from collections import OrderedDict
from pathlib import Path
import click

from tools.recipe_preprocessor import preprocess_recipes

steps_dict = OrderedDict([("preprocess", preprocess_recipes)])


@click.command()
@click.option("--data_dir", "-d", type=click.Path(exists=True), default="data")
@click.option("--output_dir", "-o", type=click.Path(), default="output")
@click.option(
    "--step",
    "-s",
    type=click.Choice(list(steps_dict.keys())+["all"], case_sensitive=False),
    multiple=True,
    default=["all"],
)
def cli(data_dir: str, output_dir: str, step: list[str]):
    """Convert recipes to NERD format via a series of steps"""
    print("Welcome to the NERD Converter!")

    data_path = Path(data_dir)
    # If data_path doesn't exist, we've got issues
    if not data_path.exists():
        click.echo(f"Data directory {data_path} not found")
        return
    output_path = Path(output_dir)
    # We can create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    if "all" in step:
        step = list(steps_dict.keys())
    
    for s in step:
        print()
        print(f"Running step: {s}")
        if s not in steps_dict:
            click.echo(f"Step {s} not found")
            return
        if not steps_dict[s](data_path, output_path):
            click.echo(f"Step {s} failed")
            return
    click.echo("All steps completed successfully!")


if __name__ == "__main__":
    cli()
