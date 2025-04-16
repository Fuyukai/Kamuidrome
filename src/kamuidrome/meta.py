import contextlib
import enum
import subprocess
from subprocess import SubprocessError

import attr


class AvailablePackLoader(enum.Enum):
    """
    Enumeration of the supported pack loaders.
    """

    LEGACY_FORGE = "legacyforge"
    FABRIC = "fabric"
    QUILT = "quilt"
    NEOFORGE = "neoforge"


@attr.s(slots=True, kw_only=True)
class PackLoaderInfo:
    """
    Definition for modpack loader information.
    """

    #: The name of the modloader to use.
    type: AvailablePackLoader = attr.ib()

    #: The version of the modloader, if any.
    version: str | None = attr.ib(default=None)

    #: For "legacyforge" and "neoforge", this enables using Fabric mods and treating
    #: Forgified Fabric API as Fabric API for dependency purposes.
    sinytra_compat: bool = attr.ib(default=False)

    #: Hack to work around geckolib issues.
    prefer_fabric_geckolib: bool = attr.ib(default=True)

    def get_modrinth_facets(self, *, pretend_to_be_forge: bool = False) -> list[str]:
        """
        Gets a list of Modrinth facets for the loader information within.
        """

        if self.type == AvailablePackLoader.FABRIC or self.type == AvailablePackLoader.QUILT:
            return [f"categories:{self.type.value}"]

        facets: list[str] = []
        if self.sinytra_compat:
            facets.append("categories:fabric")

        if self.type == AvailablePackLoader.LEGACY_FORGE or pretend_to_be_forge:
            facets.append("categories:forge")

        if self.type == AvailablePackLoader.NEOFORGE:
            facets.append("categories:neoforge")

        return facets

    @property
    def modrinth_facets(self) -> list[str]:
        """
        Gets a list of Modrinth facets for the loader information within.
        """

        return self.get_modrinth_facets(pretend_to_be_forge=False)

    @property
    def mrpack_name(self) -> str:
        """
        Returns the ``mrpack`` dependency name for this loader.
        """

        match self.type:
            case AvailablePackLoader.FABRIC:
                return "fabric-loader"

            case AvailablePackLoader.QUILT:
                return "quilt-loader"

            case AvailablePackLoader.LEGACY_FORGE:
                return "forge"

            case AvailablePackLoader.NEOFORGE:
                return "neoforge"


@attr.s(slots=True, frozen=True, kw_only=True)
class PackMetadata:
    """
    Base definition for a pack file.
    """

    #: Human-friendly name of the pack, used during export.
    name: str = attr.ib()

    #: Human-friendly version of the pack, used during export.
    version: str = attr.ib(default="0.0.0")

    #: If True, dynamic versioning (Git versioning) is enabled.
    dynamic_version: bool = attr.ib(default=False)

    #: The minecraft version for this pack.
    game_version: str = attr.ib()

    #: The additional directories to include.
    include_directories: list[str] = attr.ib()

    loader: PackLoaderInfo = attr.ib()

    def __attrs_post_init__(self) -> None:
        if not self.dynamic_version:
            return

        with contextlib.suppress(SubprocessError):
            described = subprocess.check_output(["git", "describe"], encoding="utf-8").strip()

            if described.startswith("v"):
                described = described[1:]

            object.__setattr__(self, "version", described)

    def get_available_loaders(
        self, *, pretend_to_be_forge: bool = False
    ) -> tuple[str] | tuple[str, str]:
        """
        Returns the available modloaders, in priority order.
        """

        match self.loader.type:
            case AvailablePackLoader.FABRIC:
                return ("fabric",)

            case AvailablePackLoader.QUILT:
                return ("quilt", "fabric")

            case AvailablePackLoader.LEGACY_FORGE if self.loader.sinytra_compat:
                return ("forge", "fabric")

            case AvailablePackLoader.LEGACY_FORGE:
                return ("forge",)

            case AvailablePackLoader.NEOFORGE if pretend_to_be_forge and self.loader.sinytra_compat:
                return ("forge", "fabric")

            case AvailablePackLoader.NEOFORGE if self.loader.sinytra_compat:
                return ("neoforge", "fabric")

            case AvailablePackLoader.NEOFORGE:
                return ("neoforge",)

    @property
    def available_loaders(self) -> tuple[str] | tuple[str, str]:
        """
        Returns the available modloaders, in priority order.
        """

        match self.loader.type:
            case AvailablePackLoader.FABRIC:
                return ("fabric",)

            case AvailablePackLoader.QUILT:
                return ("quilt", "fabric")

            case AvailablePackLoader.LEGACY_FORGE if self.loader.sinytra_compat:
                return ("forge", "fabric")

            case AvailablePackLoader.LEGACY_FORGE:
                return ("forge",)

            case AvailablePackLoader.NEOFORGE if self.loader.sinytra_compat:
                return ("neoforge", "fabric")

            case AvailablePackLoader.NEOFORGE:
                return ("neoforge",)


@attr.s(slots=True, kw_only=True)
class LocalMetadata:
    """
    Wrapper for the data within the ``localpack.toml``.
    """

    #: The name of the instance to deploy to automatically.
    instance_name: str = attr.ib()

    #: Extra directories to symlink, but not to include.
    extra_symlinked_dirs: list[str] = attr.ib(factory=list)
