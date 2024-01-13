import enum
import json
from pathlib import Path

import attr
import cattrs
from rich.progress import Progress
from tomlkit import load as toml_load

from kamuidrone.cache import ModCache
from kamuidrone.meta import PackMetadata
from kamuidrone.modrinth.client import ModrinthApi
from kamuidrone.modrinth.models import ProjectId
from kamuidrone.modrinth.utils import VersionResult


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
    project_id: str = attr.ib()

    #: The pretty, human-readable version for this mod.
    version: str = attr.ib()

    #: The installed version of this mod.
    version_id: str = attr.ib()

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
        mods: dict[str, InstalledMod],
    ) -> None:
        self.directory = pack_dir
        self.metadata = metadata
        self.mods = mods

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
                # exists_already = cache.get_real_filename(version.project_id, version.id) is None
                # if exists_already:
                #    continue
                selected_file = version.primary_file
                current_task = progress.add_task(
                    f"[green]Downloading[/green] [white]{version.name}[/white]",
                    total=selected_file.size,
                )

                with api.get_file(selected_file.url) as resp:
                    for chunk in cache.save_mod_from_response(
                        resp, version.project_id, version.id, selected_file.filename
                    ):
                        progress.update(current_task, advance=chunk)

                self.mods[project.id] = InstalledMod(
                    name=project.title,
                    project_id=version.project_id,
                    version=version.version_number,
                    version_id=version.id,
                    checksum=cache.get_file_checksum(version.project_id, version.id),
                    selected=selected_mod == version.project_id,
                )

                progress.update(all_mods, advance=1)

        self._write_index()


def load_local_pack(directory: Path) -> LocalPack:
    """
    Loads a :class:`.LocalPack` from the specified directory.
    """

    pack_meta_path = directory / "pack.toml"
    with pack_meta_path.open() as f:
        raw_data = toml_load(f)
        pack_meta = cattrs.structure(raw_data, PackMetadata)

    try:
        mods_index_path = directory / "mods-index.json"
        with mods_index_path.open() as f:
            raw_selected = json.load(f)
            selected_mods = cattrs.structure(raw_selected, dict[str, InstalledMod])
    except FileNotFoundError:
        selected_mods: dict[str, InstalledMod] = {}

    return LocalPack(directory, pack_meta, selected_mods)
