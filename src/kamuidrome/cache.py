import hashlib
import json
from collections.abc import Generator
from pathlib import Path

import attr
import cattrs
from httpx import Response

from kamuidrome.modrinth.models import ProjectId, VersionId


@attr.s(slots=True, kw_only=True)
class ModVersionMetadata:
    """
    Contains metadata for a single mod version.
    """

    #: The real filename for this mod.
    real_file_name: str = attr.ib()

    #: The blake2b hash for this mod version.
    blake_hexdigest: str = attr.ib()


class ModCache:
    """
    Stores information related to mods in the mod cache.
    """

    def __init__(self, cache_dir: Path) -> None:
        self.path = cache_dir

        self.path.mkdir(exist_ok=True)

    def get_mod_path(self, id: ProjectId, version_id: VersionId) -> Path:
        """
        Gets the path to a mod ``.jar`` file.

        This path may or may not exist.
        """

        return (self.path / id / version_id).with_suffix(".jar")

    def _get_metadata(self, id: ProjectId) -> dict[str, ModVersionMetadata]:
        path = self.path / id / "metadata.json"
        try:
            content = cattrs.structure(json.loads(path.read_text()), dict[str, ModVersionMetadata])
        except FileNotFoundError:
            content = {}

        return content

    def get_real_filename(self, id: ProjectId, version_id: VersionId) -> str | None:
        """
        Gets the real filename for the provided mod pair, or None if it is an unknown mod/version.
        """

        try:
            return self._get_metadata(id)[version_id].real_file_name
        except (FileNotFoundError, KeyError):
            return None

    def _update_metadata(
        self,
        project_id: ProjectId,
        version_id: VersionId,
        filename: str,
        hash: str,
    ) -> None:
        """
        Updates the metadata for a single mod version file.
        """

        content = self._get_metadata(project_id)
        content[version_id] = ModVersionMetadata(real_file_name=filename, blake_hexdigest=hash)
        with (self.path / project_id / "metadata.json").open(mode="w") as f:
            json.dump(cattrs.unstructure(content), f)

    def get_file_checksum(self, project_id: ProjectId, version_id: VersionId) -> str | None:
        """
        Gets the file checksum for the provided mod, or None if it is an unknown mod/version.
        """

        try:
            return self._get_metadata(project_id)[version_id].blake_hexdigest
        except KeyError:
            return None

    def save_mod_from_response(
        self,
        response: Response,
        project_id: ProjectId,
        version_id: VersionId,
        real_file_name: str,
    ) -> Generator[int, None, None]:
        """
        Downloads a single mod from the provided :class:`.Response`.
        """

        mod_path = self.get_mod_path(project_id, version_id)
        mod_path.parent.mkdir(exist_ok=True)

        summer = hashlib.blake2b()

        with mod_path.open(mode="wb") as f:
            for chunk in response.iter_bytes(16 * 1024):  # 16KiB chunks seems reasonable
                summer.update(chunk)
                f.write(chunk)
                yield len(chunk)

        self._update_metadata(project_id, version_id, real_file_name, summer.hexdigest())
