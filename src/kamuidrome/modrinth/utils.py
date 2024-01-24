from collections.abc import Sequence

from rich import print

from kamuidrome.meta import PackMetadata
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.modrinth.models import (
    ProjectId,
    ProjectInfoFromProject,
    ProjectInfoMixin,
    ProjectVersion,
)

type VersionResult = Sequence[tuple[ProjectInfoMixin, ProjectVersion]]

# Hardcoded Modrinth project IDs used to swap out dependencies easily.

FABRIC_API_VERSION = ProjectId("P7dR8mSH")
FORGIFIED_API_VERSION = ProjectId("Aqlf1Shp")
MODMENU_API_ID = ProjectId("mOgUt4GM")
CONNECTOR_EXTRAS_ID = ProjectId("FYpiwiBR")
FORGE_CONFIG_PORT_ID = ProjectId("ohNO6lps")
GECKOLIB_API_ID = ProjectId("8BmcQJ2H")

DEPENDENCY_SWAPS: dict[ProjectId, ProjectId] = {
    FABRIC_API_VERSION: FORGIFIED_API_VERSION,
    MODMENU_API_ID: CONNECTOR_EXTRAS_ID,
    FORGE_CONFIG_PORT_ID: CONNECTOR_EXTRAS_ID,
}


def resolve_latest_version(
    pack: PackMetadata,
    modrinth: ModrinthApi,
    info: ProjectInfoMixin | ProjectId,
    allow_unstable: bool = False,
) -> ProjectVersion:
    """
    Resolves the latest matching version for the specified mod.

    If ``allow_unstable`` is False, then the most recent *stable* version is chosen; otherwise,
    unstable (alpha and beta) versions will be picked.
    """

    if not isinstance(info, ProjectInfoMixin):
        info = modrinth.get_project_info(info)

    project_id = info.id

    versions = modrinth.get_project_versions(
        project_id=project_id, loaders=pack.available_loaders, game_versions=pack.game_version
    )

    # a bit of trickiness with multiple loader scenarios.
    # some mods are dual fabric-forge (or dual quilt-fabric); and due to the way modrinth orders
    # them, the *secondary* loader might be first.
    # so what we do is we will *always* select *any* version for our preferred loader first,
    # and only fall back to our alternative loader if we fail to select any version for the
    # primary loader.

    versions = sorted(versions, key=lambda it: it.date_published, reverse=True)

    selected_version: ProjectVersion | None = None
    secondary_version: ProjectVersion | None = None

    primary_loader: str
    secondary_loader: str | None = None

    if project_id == ProjectId("8BmcQJ2H") and (
        pack.loader.sinytra_compat and pack.loader.prefer_fabric_geckolib
    ):
        print("[bold yellow]forcing geckolib onto fabric...[/bold yellow]")
        primary_loader = "fabric"
    else:
        primary_loader = pack.available_loaders[0]

        if len(pack.available_loaders) == 2:
            secondary_loader = pack.available_loaders[1]

    # we do a single-pass strategy here using two local variables.
    for version in versions:
        title = info.title

        if primary_loader in version.loaders:
            # a bit of trickiness here; if we find a release version for our preferred loader,
            # that's the version we want to pick *always*.
            # if we find a non-release version for our non-preferred loader, we only select it
            # if we haven't selected a release before, then continue on to try and find a release
            # version.

            if version.version_type == "release" or allow_unstable:
                selected_version = version
                print(
                    f"[green]selected version[/green] "
                    f"[bold white]{version.version_number}[/bold white] "
                    f"for [bold white]{title}[/bold white]"
                )
                break
            elif (  # noqa: RET508
                selected_version is None
            ):
                selected_version = version
                print(
                    f"[italic yellow]saving fallback version[/italic yellow] "
                    f"[bold white]{version.version_number}[/bold white] ({version.loaders}) "
                    f"for [bold white]{title}[/bold white]"
                )
                continue

        # only assign if ``secondary_version`` is None, because we don't want to replace it with
        # an older version for no reason.
        if all(
            (
                secondary_loader is not None,
                secondary_loader in version.loaders,
                secondary_version is None,
            )
        ):
            print(
                f"[italic yellow]saving fallback version[/italic yellow] "
                f"[bold white]{version.version_number}[/bold white] ({version.loaders}) "
                f"for [bold white]{title}[/bold white]"
            )
            # never break here; there might be a primary version coming *after* this one.
            secondary_version = version
        else:
            print(
                f"[red]rejected version[/red] [bold white]{version.version_number}[/bold white] "
                f"for [bold white]{title}[/bold white]"
            )

    if selected_version is not None:
        return selected_version

    if secondary_version is not None:
        title = info.title if isinstance(info, ProjectInfoFromProject) else secondary_version.name
        print(
            "[green]selected secondary version[/green] "
            f"[bold white]{secondary_version.version_number}[/bold white] "
            f"for [bold white]{title}[/bold white]"
        )
        return secondary_version

    raise ValueError(
        f"Couldn't find an appropriate version for {info.title}; "
        f"no valid versions found for {pack.available_loaders} on {pack.game_version}"
    )


def transform_dependencies(pack: PackMetadata, projects: list[ProjectId]) -> list[ProjectId]:
    """
    Transforms dependencies depending on certain pack metadata.
    """

    # TODO: make this more generic.

    if not pack.loader.sinytra_compat:
        return projects

    return [DEPENDENCY_SWAPS.get(i, i) for i in projects]


def get_set_of_dependencies(pack: PackMetadata, version: ProjectVersion) -> list[ProjectId]:
    """
    Gets the appropriate set of required dependencies given the provided :class:`.ProjectVersion`.
    """

    resolved: list[ProjectId] = []
    for dep in version.relationships:
        if dep.dependency_type != "required":
            continue

        if pack.loader.sinytra_compat:
            resolved.append(DEPENDENCY_SWAPS.get(dep.project_id, dep.project_id))
        else:
            resolved.append(dep.project_id)

    return resolved


def resolve_dependency_versions(
    pack: PackMetadata,
    modrinth: ModrinthApi,
    selected_version: ProjectVersion,
    _seen: set[ProjectId] | None = None,
) -> VersionResult:
    """
    Recursively resolves the dependency versions of the provided selected version.
    """

    dependencies = get_set_of_dependencies(pack, selected_version)

    seen: set[ProjectId] = _seen if _seen is not None else set()

    resolved: list[ProjectVersion] = []

    while True:
        if not dependencies:
            break

        next_dependencies: list[ProjectId] = []

        for project in dependencies:
            if project in seen:
                continue

            seen.add(project)
            selected_version = resolve_latest_version(pack, modrinth, project)
            resolved.append(selected_version)
            next_dependencies += get_set_of_dependencies(pack, selected_version)

        dependencies = next_dependencies

    project_infos = modrinth.get_multiple_projects([i.project_id for i in resolved])
    return list(zip(project_infos, resolved, strict=True))
