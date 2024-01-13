import argparse
import pprint
import sys
from pathlib import Path

import httpx
import platformdirs
from rich import print
from rich.prompt import IntPrompt

from kamuidrone.cache import ModCache
from kamuidrone.modrinth.client import ModrinthApi
from kamuidrone.modrinth.utils import resolve_dependency_versions, resolve_latest_version
from kamuidrone.pack import LocalPack, load_local_pack


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


def main() -> int:
    """
    Main entrypoint.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pack-dir",
        help="The directory to use (defaults to CWD)",
        default=Path.cwd(),
        type=Path,
    )
    parser.add_argument(
        "--cache-dir",
        help="The cache directory to use (defaults to ~/.cache)",
        default=Path(platformdirs.user_cache_dir("kamuidrone")),
        type=Path,
    )

    subcommands = parser.add_subparsers(
        title="Subcommands",
        description="Pack management actions",
        dest="subcommand",
        required=True,
    )

    add_mod = subcommands.add_parser("add", help="Adds a new mod")
    add_group = add_mod.add_mutually_exclusive_group(required=True)
    add_group.add_argument(
        "-s", "--search", help="Adds a mod by searching for the specified argument", default=None
    )
    add_group.add_argument(
        "-p", "--project-id", help="Adds a mod using the specified project ID", default=None
    )
    add_group.add_argument(
        "-V", "--version-id", help="Adds a mod using the specified version ID", default=None
    )

    args = parser.parse_args()
    cache_dir: Path = args.cache_dir
    cache = ModCache(cache_dir=cache_dir)

    pack = load_local_pack(args.pack_dir)

    subcommand: str = args.subcommand

    with httpx.Client() as client:
        api = ModrinthApi(client)

        if subcommand == "add":
            search_query: str | None = args.search
            if search_query is not None:
                return add_mod_by_searching(pack, api, cache, search_query)

            project_id: str | None = args.project_id

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.HTTPStatusError as e:
        pprint.pprint(e.response.json())
