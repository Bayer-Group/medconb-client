import logging
from collections import UserList
from dataclasses import dataclass
from enum import Enum
from typing import Optional, overload

import pandas as pd
from gql import Client as GQLClient
from gql import gql
from gql.transport.requests import RequestsHTTPTransport
from pydantic import BaseModel


class Workspace(BaseModel):
    """
    Workspace as defined in MedConB.

    Attributes:
        collections (list[Collection]): List of collections in the
            workspace owned by the user.
        shared (list[Collection]): List of collections in the workspace
            shared with the user.
    """

    collections: Optional[list["Collection"]]
    shared: Optional[list["Collection"]]


class Collection(BaseModel):
    """
    Collection as defined in MedConB.

    Attributes:
        id (str): ID of the collection.
        name (str): Name of the collection.
        description (str): Description of the collection.
        referenceID (str): ID of the collection this one was copied from.
        itemType (str): Type of the collections items.
        items (list[CodelistInfo | PhenotypeInfo]): Basic information on
            the items in this collection.
        ownerID (str): ID of the owner of the collection.
        locked (bool): Whether the collection is locked.
        visibility (str): Visibility of the collection. Can be "own",
            "shared" or "public".
    """

    id: str
    name: str
    description: Optional[str]
    referenceID: Optional[str]
    itemType: str
    items: list["CodelistInfo | PhenotypeInfo"]
    ownerID: str
    locked: bool
    visibility: str


class CodelistInfo(BaseModel):
    """
    Basic information on a codelist as defined in MedConB.

    Attributes:
        id (str): ID of the codelist.
        name (str): Name of the codelist.
    """

    id: str
    name: str


class PhenotypeInfo(BaseModel):
    """
    Basic information on a phenotype as defined in MedConB.

    Attributes:
        id (str): ID of the phenotype.
        name (str): Name of the phenotype.
    """

    id: str
    name: str


@dataclass
class Codelist:
    """
    Codelist is a codelist as defined in MedConB.

    Attributes:
        id (str): ID of the codelist.
        name (str): Name of the codelist.
        description (str): Description of the codelist.
        codesets (Codesets): List of codesets in the codelist.
    """

    id: str
    name: str
    description: Optional[str]
    codesets: "Codesets"

    def to_pandas(self):
        """
        Convert the codelists codesets to a pandas DataFrame.

        Returns:
            pd.DataFrame: The codesets as a DataFrame.
        """
        return self.codesets.to_pandas()


class Codesets(UserList["Codeset"]):
    """
    Codesets is a list of codesets as defined in MedConB.

    It's just a thin wrapper, so we can offer `to_pandas`.
    """

    def to_pandas(self):
        """
        Convert the codesets to a pandas DataFrame.

        Returns:
            pd.DataFrame: The codesets as a DataFrame.
        """
        rows = []
        for codeset in self.data:
            for code, description in codeset.codes:
                rows.append(
                    {
                        "ontology": codeset.ontology,
                        "code": code,
                        "description": description,
                    }
                )

        return pd.DataFrame(rows)


@dataclass
class Codeset:
    """
    Codeset is a codeset as defined in MedConB.

    Attributes:
        ontology (str): Ontology which the codes belong to
        codes (list[tuple[str, str]]): List of codes, each represented as a tuple of code and description
    """

    ontology: str
    codes: list[tuple[str, str]]  # code, description


class SearchMatchingType(Enum):
    """
    Types of matching to use when searching the public marketplace.

    **Enum Members:**

    Enum Name   | Description
    ------------|------------
    `EXACT`     | Search for an exact match.
    `SUBSTRING` | Search for a substring match.
    """

    EXACT = 1
    SUBSTRING = 2


class Client:
    def __init__(
        self,
        endpoint: str,
        token: str,
    ):
        """
        Creates a new MedConB client.

        Args:
            endpoint (str): URL of the MedConB API. E.g. https://api.medconb.example.com/graphql/
            token (str): Authorization token.
        """
        self.endpoint = endpoint
        self.token = token
        self.transport = RequestsHTTPTransport(
            url=self.endpoint,
            headers={"Authorization": f"Bearer {self.token}"},
            retries=3,
        )
        self.client = GQLClient(
            transport=self.transport,
            fetch_schema_from_transport=True,
            execute_timeout=30,
        )

    def get_workspace(self) -> "Workspace":
        """
        Retrieves a listing of all collections and their codelists/pheontypes
        within the workspace.

        Returns:
            Workspace: Workspace object containing id and name of all codelists and phenotypes.

        Example:
            For a detailed example, see [Examples](/examples#list-all-collections-in-your-workspace).
            ```ipython
            >>> workspace = client.get_workspace()
            >>> print(workspace)
            Workspace(
                collections=[
                    Collection(
                        id="ff755b3a-8f93-43a2-bb8f-2ee435e28938",
                        name="ATTR CM Library",
                        description="...",
                        referenceID="...",
                        itemType="Codelist",
                        items=[
                            CodelistInfo(id="...", name="..."),
                            CodelistInfo(id="...", name="..."),
                            ...
                        ],
                        ownerID="...",
                        locked=False,
                        visibility="Private",
                    ),
                    ...
                ],
                shared=[
                    Collection(...),
                ],
            )
            ```
        """
        query = gql(_GQL_QUERY_WORKSPACE)

        with self.client as session:
            result = session.execute(query)
            workspace_data = result["self"]["workspace"]
            return Workspace(**workspace_data)

    def get_codelist(
        self, codelist_id: str, with_description: bool = False
    ) -> "Codelist":
        """
        Retrieves the codelist by ID from the API and parses
        the data into the python data structures.

        It mirrors the logic of the export and current understanding
        of transient codesets:
        Transient codesets are the current version and should be used
        if they exist. (At some point the API might change to reflect
        that default behaviour better as it might be a bit confusing
        atm.)
        """
        query = gql(
            _GQL_QUERY_CODELST
            if with_description
            else _GQL_QUERY_CODELST_NO_DESCRIPTION
        )

        with self.client as session:
            result = session.execute(query, variable_values={"codelistID": codelist_id})
            codelist_data = result["codelist"]

            css = codelist_data["codesets"]
            tcss = codelist_data["transientCodesets"]
            codesets: Codesets = Codesets()

            if tcss is None:
                tcss = css

            for cs in tcss:
                codesets.append(
                    Codeset(
                        ontology=cs["ontology"]["name"],
                        codes=[
                            (
                                c["code"],
                                c["description"] if with_description else "",
                            )
                            for c in cs["codes"]
                        ],
                    )
                )

            return Codelist(
                id=codelist_data["id"],
                name=codelist_data["name"],
                description=codelist_data.get("description"),
                codesets=codesets,
            )

    @overload
    def get_codelist_by_name(
        self, *, codelist_name: str, codelist_collection_name: str
    ): ...

    @overload
    def get_codelist_by_name(
        self, *, codelist_name: str, phenotype_collection_name: str, phenotype_name: str
    ): ...

    def get_codelist_by_name(
        self,
        *,
        codelist_name,
        codelist_collection_name=None,
        phenotype_collection_name=None,
        phenotype_name=None,
    ) -> "Codelist":
        """
        Retrieves a Codelist by its name.

        Use the arguments `codelist_name` with either:

        - `codelist_collection_name` or
        - `phenotype_collection_name` and `phenotype_name`

        Args:
            codelist_name (str): Name of the codelist
            codelist_collection_name (str, optional): Name of the codelist collection
            phenotype_collection_name (str, optional): Name of the phenotype collection
            phenotype_name (str, optional): Name of the phenotype
        """
        # codelist_collection_name = kwargs.get("codelist_collection_name")
        # codelist_name = kwargs.get("codelist_name")
        # phenotype_collection_name = kwargs.get("phenotype_collection_name")
        # phenotype_name = kwargs.get("phenotype_name")

        if codelist_name is None:
            raise ValueError("Invalid arguments: codelist_name is required")

        mode = None

        if codelist_collection_name is not None:
            mode = "collection"
        elif phenotype_collection_name is not None and phenotype_name is not None:
            mode = "phenotype"
        else:
            raise ValueError(
                "Invalid arguments: Specify either codelist_collection_name or"
                " phenotype_collection_name and phenotype_name"
            )

        candidates = self._search_codelist(codelist_name)
        matches = []

        if mode == "collection":
            matches = self._filter_codelist_in_collection(
                candidates, codelist_collection_name
            )
        else:
            matches = self._filter_codelist_in_phenotype(
                candidates, phenotype_collection_name, phenotype_name
            )

        if len(matches) > 1:
            raise ValueError(
                "The codelist can not be retrieved because the name is ambiguous"
            )

        if len(matches) == 0:
            raise ValueError(
                "The codelist can not be retrieved because it was not found"
            )

        return self.get_codelist(matches[0])

    def search_public_codelists(self, query: str) -> list[CodelistInfo]:
        """
        Searches the public marketplace for codelists.

        Args:
            query (str): A query string similar to a google search.

        Returns:
            list[CodelistInfo]: List of codelists that match the search.

        All search is case-insensitive.

        The search by default searches name and description for the
        search terms. By using "name:search-term" you can search
        a specific field (name in this case).
        To only consider exact matches of a word, use
        "name:'blood'". This will find results like "Blood Infusion",
        but not "bloody nose".
        """
        gql_query = gql(_GQL_QUERY_SEARCH_CODELIST)

        query_str = f"{query} visibility:'public'"

        with self.client as session:
            result = session.execute(gql_query, variable_values={"query": query_str})
            items = result["searchEntities"]["items"]
            res = [CodelistInfo(id=i["id"], name=i["name"]) for i in items]
            return res

    def _filter_codelist_in_phenotype(
        self,
        candidates: list[dict],
        phenotype_collection_name: str,
        phenotype_name: str,
    ) -> list[str]:
        matches = []
        for candidate in candidates:
            ch = candidate["containerHierarchy"]
            if len(ch) != 2:
                # codelists are stacked:
                # Phenotype Collection -> Phenotype -> Codelist
                # so this is probably a codelist Collection
                continue

            if ch[0]["type"] != "Collection" or ch[1]["type"] != "Phenotype":
                logging.warning("API returned an unexpected data structure.")
                continue

            if (
                ch[0]["name"] != phenotype_collection_name
                or ch[1]["name"] != phenotype_name
            ):
                logging.debug(
                    "Disregarding codelist of the requested name because"
                    " the containing Collection has the wrong name"
                    f" ({ch[0]['name']} != {phenotype_collection_name}"
                    f", {ch[1]['name']} != {phenotype_name})"
                )
                continue

            matches.append(candidate["id"])

        return matches

    def _filter_codelist_in_collection(
        self, candidates: list[dict], codelist_collection_name: str
    ) -> list[str]:
        matches = []
        for candidate in candidates:
            ch = candidate["containerHierarchy"]
            if len(ch) != 1:
                # codelists are directly in codelist collections
                # so this is probably a codelist of a Phenotype
                continue

            if ch[0]["type"] != "Collection":
                logging.warning(
                    "API returned an unexpected data structure: No Collection as root."
                )
                continue

            if ch[0]["name"] != codelist_collection_name:
                logging.debug(
                    "Disregarding codelist of the requested name because"
                    " the containing Collection has the wrong name"
                    f" ({ch[0]['name']} != {codelist_collection_name})"
                )
                continue

            matches.append(candidate["id"])

        return matches

    def _search_codelist(self, codelist_name: str) -> list[dict]:
        query = gql(_GQL_QUERY_SEARCH_CODELIST)

        query_str = f"name:'^{codelist_name}$' visibility:'public,shared,own'"

        with self.client as session:
            result = session.execute(query, variable_values={"query": query_str})
            return result["searchEntities"]["items"]


# GQL Queries
_GQL_QUERY_WORKSPACE = """
query {
    self {
        workspace {
            collections {
                id
                name
                description
                referenceID
                itemType
                ownerID
                locked
                visibility
                items {
                    ... on Codelist {
                        id
                        name
                    }
                    ... on Phenotype {
                        id
                        name
                    }
                }
            }
            shared {
                id
                name
                description
                referenceID
                itemType
                ownerID
                locked
                visibility
                items {
                    ... on Codelist {
                        id
                        name
                    }
                    ... on Phenotype {
                        id
                        name
                    }
                }
            }
        }
    }
}
"""

_GQL_QUERY_CODELST = """
query codelist($codelistID: ID!) {
    codelist(codelistID: $codelistID) {
        id
        name
        codesets {
            ontology { name }
            codes {
                code
                id
                description
                numberOfChildren
            }
        }
        transientCodesets {
            ontology { name }
            codes {
                code
                id
                description
                numberOfChildren
            }
        }
    }
}
"""


_GQL_QUERY_CODELST_NO_DESCRIPTION = """
query codelist($codelistID: ID!) {
    codelist(codelistID: $codelistID) {
        id
        name
        codesets {
            ontology { name }
            codes {
                code
                id
                numberOfChildren
            }
        }
        transientCodesets {
            ontology { name }
            codes {
                code
                id
                numberOfChildren
            }
        }
    }
}
"""

_GQL_QUERY_SEARCH_CODELIST = """
query codelist($query: String!) {
    searchEntities(
        entityType: Codelist
        query: $query
    ) {
        items {
            ... on Codelist {
                id
                name
                containerHierarchy {
                    type
                    name
                }
            }
        }
    }
}
"""
