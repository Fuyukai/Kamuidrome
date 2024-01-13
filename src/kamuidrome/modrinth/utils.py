from collections.abc import Sequence

from rich import print

from kamuidrome.meta import PackMetadata
from kamuidrome.modrinth.client import ModrinthApi
from kamuidrome.modrinth.models import ProjectId, ProjectInfoFromProject, ProjectVersion

type VersionResult = Sequence[tuple[ProjectInfoFromProject, ProjectVersion]]

# Hardcoded Modrinth project IDs used to swap out dependencies easily.

DEPENDENCY_SWAPS: dict[ProjectId, ProjectId] = {
    # Fabric API -> Forgified Fabric API
    ProjectId("P7dR8mSH"): ProjectId("Aqlf1Shp")
}


def resolve_latest_version(
    pack: PackMetadata,
    modrinth: ModrinthApi,
    info: ProjectInfoFromProject | ProjectId,
    allow_unstable: bool = False,
) -> ProjectVersion:
    """
    Resolves the latest matching version for the specified mod.

    If ``allow_unstable`` is False, then the most recent *stable* version is chosen; otherwise,
    unstable (alpha and beta) versions will be picked.
    """

    project_id = info.id if isinstance(info, ProjectInfoFromProject) else info

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

    primary_loader = pack.available_loaders[0]
    secondary_loader: str | None = None
    if len(pack.available_loaders) == 2:
        secondary_loader = pack.available_loaders[1]

    # we do a single-pass strategy here using two local variables.
    for version in versions:
        title = info.title if isinstance(info, ProjectInfoFromProject) else version.name

        if primary_loader in version.loaders:
            # break here if stable; it's sorted by upload time so unless the author did a silly
            # and uploaded an older version for the wrong game version, it'll be fine; we got the
            # newest version for our primary loader.
            selected_version = version

            if version.version_type == "release" or allow_unstable:
                print(
                    f"[green]selected version[/green] "
                    f"[bold green]{version.version_number}[/bold green] "
                    f"for [green]{title}[/green]"
                )
                break
            else:  # noqa: RET508
                print(
                    f"[italic yellow]saving fallback version[/italic yellow] "
                    f"[bold green]{version.version_number}[/bold green] ({version.loaders}) "
                    f"for [green]{title}[/green]"
                )

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
                f"[bold green]{version.version_number}[/bold green] ({version.loaders}) "
                f"for [green]{title}[/green]"
            )
            # never break here; there might be a primary version coming *after* this one.
            secondary_version = version
        else:
            print(
                f"[yellow]rejected version[/yellow] [red]{version.version_number}[/red] "
                f"for [green]{title}[/green]"
            )

    if selected_version is not None:
        return selected_version

    if secondary_version is not None:
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
) -> VersionResult:
    """
    Recursively resolves the dependency versions of the provided selected version.
    """

    dependencies = get_set_of_dependencies(pack, selected_version)
    seen: set[ProjectId] = set()

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