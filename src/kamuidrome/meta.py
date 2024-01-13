import enum

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

    @property
    def modrinth_facets(self) -> list[str]:
        """
        Gets a list of Modrinth facets for the loader information within.
        """

        if self.type == AvailablePackLoader.FABRIC or self.type == AvailablePackLoader.QUILT:
            return [f"categories:{self.type}"]

        facets: list[str] = []
        if self.sinytra_compat:
            facets.append("categories:fabric")

        if self.type == AvailablePackLoader.LEGACY_FORGE:
            facets.append("categories:forge")
        else:
            facets.append("categories:neoforge")

        return facets


@attr.s(slots=True, frozen=True)
class PackMetadata:
    """
    Base definition for a pack file.
    """

    #: Human-friendly name of the pack, used during export.
    name: str = attr.ib()

    #: Human-friendly version of the pack, used during export.
    version: str = attr.ib()

    #: The minecraft version for this pack.
    game_version: str = attr.ib()

    loader: PackLoaderInfo = attr.ib()

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
