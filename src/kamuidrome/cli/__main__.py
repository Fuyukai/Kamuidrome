import argparse
import contextlib
import pprint
import sys
from pathlib import Path

import cattrs
import httpx
import platformdirs
import tomlkit

from kamuidrome.cache import ModCache
from kamuidrome.cli.add import add_mod_by_project_id, add_mod_by_searching, add_mod_by_version_id
from kamuidrome.cli.init import interactively_create_pack
from kamuidrome.cli.list import list_indexed_mods
from kamuidrome.cli.update import download_all_mods, update_all_mods
from kamuidrome.meta import LocalMetadata
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.modrinth.models import ProjectId, VersionId
from kamuidrome.modrinth.mrpack import create_mrpack
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

    init_group = subcommands.add_parser("init", help="Initialise a new modpack interactively")
    init_group.add_argument(
        "--git", help="Create a Git repository and .gitignore", action="store_true", default=False
    )

    add_mod = subcommands.add_parser("add", help="Adds a new mod")
    add_mod.add_argument(
        "--always-select",
        help="Always shows a selection prompt for search",
        action="store_true",
        default=False,
    )
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
    deploy_group_args = deploy_group.add_mutually_exclusive_group(required=False)
    deploy_group_args.add_argument(
        "-i", "--instance", help="The name of the Prism instance to deploy to", default=None
    )
    deploy_group_args.add_argument(
        "-d", "--directory", help="The path of the directory to deploy to", default=None, type=Path
    )

    pin_group = subcommands.add_parser(name="pin", help="Pins a mod version to the current version")
    pin_group.add_argument("MOD", nargs="+", help="The mod name or ID to pin")

    subcommands.add_parser(name="list", help="List indexed mods")

    subcommands.add_parser(name="download", help="Downloads all mods in the index")
    subcommands.add_parser(name="update", help="Updates all mods and dependenciess in the index")

    export_group = subcommands.add_parser("export", help="Exports pack as an mrpack file")
    export_group.add_argument(
        "FILENAME", help="The name of the file or directory to write", nargs="?", default=None
    )
    export_group.add_argument(
        "--ci-mode",
        action="store_true",
        default=False,
        help="Outputs an unpacked mrpack instead of a fully packed one",
    )
    export_group.add_argument(
        "--server-only", action="store_true", default=False, help="Only outputs server-side mods"
    )

    args = parser.parse_args()
    cache_dir: Path = args.cache_dir
    cache = ModCache(cache_dir=cache_dir)

    subcommand: str = args.subcommand

    if subcommand == "init":
        return interactively_create_pack(args.pack_dir, with_git=args.git)

    pack = load_local_pack(args.pack_dir)

    with httpx.Client() as client:
        api = ModrinthApi(client)

        if subcommand == "add":
            search_query: str | None = args.search
            if search_query is not None:
                return add_mod_by_searching(pack, api, cache, search_query, args.always_select)

            project_id: str | None = args.project_id
            if project_id is not None:
                return add_mod_by_project_id(pack, api, cache, ProjectId(project_id))

            version_id: str = args.version_id
            add_mod_by_version_id(pack, api, cache, VersionId(version_id))

        elif subcommand == "deploy":
            instance_name: str | None = args.instance
            folder_name: Path | None = args.directory

            local_metadata: LocalMetadata | None = None

            with contextlib.suppress(FileNotFoundError, KeyError):
                localpack = pack.directory / "localpack.toml"
                data = tomlkit.loads(localpack.read_text())
                local_metadata = cattrs.structure(data, LocalMetadata)

            if folder_name is not None:
                return pack.deploy_to_directory(cache, folder_name, local_metadata)

            if instance_name is None:
                if local_metadata is None:
                    parser.error(
                        "expected either a folder name, an instance name, "
                        "or for the instance name to be set in localpack.toml"
                    )

                instance_name = local_metadata.instance_name

            return pack.deploy_to_instance(cache, instance_name, local_metadata)

        elif subcommand == "pin":
            return pack.pin(" ".join(args.MOD))

        elif subcommand == "download":
            return download_all_mods(pack, api, cache)

        elif subcommand == "update":
            return update_all_mods(pack, api, cache)

        elif subcommand == "list":
            return list_indexed_mods(pack)

        elif subcommand == "export":
            export_name: str | None = args.FILENAME
            ci_mode: bool = args.ci_mode
            server_only: bool = args.server_only

            if export_name is None:
                if ci_mode:
                    parser.error("must provide a directory name in ci mode")
                else:
                    export_path = (Path.cwd() / pack.metadata.name).with_suffix(".mrpack")
            elif not ci_mode:
                export_path = Path(export_name).with_suffix(".mrpack")
            else:
                export_path = Path(export_name)
                export_path.mkdir(exist_ok=True, parents=True)

            create_mrpack(pack, api, export_path, ci_mode=ci_mode, server_only=server_only)
            return 0

    return 0


if __name__ == "__main__":

    def _run():
        try:
            sys.exit(main())
        except httpx.HTTPStatusError as e:
            pprint.pprint(e.response.json())

    _run()
