from collections.abc import Iterable

from rich import box, print
from rich.table import Table
from rich.text import Text

from kamuidrome.pack import InstalledMod, LocalPack


def _apply_table(table: Table, mods: Iterable[InstalledMod]) -> None:
    table.add_column("Name", justify="left")
    table.add_column("Version", justify="center")
    table.add_column("Pinned", justify="right")

    for mod in mods:
        pinned = "No" if not mod.pinned else "Yes"
        pinned_style = "yellow" if not mod.pinned else "green"
        table.add_row(
            Text(mod.name, style="magenta", justify="left"),
            mod.version,
            Text(pinned, justify="right", style=pinned_style),
        )

    print(table)


def list_indexed_mods(pack: LocalPack, include_deps: bool = True) -> int:
    """
    Lists the indexed mods for the current pack.
    """

    if include_deps:
        dependencies = [mod for mod in pack.mods.values() if not mod.selected]
        dep_table = Table(
            title="[italic]Dependency mods[/italic] (not explicitly selected)",
            box=box.SIMPLE,
            min_width=50,
        )
        _apply_table(dep_table, dependencies)
        print()

    selected = [mod for mod in pack.mods.values() if mod.selected]
    selected_table = Table(title="Selected mods", box=box.SIMPLE, min_width=50)
    _apply_table(selected_table, selected)

    return 0
