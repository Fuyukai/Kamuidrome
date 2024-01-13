from rich import print
from rich.prompt import IntPrompt

from kamuidrone.cache import ModCache
from kamuidrone.modrinth.client import ModrinthApi
from kamuidrone.modrinth.utils import resolve_dependency_versions, resolve_latest_version
from kamuidrone.pack import LocalPack


def add_mod_by_searching(pack: LocalPack, client: ModrinthApi, cache: ModCache, query: str) -> int:
    """
    Adds a new mod by searching Modrinth.
    """

    result = client.get_projects_via_search(
        query,
        f"game_versions:{pack.metadata.game_version}",
        pack.metadata.loader.modrinth_facets,
        "project_type:mod",
        limit=10,
    )

    if not result:
        print("[red]error:[/red] no results found")
        return 1

    matched = result[0]
    if matched.title.lower() == query.lower() or len(result) == 1:
        print(f"[green]successful match[/green]: {matched.title} / {matched.id}")

    else:
        print("[yellow]No exact match found[/yellow], listing possible options")

        for idx, option in enumerate(result):
            print(rf"[white]\[{idx}][/white] - {option.title}")

        option = IntPrompt.ask(
            prompt="Pick an option", show_choices=False, choices=list(map(str, range(len(result))))
        )

        matched = result[option]

    project_info = client.get_project_info(matched.id)
    version = resolve_latest_version(pack.metadata, client, project_info)
    all_versions = [version, *resolve_dependency_versions(pack.metadata, client, version)]
    pack.download_and_add_mods(client, cache, all_versions, selected_mod=project_info.id)

    return 0
