import json
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from importlib import metadata
from typing import Literal

import arrow
import cattr
import httpx

from kamuidrome.modrinth.models import (
    ProjectId,
    ProjectInfoFromProject,
    ProjectInfoMixin,
    ProjectSearchResult,
    ProjectVersion,
    VersionId,
)

CONVERTER = cattr.GenConverter()
CONVERTER.forbid_extra_keys = False
CONVERTER.register_structure_hook(arrow.Arrow, lambda it, _: arrow.get(it))

ProjectInfoMixin.configure_converter(CONVERTER)
ProjectVersion.configure_converter(CONVERTER)
VERSION = metadata.version("kamuidrome")


# Here's my small Complaining About The Modrinth API section.
#
# the ``/search`` API and the ``/project`` API have both fields named arbitrarily differently
# (``project_id`` in ``/search``, ``id`` in ``project`` - what fucking ID could it be in search
# that isn't the project ID!) *and* fields with the same name but DIFFERENT meanings (``versions``
# in ``/search`` is the *game versions*, whereas ``versions`` in ``/project`` refers to *project*
# versions instead, and it has a ``game_versions`` field instead.)
#
# the ratelimit stuff is blatant "this was made by somebody who wrote a Discord wrapper library".
# i'm ignoring it because I don't care about hitting your ratelimits.
#
# search queries are some horrible json array query parameter syntax that is passed directly
# to meilisearch (lol) so if you fuck it up you get an unhelpful error message from either the
# backend (because fake json parsing failed) or meilisearch complaining about indexes. fun fucking
# fact: when i was writing this today (2024-01-13), i trieed using a query over ``game_version``
# and it didn't work even though the docs said it would. then the site went down, and it started
# working again immediately after. what the hell is up with that?
#
# STOP MAKING ME PUT JSON IN QUERY STRINGS. are they fucking allergic to commas? hmm yes today
# i will urlescape ``["1.19.2"]``. what a bunch of wasted work for no reason.
#
# minor nitpick: the API returns the sha-1 hash (what?) and the sha512 hash which sucks because
# i use blake2b hashes.
#
# more will certainly come as i deal more with the API, but I am already annoyed.


class ModrinthApi:
    """
    Wrapper around the Modrinth API.
    """

    API_VERSION = "v2"

    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        client.base_url = f"https://api.modrinth.com/{self.API_VERSION}"
        client.headers = {
            "user-agent": f"Mozilla/5.0 (kamuidrome/{VERSION}; https://github.com/Fuyukai/kamuidrome) AppleWebKit/537.3 (KHTML, like Packwiz)"  # noqa: E501
        }
        client.timeout = 30
        client.follow_redirects = True

    def get_project_info(self, project_id: str) -> ProjectInfoFromProject:
        """
        Gets info about the specified project.
        """

        resp = self.client.get(f"/project/{project_id}")
        resp.raise_for_status()
        body = resp.json()
        return CONVERTER.structure(body, ProjectInfoFromProject)

    def get_project_versions(
        self,
        project_id: ProjectId,
        *,
        loaders: Sequence[str] | None = None,
        game_versions: list[str] | str | None = None,
    ) -> list[ProjectVersion]:
        """
        Gets the list of versions for a single project.

        Whilst its not documented anywhere, this is returned in descending upload time order.
        """

        params: dict[str, str] = {}
        if loaders:
            params["loaders"] = json.dumps(loaders)

        if game_versions:
            if isinstance(game_versions, str):
                # fucking modrinth. why?
                game_versions = [game_versions]

            params["game_versions"] = json.dumps(game_versions)

        resp = self.client.get(f"/project/{project_id}/version", params=params)
        resp.raise_for_status()
        return CONVERTER.structure(resp.json(), list[ProjectVersion])

    def get_projects_via_search(
        self,
        search_query: str,
        *facets: str | list[str],
        index: Literal["relevance", "downloads", "follows", "newest", "updated"] = "relevance",
        offset: int = 0,
        limit: int = 100,
    ) -> ProjectSearchResult:
        """
        Gets a list of projects via Modrinth search.
        """

        # modrinth uses this really fucking stupid format for searching
        # it's like... nested json?
        query_facets = [[f] if isinstance(f, str) else f for f in facets]
        resp = self.client.get(
            "/search",
            params={
                "facets": json.dumps(query_facets),
                "query": search_query,
                "offset": offset,
                "limit": limit,
            },
        )
        resp.raise_for_status()
        return CONVERTER.structure(resp.json(), ProjectSearchResult)

    def get_multiple_projects(self, projects: list[ProjectId]) -> list[ProjectInfoFromProject]:
        """
        Gets multiple projeects in one request.
        """

        resp = self.client.get("/projects", params={"ids": json.dumps(projects)})
        resp.raise_for_status()

        return CONVERTER.structure(resp.json(), list[ProjectInfoFromProject])

    def get_single_version(self, version: VersionId) -> ProjectVersion:
        """
        Gets a single version for a project.
        """

        resp = self.client.get(f"/version/{version}")
        resp.raise_for_status()

        return CONVERTER.structure(resp.json(), ProjectVersion)

    def get_multiple_versions(self, versions: list[VersionId]) -> list[ProjectVersion]:
        """
        Gets multiple versions in one request.
        """

        resp = self.client.get(
            "/versions",
            params={
                "ids": json.dumps(versions),
            },
        )
        resp.raise_for_status()

        return CONVERTER.structure(resp.json(), list[ProjectVersion])

    @contextmanager
    def get_file(self, url: str) -> Generator[httpx.Response, None, None]:
        """
        Gets a single file by URL, using this client's ``httpx.Client``.
        """

        with self.client.stream("GET", url) as r:
            yield r
