"""Normalized store-event identity. One event_id lands once; a replay is a duplicate."""

import json
import os
import re
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import ValidationError

from retailtwin_api.schemas import StoreEvent
from retailtwin_api.settings import REPO_ROOT

ALLOWED_PROJECT = "retailtwin-ai-511002"
ALLOWED_LOCATION = "us-central1"
ALLOWED_TOPIC = "store-events"
ALLOWED_SUBSCRIPTION = "store-events-analytics"
ALLOWED_DATASET = "retailtwin"
TABLES = ("sales_events", "inventory_events", "agent_actions")
SALE_COMPLETED = "sale.completed"
DEFAULT_FIXTURE = REPO_ROOT / "data" / "synthetic" / "sale-completed.json"
_ATTRIBUTE_TEXT = re.compile(r"^[A-Za-z0-9_.:@+-]+$")


class BackboneError(Exception):
    """The store-event backbone cannot publish or land this event."""


@dataclass(frozen=True)
class BackboneConfig:
    project: str = ALLOWED_PROJECT
    location: str = ALLOWED_LOCATION
    topic: str = ALLOWED_TOPIC
    subscription: str = ALLOWED_SUBSCRIPTION
    dataset: str = ALLOWED_DATASET

    def validated(self) -> "BackboneConfig":
        if self.project != ALLOWED_PROJECT:
            raise BackboneError(
                f"Refusing project {self.project}. Store events stay on {ALLOWED_PROJECT}."
            )
        if self.location != ALLOWED_LOCATION:
            raise BackboneError(f"Refusing location {self.location}. Store events stay in {ALLOWED_LOCATION}.")
        if self.topic != ALLOWED_TOPIC:
            raise BackboneError(f"Refusing topic {self.topic}.")
        if self.subscription != ALLOWED_SUBSCRIPTION:
            raise BackboneError(f"Refusing subscription {self.subscription}.")
        if self.dataset != ALLOWED_DATASET:
            raise BackboneError(f"Refusing dataset {self.dataset}.")
        return self


def config_from_env(env: Mapping[str, str] | None = None) -> BackboneConfig:
    source = os.environ if env is None else env
    region = source.get("GCP_REGION", "").strip()
    location = source.get("BIGQUERY_LOCATION", "").strip()
    if region and location and region != location:
        raise BackboneError("GCP_REGION and BIGQUERY_LOCATION differ.")
    return BackboneConfig(
        project=source.get("GCP_PROJECT_ID", "").strip() or ALLOWED_PROJECT,
        location=location or region or ALLOWED_LOCATION,
        topic=source.get("STORE_EVENTS_TOPIC", "").strip() or ALLOWED_TOPIC,
        subscription=source.get("STORE_EVENTS_SUBSCRIPTION", "").strip() or ALLOWED_SUBSCRIPTION,
        dataset=source.get("BIGQUERY_DATASET", "").strip() or ALLOWED_DATASET,
    ).validated()


@dataclass(frozen=True)
class Landing:
    outcome: Literal["inserted", "duplicate", "conflict", "rejected"]
    event: StoreEvent | None
    table: str | None
    reason: str | None = None


@dataclass(frozen=True)
class PulledMessage:
    ack_id: str
    body: str
    attributes: dict[str, str]
    publish_time: str


class EventSink(Protocol):
    def get(self, table: str, event_id: str) -> StoreEvent | None: ...

    def insert(self, table: str, event: StoreEvent) -> None: ...

    def count(self, table: str, event_id: str) -> int: ...


class EventPipe(Protocol):
    def publish(self, event: StoreEvent) -> None: ...

    def pull(self, limit: int = 10) -> list[PulledMessage]: ...

    def ack(self, ack_id: str) -> None: ...


def table_for(event_type: str) -> str | None:
    if event_type == SALE_COMPLETED:
        return "sales_events"
    if event_type.startswith("inventory.") and event_type != "inventory.":
        return "inventory_events"
    if event_type.startswith("agent.") and event_type != "agent.":
        return "agent_actions"
    return None


def format_occurred_at(value: datetime) -> str:
    text = value.astimezone(timezone.utc).isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def canonical_body(event: StoreEvent) -> str:
    payload = {
        "correlation_id": event.correlation_id,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "occurred_at": format_occurred_at(event.occurred_at),
        "quantity": event.quantity,
        "sku": event.sku,
        "source": event.source,
        "store_id": event.store_id,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def parse_event(body: str) -> StoreEvent:
    try:
        return StoreEvent.model_validate_json(body)
    except (ValidationError, ValueError) as exc:
        raise BackboneError("invalid store event") from exc


def load_fixture(path: Path) -> StoreEvent:
    try:
        return StoreEvent.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        raise BackboneError(f"Cannot read fixture {path}") from exc


def require_sale(event: StoreEvent) -> None:
    if event.event_type != SALE_COMPLETED:
        raise BackboneError("This publisher emits sale.completed only.")


def message_attributes(event: StoreEvent) -> dict[str, str]:
    attributes = {
        "correlation_id": event.correlation_id,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "store_id": event.store_id,
    }
    for key, value in attributes.items():
        if _ATTRIBUTE_TEXT.fullmatch(value) is None:
            raise BackboneError(f"{key} cannot be copied into a Pub/Sub attribute.")
    return attributes


def format_attributes(attributes: Mapping[str, str]) -> str:
    return ",".join(f"{key}={attributes[key]}" for key in sorted(attributes))


def attributes_agree(event: StoreEvent, attributes: Mapping[str, str]) -> bool:
    expected = {
        "correlation_id": event.correlation_id,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "store_id": event.store_id,
    }
    return all(attributes[key] == value for key, value in expected.items() if key in attributes)


def row_to_event(row: Mapping[str, object]) -> StoreEvent:
    return StoreEvent.model_validate(
        {
            "event_id": row["event_id"],
            "correlation_id": row["correlation_id"],
            "event_type": row["event_type"],
            "store_id": row["store_id"],
            "sku": row["sku"],
            "quantity": row["quantity"],
            "occurred_at": row["occurred_at"],
            "source": row["source"],
        }
    )


class MemorySink:
    """In-memory stand-in for the three analytical tables."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, StoreEvent]] = {table: {} for table in TABLES}

    def get(self, table: str, event_id: str) -> StoreEvent | None:
        self._known(table)
        row = self.rows[table].get(event_id)
        if row is None:
            return None
        return row.model_copy(deep=True)

    def insert(self, table: str, event: StoreEvent) -> None:
        self._known(table)
        self.rows[table].setdefault(event.event_id, event.model_copy(deep=True))

    def count(self, table: str, event_id: str) -> int:
        self._known(table)
        return int(event_id in self.rows[table])

    def _known(self, table: str) -> None:
        if table not in TABLES:
            raise BackboneError(f"Unknown table {table}.")


class MemoryPipe:
    """Queues canonical messages so the trace can run without Google Cloud."""

    def __init__(self) -> None:
        self.pending: list[PulledMessage] = []
        self.acked: list[str] = []
        self._sequence = 0

    def publish(self, event: StoreEvent) -> None:
        require_sale(event)
        self._sequence += 1
        self.pending.append(
            PulledMessage(
                ack_id=str(self._sequence),
                body=canonical_body(event),
                attributes=message_attributes(event),
                publish_time="",
            )
        )

    def pull(self, limit: int = 10) -> list[PulledMessage]:
        batch = self.pending[:limit]
        self.pending = self.pending[limit:]
        return batch

    def ack(self, ack_id: str) -> None:
        self.acked.append(ack_id)


def find_existing(sink: EventSink, event_id: str) -> tuple[str, StoreEvent] | None:
    found: list[tuple[str, StoreEvent]] = []
    for table in TABLES:
        row = sink.get(table, event_id)
        if row is not None:
            found.append((table, row))
    if not found:
        return None
    if len(found) > 1:
        raise BackboneError(f"event_id {event_id} is stored in more than one table.")
    return found[0]


def land(sink: EventSink, event: StoreEvent) -> Landing:
    table = table_for(event.event_type)
    if table is None:
        return Landing("rejected", None, None, "unsupported_event_type")
    existing = find_existing(sink, event.event_id)
    if existing is not None:
        existing_table, stored = existing
        if existing_table == table and stored == event:
            return Landing("duplicate", stored, table)
        return Landing("conflict", stored, existing_table)
    sink.insert(table, event)
    stored = sink.get(table, event.event_id)
    if stored is None:
        raise BackboneError(f"event_id {event.event_id} was not stored.")
    if stored != event:
        return Landing("conflict", stored, table)
    return Landing("inserted", stored, table)


def handle_message(sink: EventSink, body: str, attributes: Mapping[str, str]) -> Landing:
    try:
        event = parse_event(body)
    except BackboneError:
        return Landing("rejected", None, None, "invalid_event")
    if not attributes_agree(event, attributes):
        return Landing("rejected", event, None, "attribute_mismatch")
    return land(sink, event)


def consume_matching(
    pipe: EventPipe,
    sink: EventSink,
    event: StoreEvent,
    timeout_s: float,
) -> tuple[PulledMessage, Landing]:
    deadline = time.monotonic() + timeout_s
    announced = False
    while time.monotonic() < deadline:
        batch = pipe.pull()
        if not batch:
            if not announced:
                print(f"waiting for {event.event_id}", file=sys.stderr)
                announced = True
            time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))
            continue
        matched: tuple[PulledMessage, Landing] | None = None
        for message in batch:
            landing = handle_message(sink, message.body, message.attributes)
            pipe.ack(message.ack_id)
            if _targets(message, event):
                matched = (message, landing)
        if matched is not None:
            return matched
    raise BackboneError(f"Timed out waiting for {event.event_id}.")


def run_trace(
    event: StoreEvent,
    pipe: EventPipe,
    sink: EventSink,
    timeout_s: float = 90.0,
) -> dict[str, object]:
    require_sale(event)
    pipe.publish(event)
    first_message, first = consume_matching(pipe, sink, event, timeout_s)
    _require_correlation(first_message, event)
    if first.outcome not in ("inserted", "duplicate"):
        raise BackboneError(f"First delivery was {first.outcome}.")
    found = find_existing(sink, event.event_id)
    if found is None or found[0] != "sales_events" or found[1] != event:
        raise BackboneError("Stored sale does not match the published event.")
    if sink.count("sales_events", event.event_id) != 1:
        raise BackboneError("event_id landed more than once.")
    pipe.publish(event)
    replay_message, replay = consume_matching(pipe, sink, event, timeout_s)
    _require_correlation(replay_message, event)
    if replay.outcome != "duplicate":
        raise BackboneError(f"Replay was {replay.outcome}.")
    if sink.count("sales_events", event.event_id) != 1:
        raise BackboneError("Replay added another row.")
    stored_after = find_existing(sink, event.event_id)
    if stored_after is None or stored_after[1] != event:
        raise BackboneError("Replay changed the stored event.")
    return {
        "event_id": event.event_id,
        "correlation_id": stored_after[1].correlation_id,
        "table": "sales_events",
        "first": first.outcome,
        "replay": "duplicate",
        "rows": 1,
    }


def _targets(message: PulledMessage, event: StoreEvent) -> bool:
    try:
        parsed = parse_event(message.body)
    except BackboneError:
        return False
    return parsed.event_id == event.event_id and parsed.event_type == event.event_type


def _require_correlation(message: PulledMessage, event: StoreEvent) -> None:
    if message.attributes.get("correlation_id") != event.correlation_id:
        raise BackboneError("correlation_id was not preserved on the message.")
    if message.attributes.get("event_id") != event.event_id:
        raise BackboneError("event_id was not preserved on the message.")
