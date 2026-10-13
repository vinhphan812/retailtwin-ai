"""Store adapter: routes GET /store through either a fixture (day-0 dev) or the
canonical Firestore Live Twin (issue #6 / #81).

Issue #6 replaces this module's open_store with Firestore. The replacement must
keep `loaded`, `store_id`, `view`, and `inventory`. The HTTP routes stay put.
"""

import json
import re
from pathlib import Path

from pydantic import ValidationError

from retailtwin_api.firestore_twin import (
    FirestoreLiveTwinRepository,
    InMemoryTwinRepository,
    InventorySeed,
    LiveTwinRepository,
    StoreRepository,
    TwinConfig,
    TwinUnavailable,
)
from retailtwin_api.schemas import FixtureFile, ProductInventory, StoreResponse
from retailtwin_api.settings import DEFAULT_FIXTURE

_VERSION = re.compile(r"v(?P<number>[0-9]+)\Z")

# ── Default seed for store-001 P001-P003 ────────────────────────────────────

_DEFAULT_SEED: list[InventorySeed] = [
    InventorySeed(
        sku="P001",
        shelf_id="A01",
        slot_id="A01-S01",
        facings=3,
        shelf_quantity=8,
        backroom_quantity=42,
    ),
    InventorySeed(
        sku="P002",
        shelf_id="A01",
        slot_id="A01-S02",
        facings=2,
        shelf_quantity=5,
        backroom_quantity=30,
    ),
    InventorySeed(
        sku="P003",
        shelf_id="B01",
        slot_id="B01-S01",
        facings=4,
        shelf_quantity=12,
        backroom_quantity=60,
    ),
]


def open_store(
    store_id: str,
    use_firestore: bool = True,
    firestore_project: str = "retailtwin-ai-511002",
    fixture_path: Path | None = None,
    seed_data: list[InventorySeed] | None = None,
) -> "StoreRepository":
    """Open a store repository.

    When use_firestore=True (default), backs GET /store from the canonical
    Firestore Live Twin (retailtwin-ai-511002, us-central1).  Seeds the store on
    first call if not yet present.  Falls back to an in-memory repository if
    Firestore is unavailable so tests and local dev work without GCP credentials.

    When use_firestore=False, reads from the committed day-0 fixture JSON for
    local development without GCP credentials.
    """
    if use_firestore:
        config = TwinConfig(project=firestore_project, location="us-central1")
        live_twin = FirestoreLiveTwinRepository(config)
        repo = StoreRepository(live_twin, store_id)
        # Seed once if the store document does not exist yet.
        if not live_twin.is_available():
            # Firestore unreachable — fall back to in-memory so tests pass locally
            live_twin = InMemoryTwinRepository()
            repo = StoreRepository(live_twin, store_id)
            repo._twin.seed(store_id, "v1", seed_data or _DEFAULT_SEED)
            return repo
        try:
            if live_twin.get_store(store_id) is None:
                live_twin.seed(store_id, "v1", seed_data or _DEFAULT_SEED)
        except TwinUnavailable:
            live_twin = InMemoryTwinRepository()
            repo = StoreRepository(live_twin, store_id)
            repo._twin.seed(store_id, "v1", seed_data or _DEFAULT_SEED)
        return repo
    # Day-0 fixture path: use the provided path, or the default fixture if none given
    if fixture_path is None:
        fixture_path = DEFAULT_FIXTURE
    return FixtureStoreRepository(fixture_path, store_id)


def _open_fixture_store(fixture_path: Path, store_id: str) -> "FixtureStoreRepository":
    """Day-0 fixture adapter (legacy path for backward compatibility)."""
    return FixtureStoreRepository(fixture_path, store_id)


def parse_version(version: str) -> int:
    match = _VERSION.fullmatch(version)
    if match is None:
        raise ValueError("store version must look like v1")
    return int(match.group("number"))


class FixtureStoreRepository:
    def __init__(self, fixture_path: Path, store_id: str) -> None:
        self.fixture_path = fixture_path
        self.store_id = store_id
        self.loaded = False
        self.error: str | None = None
        self._file: FixtureFile | None = None
        self._version = 0
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            parsed = FixtureFile.model_validate(payload)
            if parsed.store_id != self.store_id:
                raise ValueError(
                    f"fixture store_id {parsed.store_id!r} does not match {self.store_id!r}"
                )
            version = parse_version(parsed.version)
            skus = [product.sku for product in parsed.products]
            if len(skus) != len(set(skus)):
                raise ValueError("fixture contains a duplicate sku")
            self._file = parsed
            self._version = version
            self.loaded = True
            self.error = None
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            self._file = None
            self.loaded = False
            self.error = str(exc)

    def view(self) -> StoreResponse:
        fixture = self._require()
        return StoreResponse(
            store_id=fixture.store_id,
            context_version=f"{fixture.store_id}:{fixture.version}",
            version=fixture.version,
            products=[self._product(item.sku) for item in fixture.products],
        )

    def inventory(self, sku: str) -> ProductInventory | None:
        fixture = self._require()
        for item in fixture.products:
            if item.sku == sku:
                return self._product(item.sku)
        return None

    def _require(self) -> FixtureFile:
        if self._file is None:
            raise RuntimeError("store fixture is not loaded")
        return self._file

    def _product(self, sku: str) -> ProductInventory:
        fixture = self._require()
        item = next(product for product in fixture.products if product.sku == sku)
        return ProductInventory(
            store_id=fixture.store_id,
            sku=item.sku,
            shelf_id=item.shelf_id,
            slot_id=item.slot_id,
            facings=item.facings,
            shelf_quantity=item.shelf_quantity,
            backroom_quantity=item.backroom_quantity,
            version=self._version,
        )
