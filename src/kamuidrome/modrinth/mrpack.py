# fun fucking fact: modrinth changed from using the relatively clean (albeit, still evil) gitbook
# to a fucking SUPPORT WEBSITE TEMPLATE for their *technical* documentation. what the fuck is
# wrong with them?
# luckily, the internet archive does not forget, so here's a nice direct link to the fullwidth
# page: https://web.archive.org/web/20231009172349/https://docs.modrinth.com/modpacks/format
#
# the documentation itself is pretty poor, so here's some Unofficial Documentation that
# is a bit easier to read.
#
# ``modpack.mrpack`` files are zip files with a bunch of metadata stuffed inside.
# the actual folders and such inside the zip are simply unpacked into the ``.minecraft`` directory.
# there's a bunch of metadata stored within the ``modrinth.index.json`` (which seemingly isn't
# minified?) which contains basic information about the pack and externally downloaded mods.
#
# in their seemingly infinite wisdom, modrinth decided the mod references within would use
# URLs to modrintn's CDN. rather than using version IDs. because the format is fucking insanely
# generic for no reason.

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import httpx
import more_itertools

from kamuidrome.meta import AvailablePackLoader
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.pack import LocalPack


def _parse_forge_version(
    body: list[dict[str, Any]],
    game_version: str,
) -> str:
    """
    Gets the latest Forge version from Prism's metadata.
    """

    for entry in body:
        version = entry["version"]
        requires = entry["requires"]

        for i in requires:
            if i["uid"] == "net.minecraft" and i["equals"] == game_version:
                return version

    raise ValueError("Couldn't find a valid legacyforge version!")


def select_latest_loader_version(
    client: httpx.Client, game_version: str, loader: AvailablePackLoader
) -> str:
    """
    Gets the latest version for the specified modloader.
    """

    match loader:
        case AvailablePackLoader.FABRIC:
            result = client.get("https://meta.fabricmc.net/v2/versions/loader")
            result.raise_for_status()
            body: list[dict[str, Any]] = result.json()

            return more_itertools.first(filter(lambda it: it["stable"] is True, body))["version"]

        case AvailablePackLoader.QUILT:
            result = client.get("https://meta.quiltmc.org/v3/versions/loader")
            result.raise_for_status()
            body: list[dict[str, Any]] = result.json()

            return body[0]["version"]

        case AvailablePackLoader.LEGACY_FORGE:
            result = client.get("https://meta.prismlauncher.org/v1/net.minecraftforge")
            result.raise_for_status()
            return _parse_forge_version(result.json(), game_version)

        case AvailablePackLoader.NEOFORGE:
            result = client.get("https://meta.prismlauncher.org/v1/net.neoforged")
            result.raise_for_status()
            return _parse_forge_version(result.json(), game_version)


# https://stackoverflow.com/a/69375880/15026456
def make_archive(source: Path, destination: Path) -> None:
    """
    Creates a new archive from the given directory.
    """

    base_name = destination.parent / destination.stem
    shutil.make_archive(
        str(base_name),
        "zip",
        root_dir=str(source),
    )


def create_mrpack(
    pack: LocalPack,
    api: ModrinthApi,
    output: Path,
) -> Path:
    """
    Creates a new ``mrpack`` file from the given pack.
    """

    # initially i tried writing directly to the zipfilee, but python ``zipfile`` is an evil module
    # that sucks (i miss java.nio).
    # so instead we just make a temporary directory and use ``shutil.make_archive``.

    with tempfile.TemporaryDirectory() as dir:
        tmpdir_path = Path(dir)

        versions = api.get_multiple_versions([m.version_id for m in pack.mods.values()])
        files = [version.primary_file for version in versions]

        loader_version = pack.metadata.loader.version
        if loader_version is None:
            loader_version = select_latest_loader_version(
                api.client,
                pack.metadata.game_version,
                pack.metadata.loader.type,
            )

        files_struct: list[dict[str, Any]] = []
        index = {
            "formatVersion": 1,
            "game": "minecraft",
            "versionId": pack.metadata.version,
            "dependencies": {
                "minecraft": pack.metadata.game_version,
                pack.metadata.loader.mrpack_name: loader_version,
            },
            "files": files_struct,
        }

        # versions in this case means the indexed mods.
        for version_file in files:
            body = {
                "path": f"mods/{version_file.filename}",
                "hashes": version_file.hashes,
                "downloads": [version_file.url],
                "fileSize": version_file.size,
            }
            files_struct.append(body)

        with (tmpdir_path / "modrinth.index.json").open(mode="w") as f:
            json.dump(index, f)

        directories = ["config", "mods", *pack.metadata.include_directories]

        for to_copy_dir in directories:
            real_dir = (pack.directory / to_copy_dir).resolve()
            shutil.copytree(real_dir, tmpdir_path / to_copy_dir)

        actual_file = output.with_suffix(".zip")
        make_archive(tmpdir_path, output)
        actual_file.rename(output)

    return output
