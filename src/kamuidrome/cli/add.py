import httpx
from rich import print
from rich.prompt import IntPrompt

from kamuidrome.cache import ModCache
from kamuidrome.meta import AvailablePackLoader
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.modrinth.models import ProjectId, ProjectInfoMixin, VersionId
from kamuidrome.modrinth.utils import (
    FABRIC_API_VERSION,
    resolve_dependency_versions,
    resolve_latest_version,
)
from kamuidrome.pack import LocalPack


def _common_from_project_id(
    pack: LocalPack,
    client: ModrinthApi,
    cache: ModCache,
    project_id: ProjectId | ProjectInfoMixin,
) -> int:
    """
    Common code for any path that uses a project ID.
    """

    if isinstance(project_id, ProjectInfoMixin):
        project_info = project_id
    else:
        project_info = client.get_project_info(project_id)

    if (
        pack.metadata.loader.type
        in (AvailablePackLoader.LEGACY_FORGE, AvailablePackLoader.NEOFORGE)
        and project_id == FABRIC_API_VERSION
    ):
        print("[red]error:[/red] cowardly refusing to install Fabric API on a forge instance")
        return 1

    version = resolve_latest_version(pack.metadata, client, project_info)
    all_versions = [
        (project_info, version),
        *resolve_dependency_versions(pack.metadata, client, version),
    ]
    pack.download_and_add_mods(client, cache, all_versions, selected_mod=project_info.id)

    return 0


def add_mod_by_searching(
    pack: LocalPack,
    client: ModrinthApi,
    cache: ModCache,
    query: str,
    always_prompt_selection: bool,
) -> int:
    """
    Adds a new mod by searching Modrinth.

    If ``always_prompt_selection`` is passed, then the regular name will be ignored. Useful for
    CLI search.
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

    # written weirdly to simplify reading the logic rather than trying to unfuck an all().
    if len(result) == 1:
        should_auto_match = True

    elif always_prompt_selection:
        should_auto_match = False

    elif matched.title.lower() == query.lower():
        should_auto_match = True

    else:
        should_auto_match = False

    if not should_auto_match:
        print("[yellow]No exact match found[/yellow], listing possible options")

        for idx, option in enumerate(result):
            print(rf"[white]\[{idx}][/white] - [bold white]{option.title}[/bold white]")

        option = IntPrompt.ask(
            prompt="Pick an option", show_choices=False, choices=list(map(str, range(len(result))))
        )

        matched = result[option]
    else:
        print(f"[green]successful match[/green]: {matched.title} / {matched.id}")

    return _common_from_project_id(pack, client, cache, matched.id)


def add_mod_by_project_id(
    pack: LocalPack, client: ModrinthApi, cache: ModCache, project_id: ProjectId
) -> int:
    """
    Adds a new mod by project ID.
    """

    try:
        result = client.get_project_info(project_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print("[red]error:[/red] no such project found")
            return 1

        raise

    return _common_from_project_id(pack, client, cache, result)


def add_mod_by_version_id(
    pack: LocalPack, client: ModrinthApi, cache: ModCache, version_id: VersionId
):
    """
    Adds a new mod by an explicit version ID.
    """

    try:
        found_version = client.get_single_version(version_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print("[red]error:[/red] no such version found")
            return 1

        raise

    project_info = client.get_project_info(found_version.project_id)

    if pack.metadata.game_version not in found_version.game_versions:
        print(
            f"[red]error:[/red] [white]{project_info.title} {found_version.name}[/white] "
            f"does not support [white]{pack.metadata.game_version}[/white]"
        )
        return 1

    if not (set(pack.metadata.available_loaders) | set(found_version.loaders)):
        print(
            f"[red]error:[/red] [white]{project_info.title} {found_version.name}[/white] "
            f"does not support any of {pack.metadata.available_loaders}"
        )
        return 1

    all_versions = [
        (project_info, found_version),
        *resolve_dependency_versions(pack.metadata, client, found_version),
    ]
    pack.download_and_add_mods(client, cache, all_versions, selected_mod=project_info.id)

    return 0
