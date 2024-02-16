from rich.progress import Progress

from kamuidrome.cache import ModCache
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.modrinth.models import ProjectId
from kamuidrome.modrinth.utils import (
    VersionResult,
    resolve_dependency_versions,
    resolve_latest_version,
)
from kamuidrome.pack import LocalPack


def download_all_mods(
    pack: LocalPack,
    modrinth: ModrinthApi,
    cache: ModCache,
) -> int:
    """
    Downloads all mods in the index for a specified pack.
    """

    projects = {p.id: p for p in modrinth.get_multiple_projects(list(pack.mods.keys()))}
    versions = modrinth.get_multiple_versions([v.version_id for v in pack.mods.values()])
    all_versions: VersionResult = []

    for ver in versions:
        all_versions.append((projects[ver.project_id], ver))

    pack.download_and_add_mods(modrinth, cache, all_versions, selected_mod=None)

    return 0


def update_all_mods(
    pack: LocalPack,
    modrinth: ModrinthApi,
    cache: ModCache,
) -> int:
    """
    Updates all mods in the index for a specified pack.
    """

    all_versions: VersionResult = []
    deps_seen: set[ProjectId] = set()

    with Progress() as progress:
        task = progress.add_task("Fetching mod info", total=len(pack.mods))

        projects = modrinth.get_multiple_projects(list(pack.mods.keys()))

        for mod in projects:
            latest_version = resolve_latest_version(pack.metadata, modrinth, mod)
            all_versions.append((mod, latest_version))
            all_versions += resolve_dependency_versions(
                pack.metadata, modrinth, latest_version, _seen=deps_seen
            )
            progress.advance(task, 1)

    # de-duplicate downloads
    seen: set[ProjectId] = set()
    to_download: VersionResult = []

    for info, version in all_versions:
        if info.id in seen:
            continue

        seen.add(info.id)

        to_download.append((info, version))

    pack.download_and_add_mods(modrinth, cache, to_download, selected_mod=None)

    return 0
