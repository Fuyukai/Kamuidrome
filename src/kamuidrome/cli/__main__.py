import argparse
import pprint
import sys
from pathlib import Path

import httpx
import platformdirs

from kamuidrome.cache import ModCache
from kamuidrome.cli.add import add_mod_by_searching
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.pack import load_local_pack


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

    deploy_group = subcommands.add_parser("deploy", help="Deploys a modpack")
    deploy_group.add_argument("INSTANCE", help="The name of the Prism instance to write to")

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
        
        elif subcommand == "deploy":
            return pack.deploy_modpack(cache, args.INSTANCE)

    return 0


if __name__ == "__main__":

    def _run():
        try:
            sys.exit(main())
        except httpx.HTTPStatusError as e:
            pprint.pprint(e.response.json())

    _run()
