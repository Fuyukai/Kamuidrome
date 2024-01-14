import enum
import json
import shutil
from pathlib import Path
from typing import cast

import attr
import cattrs
from rich import print
from rich.progress import Progress
from tomlkit import load as toml_load

from kamuidrome.cache import ModCache
from kamuidrome.meta import PackMetadata
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.modrinth.models import ProjectId, VersionId
from kamuidrome.modrinth.utils import VersionResult
from kamuidrome.prism import (
    cleanup_from_index,
    find_minecraft_dir,
    get_prism_instances_directory,
)


class ModSide(enum.Enum):
    """
    Enumeration of the possible sides a mod can be on.
    """

    CLIENT = "client"
    SERVER = "server"
    BOTH = "both"


@attr.s(slots=True, kw_only=True, frozen=False)
class InstalledMod:
    """
    Wraps data about a single installed mod.
    """

    #: The name of this mod.
    name: str = attr.ib()

    #: The actual Modrinth ID for this mod.
    project_id: ProjectId = attr.ib()

    #: The pretty, human-readable version for this mod.
    version: str = attr.ib()

    #: The installed version of this mod.
    version_id: VersionId = attr.ib()

    #: The Blake2b hash for this mod. Used as the filename in the cache.
    checksum: str = attr.ib()

    #: If this mod was added explicitly or not (i.e. as a dependency).
    selected: bool = attr.ib()

    #: If this mod is pinned (i.e. won't be automatically updated).
    pinned: bool = attr.ib(default=False)


class LocalPack:
    """
    A single, local modpack.
    """

    def __init__(
        self,
        pack_dir: Path,
        metadata: PackMetadata,
        mods: dict[ProjectId, InstalledMod],
    ) -> None:
        self.directory: Path = pack_dir
        self.metadata: PackMetadata = metadata
        self.mods: dict[ProjectId, InstalledMod] = mods

    def _write_index(self):
        """
        Writes out the mod index for this pack.
        """

        mod_index = self.directory / "mods" / "mod-index.json"
        serialised = cattrs.unstructure(self.mods)

        with mod_index.open(mode="w") as f:
            json.dump(serialised, f, indent=4)

    def download_and_add_mods(
        self,
        api: ModrinthApi,
        cache: ModCache,
        versions: VersionResult,
        selected_mod: ProjectId,
    ) -> None:
        """
        Downloads all of the provided mods and adds them to this pack's index.
        """

        # selected_mod is used for setting InstalledMod's explicit selection parameter.

        with Progress() as progress:
            all_mods = progress.add_task("[green]Downloading mods...", total=len(versions))

            for project, version in versions:
                old_metadata = self.mods.get(project.id)
                if (
                    old_metadata is not None
                    and old_metadata.pinned
                    and old_metadata.version_id != version.id
                ):
                    print(
                        f"[yellow]skipping[/yellow] "
                        f"[bold white]{project.title}[/bold white] as it is pinned"
                    )
                    progress.update(all_mods, advance=1)
                    continue
                exists_already = cache.get_real_filename(version.project_id, version.id) is not None
                if exists_already:
                    print(
                        f"[yellow]skipping[/yellow] "
                        f"[bold white]{project.title}[/bold white] download as it exists already"
                    )
                else:
                    selected_file = version.primary_file
                    current_task = progress.add_task(
                        f"[green]Downloading[/green] "
                        f"[white]{project.title} {version.version_number}[/white]",
                        total=selected_file.size,
                    )

                    with api.get_file(selected_file.url) as resp:
                        for chunk in cache.save_mod_from_response(
                            resp, version.project_id, version.id, selected_file.filename
                        ):
                            progress.update(current_task, advance=chunk)

                    progress.update(current_task, completed=True)

                self.mods[project.id] = InstalledMod(
                    name=project.title,
                    project_id=version.project_id,
                    version=version.version_number,
                    version_id=version.id,
                    checksum=cast(str, cache.get_file_checksum(version.project_id, version.id)),
                    selected=selected_mod == version.project_id,
                )

                progress.update(all_mods, advance=1)

        self._write_index()

    def _validate_downloaded_mods(self, cache: ModCache) -> bool:
        """
        Validates downloaded mods to check if they all exist.
        """

        any_error = False

        for project_id, mod in self.mods.items():
            path = cache.get_mod_path(project_id, mod.version_id)
            if not path.exists():
                print(
                    f"[red]missing mod:[/red] "
                    f"[white]{mod.name}[/white] ([white]{mod.version}[/white])"
                )
                any_error = True

        return not any_error

    def _setup_instance_firsttime(
        self,
        instance_path: Path,
    ) -> None:
        """
        Sets up an instance for the first time.
        """

        mods_dir = instance_path / "mods"
        shutil.rmtree(mods_dir, ignore_errors=True)
        mods_dir.mkdir(exist_ok=False, parents=False)

        configs_dir = instance_path / "config"
        shutil.rmtree(configs_dir, ignore_errors=True)

        # path traversal! oh no!
        for dir in self.metadata.include_directories:
            shutil.rmtree(instance_path / dir, ignore_errors=True)

    def deploy_modpack(
        self,
        cache: ModCache,
        instance_name: str,
    ) -> int:
        """
        Deploys a modpack to the specified Prism Launcher instance.
        """

        if not self._validate_downloaded_mods(cache):
            print("[red]unable to validate downloaded mods.[/red] try 'kamuidrome download' first.")
            return 1

        prism_dir = get_prism_instances_directory()
        instance_dir = find_minecraft_dir(prism_dir, instance_name)
        instance_dir = instance_dir.resolve()

        index_path = instance_dir / "kamuidrome.json"

        # step 1: make sure there's no stale symlinks around
        if not index_path.exists():
            print("[yellow]no index found[/yellow], cleaning up instance files")
            self._setup_instance_firsttime(instance_dir)
        else:
            print("[yellow]cleaning up symlinks from index...[/yellow]")
            cleanup_from_index(instance_dir, index_path)

        symlink_index: list[str] = []

        def symlink(symlink_file: Path, original: Path, is_dir: bool) -> None:
            symlink_file.symlink_to(original, target_is_directory=is_dir)
            symlink_index.append(str(symlink_file))

        # step 2: symlink the custom directories
        our_base_dir = self.directory.resolve()
        include_directories = ["config", *self.metadata.include_directories]

        for directory in include_directories:
            potential_dir = our_base_dir / directory
            if not potential_dir.exists():
                print(f"[yellow]skipping dir[/yellow] [white]{potential_dir}[/white] (not found)")
                continue

            instance_symlink = instance_dir / directory

            symlink(instance_symlink, potential_dir, is_dir=True)

            print(f"[green]linked included dir[/green] [white]{instance_symlink}[/white]")

        # step 3: symlink found mod jar files
        instance_mods_dir = instance_dir / "mods"
        for file in instance_mods_dir.iterdir():
            if file.suffix != ".jar":
                continue

            mod_symlink = instance_mods_dir / file.name

            symlink(mod_symlink, file, is_dir=False)

            print(f"[green]linked included mod[/green] [white]{mod_symlink}[/white]")

        # step 4: symlink mods from cache
        for mod in self.mods.values():
            actual_file_location = cache.get_mod_path(mod.project_id, mod.version_id)
            actual_file_name = cache.get_real_filename(mod.project_id, mod.version_id)
            assert actual_file_name, "don't fuck about with me!"

            instance_mod_path = instance_mods_dir / actual_file_name
            symlink(instance_mod_path, actual_file_location.resolve(), is_dir=False)

            print(f"[green]linked managed mod[/green] [white]{instance_mod_path}[/white]")

        with index_path.open(mode="w") as f:
            json.dump(symlink_index, f)

        return 0


def load_local_pack(directory: Path) -> LocalPack:
    """
    Loads a :class:`.LocalPack` from the specified directory.
    """

    pack_meta_path = directory / "pack.toml"
    with pack_meta_path.open() as f:
        raw_data = toml_load(f)
        pack_meta = cattrs.structure(raw_data, PackMetadata)

    try:
        mods_index_path = directory / "mods" / "mod-index.json"
        with mods_index_path.open() as f:
            raw_selected = json.load(f)
            selected_mods = cattrs.structure(raw_selected, dict[ProjectId, InstalledMod])
    except FileNotFoundError:
        selected_mods: dict[ProjectId, InstalledMod] = {}

    return LocalPack(directory, pack_meta, selected_mods)
