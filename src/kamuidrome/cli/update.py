from rich.progress import Progress

from kamuidrome.cache import ModCache
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.modrinth.models import ProjectId
from kamuidrome.modrinth.utils import (
    resolve_dependency_versions,
    resolve_latest_version,
)
from kamuidrome.pack import DownloadJob, LocalPack


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
    jobs: list[DownloadJob] = []

    for ver in versions:
        stored_info = pack.mods[ver.project_id]
        jobs.append(
            DownloadJob(
                project_info=projects[ver.project_id],
                version=ver,
                ignore_dependencies=stored_info.ignore_dependencies,
            )
        )

    pack.download_and_add_mods(modrinth, cache, jobs, selected_mod=None)

    return 0


def update_all_mods(
    pack: LocalPack,
    modrinth: ModrinthApi,
    cache: ModCache,
    with_changed_dependencies: bool,
) -> int:
    """
    Updates all mods in the index for a specified pack.
    """

    jobs: list[DownloadJob] = []
    deps_seen: set[ProjectId] = set()

    with Progress() as progress:
        task = progress.add_task("Fetching mod info", total=len(pack.mods))

        projects = modrinth.get_multiple_projects(list(pack.mods.keys()))

        for mod in projects:
            latest_version = resolve_latest_version(pack.metadata, modrinth, mod)
            jobs.append(DownloadJob.include_prev_metadata(mod, latest_version, pack.mods[mod.id]))
            progress.advance(task, 1)

            if with_changed_dependencies and not pack.mods[mod.id].ignore_dependencies:
                # most of the time, the dependencies *don't* change, so make sure to rewrite back
                # the old metadata too.
                for dep_name, dep_ver in resolve_dependency_versions(
                    pack.metadata, modrinth, latest_version, _seen=deps_seen
                ):
                    existing = pack.mods.get(dep_ver.project_id)

                    if existing is None:
                        jobs.append(DownloadJob(project_info=dep_name, version=dep_ver))
                    else:
                        jobs.append(DownloadJob.include_prev_metadata(dep_name, dep_ver, existing))

    # de-duplicate downloads
    seen: set[ProjectId] = set()
    to_download: list[DownloadJob] = []

    for job in jobs:
        if job.project_info.id in seen:
            continue

        seen.add(job.project_info.id)
        to_download.append(job)

    if __debug__:
        for job in jobs:
            assert job.project_info.id == job.version.project_id, (
                f"{job.project_info.title} has non-matching version {job.version.id}"
            )

    pack.download_and_add_mods(modrinth, cache, to_download, selected_mod=None)
    return 0
