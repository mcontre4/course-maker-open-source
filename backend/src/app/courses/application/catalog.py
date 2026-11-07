from dataclasses import dataclass

from app.courses.ports.catalog import Catalog


@dataclass(frozen=True)
class CatalogRequest:
    pass


@dataclass(frozen=True)
class CatalogResponse:
    topics: tuple[str, ...]


class GetCatalog:
    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    def execute(self, request: CatalogRequest) -> CatalogResponse:
        return CatalogResponse(self._catalog.topics())
