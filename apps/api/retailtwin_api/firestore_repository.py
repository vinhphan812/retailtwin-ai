import json
import urllib.request
import urllib.error
from typing import Any
from retailtwin_api.schemas import ProductInventory, StoreResponse

class FirestoreRepository:
    """Canonical Firestore Live Twin repository."""
    def __init__(self, project_id: str, store_id: str) -> None:
        self.project_id = project_id
        self.store_id = store_id
        self.loaded = True 
        self.error = None

    def _get_token(self) -> str:
        # Placeholder for GKE/Cloud Run
        return "fake-token" 

    def _call(self, url: str) -> dict[str, Any]:
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"error": str(e)}

    def view(self) -> StoreResponse:
        url = (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
            f"/databases/(default)/documents/stores/{self.store_id}"
        )
        data = self._call(url)
        if "error" in data:
            raise RuntimeError(f"Firestore Live Twin unavailable: {data.get('error')}")
        
        fields = data.get("fields", {})
        version = fields.get("version", {}).get("stringValue", "v1")
        context_version = fields.get("context_version", {}).get("stringValue", version)
        
        return StoreResponse(
            store_id=self.store_id,
            context_version=context_version,
            version=version,
            products=[],
        )

    def inventory(self, sku: str) -> ProductInventory | None:
        url = (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
            f"/databases/(default)/documents/stores/{self.store_id}/inventory/{sku}"
        )
        data = self._call(url)
        if "error" in data:
            return None
            
        fields = data.get("fields", {})
        def text(name: str) -> str:
            return str(fields.get(name, {}).get("stringValue", ""))
        def integer(name: str) -> int:
            raw = fields.get(name, {}).get("integerValue", 0)
            try:
                return int(raw)
            except (ValueError, TypeError):
                return 0
            
        return ProductInventory(
            store_id=self.store_id,
            sku=text("sku") or sku,
            shelf_id=text("shelf_id"),
            slot_id=text("slot_id"),
            facings=integer("facings"),
            shelf_quantity=integer("shelf_quantity"),
            backroom_quantity=integer("backroom_quantity"),
            version=integer("version"),
        )
