import enum
import typing
from collections.abc import Iterator, Sequence
from typing import Literal, NewType, final, overload

import attr
import cattr
from arrow import Arrow
from cattr import Converter, override
from cattrs.gen._consts import AttributeOverride

# Revert this commit when cattrs 24.x drops.
# type ProjectType = Literal["mod", "modpack", "resourcepack", "shader"]
# type ModSide = Literal["unknown", "required", "optional", "unsupported"]


class ModSideValue(enum.Enum):  # noqa: D101
    UNKNOWN = "unknown"
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNSUPPORTED = "unsupported"


# deliberately undocumented because i'm lazy. see the modrinth docs.
# see client.py for why we need some hackery with cattrs overrides.
# duck typing kinda works at least...

ProjectId = NewType("ProjectId", str)
VersionId = NewType("VersionId", str)


@attr.s(frozen=True, kw_only=True)
class ProjectInfoMixin:
    """
    Common fields between :class:`.ProjectInfoFromSearch` and :class:`.ProjectInfoFromProject`.
    """

    @classmethod
    def configure_converter(cls, converter: Converter) -> None:  # noqa: D102
        # some renames are needed because modrinth is really fucking stupid
        # and likes

        for klass in (ProjectInfoFromSearch, ProjectInfoFromProject):
            converter.register_structure_hook(
                klass,
                cattr.gen.make_dict_structure_fn(
                    klass,
                    converter,
                    raw_categories=override(rename="categories"),
                    raw_versions=override(rename="versions"),
                    **klass.get_overrides(),  # type: ignore  # ok, pyright
                ),
            )

    #: The ID of this project.
    id: ProjectId

    #: The project's URL slug.
    slug: str = attr.ib()
    #: The human-readable title for the project.
    title: str = attr.ib()
    #: Project's short description.
    description: str = attr.ib()  # short description

    # really terrible way of doing it, imo.
    client_side: ModSideValue = attr.ib()
    server_side: ModSideValue = attr.ib()

    raw_categories: list[str] = attr.ib()
    raw_versions: list[str] = attr.ib()


@attr.s(slots=True, frozen=True, kw_only=True)
@final
class ProjectInfoFromSearch(ProjectInfoMixin):
    """
    Wrapper type for project information returned from ``/search``.
    """

    @classmethod
    def get_overrides(cls) -> dict[str, AttributeOverride]:  # noqa: D102
        return {
            "id": override(rename="project_id"),
        }

    id: ProjectId = attr.ib()  # base62 encoded, but we treat it as an opaque string

    @property
    def game_versions(self) -> list[str]:
        """
        Gets the game versions this project is for.
        """

        return self.raw_versions


@attr.s(slots=True, frozen=True, kw_only=True)
@final
class ProjectInfoFromProject(ProjectInfoMixin):
    """
    Wrapper type for project information returned from ``/project``.
    """

    @classmethod
    def get_overrides(cls) -> dict[str, AttributeOverride]:  # noqa: D102
        return {}

    id: ProjectId = attr.ib()

    #: The game versions this project is for.
    game_versions: list[str] = attr.ib()


@attr.s(slots=True, frozen=True, kw_only=True)
@final
class ProjectSearchResult(Sequence[ProjectInfoFromSearch]):
    """
    Wrapper type for the result of a project search.
    """

    # wtf is this name
    hits: list[ProjectInfoFromSearch] = attr.ib()
    offset: int = attr.ib()
    limit: int = attr.ib()
    total_hits: int = attr.ib()

    def __bool__(self) -> bool:
        return bool(self.hits)

    @typing.override
    def __iter__(self) -> Iterator[ProjectInfoFromSearch]:
        return iter(self.hits)

    @typing.override
    def __len__(self) -> int:
        return len(self.hits)

    @overload
    def __getitem__(self, index: int) -> ProjectInfoFromSearch:
        ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[ProjectInfoFromSearch]:
        ...

    @typing.override
    def __getitem__(
        self,
        index: int | slice,
    ) -> ProjectInfoFromSearch | Sequence[ProjectInfoFromSearch]:
        return self.hits[index]


@attr.s(slots=True, frozen=True, kw_only=True)
@final
class ProjectVersionFile:
    """
    A single file for a project version.
    """

    #: The URL for this version.
    url: str = attr.ib()

    #: The real filename for this version.
    filename: str = attr.ib()

    #: If this version is the *primary* file or not (i.e. the main mod file).
    primary: bool = attr.ib(default=False)

    #: The size of the file, in bytes.
    size: int = attr.ib()

    #: Opaque set of hashes in unspecified algorithms.
    hashes: dict[str, str] = attr.ib()


@attr.s(slots=True, frozen=True, kw_only=True)
@final
class ProjectVersionRelation:
    """
    A single relation within a project version.
    """

    #: The ID of the other project version in this relationship.
    version_id: VersionId | None = attr.ib()

    #: The ID of the other project in this relationship.
    project_id: ProjectId = attr.ib()

    #: The type of this relationship.
    dependency_type: Literal["required", "optional", "incompatible", "embedded"] = attr.ib()


@attr.s(slots=True, frozen=True, kw_only=True)
@final
class ProjectVersion:
    """
    A single version within a project.
    """

    @classmethod
    def configure_converter(cls, converter: Converter) -> None:  # noqa: D102
        converter.register_structure_hook(
            ProjectVersion,
            cattr.gen.make_dict_structure_fn(
                ProjectVersion, converter, relationships=override(rename="dependencies")
            ),
        )

    #: The ID for this version.
    id: VersionId = attr.ib()

    #: The project ID for this version.
    project_id: ProjectId = attr.ib()

    #: The name of this version.
    name: str = attr.ib()

    #: The number for this version.
    version_number: str = attr.ib()

    #: The game versions for this mod.
    game_versions: list[str] = attr.ib()

    #: If this version is featured or not.
    featured: bool = attr.ib()

    #: The list of modloaders this version is for.
    loaders: list[str] = attr.ib()

    #: When this version was uploaded.
    date_published: Arrow = attr.ib()

    #: The stability status for this version.
    version_type: Literal["release", "beta", "alpha"] = attr.ib()

    #: The relationships for this version.
    relationships: list[ProjectVersionRelation] = attr.ib(factory=list)

    #: The list of :class:`.ProjectVersionFile` instances for this single version (e.g. main mod
    #: and sources jar, for weirdos who use Modrinth maven).
    files: list[ProjectVersionFile] = attr.ib()

    def __attrs_post_init__(self) -> None:
        if len(self.files) == 1:
            object.__setattr__(self.files[0], "primary", True)

    @property
    def primary_file(self) -> ProjectVersionFile:
        """
        Gets the primary file for this project.
        """

        for file in self.files:
            if file.primary:
                return file

        raise ValueError("modrinth fucked up, missing primary version")
