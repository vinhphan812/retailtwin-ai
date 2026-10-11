"""Public request and response models for the day-0 API."""

from typing import Literal, List, Optional, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from retailtwin_api.contracts import ActionUnion


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: Literal["retailtwin-api"]
    environment: str
    store_id: str
    fixture_loaded: bool


class ProductInventory(BaseModel):
    store_id: str
    sku: str
    shelf_id: str
    slot_id: str
    facings: int
    shelf_quantity: int
    backroom_quantity: int
    version: int


class StoreResponse(BaseModel):
    store_id: str
    context_version: str
    version: str
    products: list[ProductInventory]


class FixtureProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str = Field(min_length=1)
    shelf_id: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    facings: int = Field(ge=0)
    shelf_quantity: int = Field(ge=0)
    backroom_quantity: int = Field(ge=0)


class FixtureFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    store_id: str = Field(min_length=1)
    version: str
    products: list[FixtureProduct]


class StoreEvent(BaseModel):
    """Minimum normalized store event from the domain model."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    occurred_at: AwareDatetime
    source: str = Field(min_length=1)

    @field_validator(
        "event_id",
        "correlation_id",
        "event_type",
        "store_id",
        "sku",
        "source",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value



class EventReceipt(BaseModel):
    accepted: Literal[True] = True
    duplicate: bool
    event: StoreEvent

# ---------------------------------------------------------------------------
# Provider-neutral Simulation/Activity APIs
# ---------------------------------------------------------------------------

class AgentActivityEntry(BaseModel):
    id: str
    ts: str
    stage: str
    summary: str
    correlation_id: Optional[str] = None
    decision_id: Optional[str] = None
    sku: Optional[str] = None

class ActivityResponse(BaseModel):
    activities: List[AgentActivityEntry]
    total: int

class SimulationSummary(BaseModel):
    simulation_id: str
    store_id: str
    base_context_version: str
    status: str

class SimulationsResponse(BaseModel):
    simulations: List[SimulationSummary]

class SimulationResponse(BaseModel):
    simulation_id: str
    store_id: str
    base_context_version: str
    status: str
    actions: List[ActionUnion]
    state: StoreResponse

class SimulationCandidateResponse(BaseModel):
    candidate_id: str
    simulation_id: str
    proposed_actions: List[ActionUnion]

class KPIResultResponse(BaseModel):
    simulation_id: str
    kpi_score: float
    duration_ms: int
