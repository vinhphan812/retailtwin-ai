"""Read the committed day-0 fixture. This is not the Live Twin.

Issue #6 wires FirestoreLiveTwinRepository when USE_FIRESTORE_TWIN is set.
The returned StoreRepository still exposes `loaded`, `store_id`, `view`,
and `inventory` so HTTP routes are unchanged.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from retailtwin_api.schemas import FixtureFile, ProductInventory, StoreResponse

if TYPE_CHECKING:
    from retailtwin_api.firestore_twin import LiveTwinRepository

_VERSION = re.compile(r"v(?P<number>[0-9]+)\Z")


def parse_version(version: str) -> int:
    match = _VERSION.fullmatch(version)
    if match is None:
        raise ValueError("store version must look like v1")
    return int(match.group("number"))


def open_store(fixture_path: Path, store_id: str) -> "StoreRepository":
    """Day-0 read adapter.

    When USE_FIRESTORE_TWIN=1, opens a FirestoreLiveTwinRepository and wraps
    it in StoreRepository. Otherwise falls back to the committed fixture file.
    """
    if os.environ.get("USE_FIRESTORE_TWIN", "").strip() == "1":
        from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository
        live_twin = FirestoreLiveTwinRepository()
        return StoreRepository(fixture_path, store_id, live_twin=live_twin)
    return StoreRepository(fixture_path, store_id)


class StoreRepository:
    def __init__(
        self,
        fixture_path: Path,
        store_id: str,
        live_twin: "LiveTwinRepository | None" = None,
    ) -> None:
        self.fixture_path = fixture_path
        self.store_id = store_id
        self._live_twin = live_twin
        self.loaded = False
        self.error: str | None = None
        self._file: FixtureFile | None = None
        self._version = 0
        self._load()

    def _load(self) -> None:
        if self._live_twin is not None:
            self._load_from_firestore()
        else:
            self._load_from_fixture()

    def _load_from_firestore(self) -> None:
        """Load store state from Firestore via the Live Twin repository."""
        from retailtwin_api.firestore_twin import TwinUnavailable
        try:
            doc = self._live_twin.get_store(self.store_id)  # type: ignore[union-attr]
            if doc is None:
                self.error = "Store not found in Firestore."
                self.loaded = False
                return
            self._version = self._parse_version(doc.version)
            self.loaded = True
            self.error = None
        except TwinUnavailable as exc:
            self.error = str(exc)
            self.loaded = False

    def _load_from_fixture(self) -> None:
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

    @staticmethod
    def _parse_version(version: str) -> int:
        if version.startswith("v"):
            try:
                return int(version[1:])
            except ValueError:
                return 0
        return 0

    def view(self) -> StoreResponse:
        if self._live_twin is not None:
            from retailtwin_api.firestore_twin import TwinUnavailable
            try:
                store_doc = self._live_twin.get_store(self.store_id)
                if store_doc is None:
                    raise RuntimeError("Store is not loaded")
                items = self._live_twin.list_inventory(self.store_id)
                return StoreResponse(
                    store_id=store_doc.store_id,
                    context_version=f"{store_doc.store_id}:{store_doc.version}",
                    version=store_doc.version,
                    products=[item.to_product_inventory() for item in items],
                )
            except TwinUnavailable as exc:
                raise RuntimeError(f"Live Twin unavailable: {exc}") from exc
        fixture = self._require()
        return StoreResponse(
            store_id=fixture.store_id,
            context_version=f"{fixture.store_id}:{fixture.version}",
            version=fixture.version,
            products=[self._product(item.sku) for item in fixture.products],
        )

    def inventory(self, sku: str) -> ProductInventory | None:
        if self._live_twin is not None:
            from retailtwin_api.firestore_twin import TwinUnavailable
            try:
                doc = self._live_twin.get_inventory(self.store_id, sku)
                if doc is None:
                    return None
                return doc.to_product_inventory()
            except TwinUnavailable:
                return None
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
