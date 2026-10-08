import base64
import json

import pytest

from retailtwin_api.backbone import (
    DEFAULT_FIXTURE,
    BackboneError,
    MemoryPipe,
    MemorySink,
    canonical_body,
    config_from_env,
    format_attributes,
    handle_message,
    land,
    load_fixture,
    message_attributes,
    parse_event,
    row_to_event,
    run_trace,
)
from retailtwin_api.backbone_gcp import BigQuerySink, GcloudPipe, command_env, parse_pull_output
from retailtwin_api.schemas import StoreEvent
from retailtwin_api.settings import REPO_ROOT


class FakeRunner:
    def __init__(self, output: str = "") -> None:
        self.commands: list[list[str]] = []
        self.output = output

    def run(self, args: list[str]) -> str:
        self.commands.append(args)
        return self.output


def event() -> StoreEvent:
    return load_fixture(DEFAULT_FIXTURE)


def test_fixture_keeps_the_correlation_id() -> None:
    sale = event()

    assert sale.event_id == "evt-sale-0001"
    assert sale.correlation_id == "run-20261007-001"
    assert sale.event_type == "sale.completed"
    assert sale.store_id == "store-001"
    assert sale.sku == "P001"
    assert sale.quantity == 3


def test_canonical_body_is_stable_for_the_same_instant() -> None:
    sale = event()
    payload = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    payload["occurred_at"] = "2026-10-07T08:01:00+00:00"
    shifted = StoreEvent.model_validate(payload)

    assert canonical_body(sale) == canonical_body(shifted)
    assert "run-20261007-001" in canonical_body(sale)
    assert parse_event(canonical_body(sale)) == sale


def test_schema_requires_the_correlation_id() -> None:
    schema = json.loads((REPO_ROOT / "data" / "schemas" / "store-event.schema.json").read_text())

    assert schema["additionalProperties"] is False
    assert "correlation_id" in schema["required"]
    assert "event_id" in schema["required"]
    assert schema["properties"]["quantity"]["minimum"] == 1


def test_same_event_id_lands_once_and_a_replay_is_a_duplicate() -> None:
    sale = event()
    sink = MemorySink()

    first = land(sink, sale)
    replay = land(sink, sale)

    assert first.outcome == "inserted"
    assert replay.outcome == "duplicate"
    assert replay.event is not None
    assert replay.event.correlation_id == "run-20261007-001"
    assert sink.count("sales_events", sale.event_id) == 1


def test_a_different_payload_does_not_replace_the_stored_event() -> None:
    sale = event()
    sink = MemorySink()
    land(sink, sale)

    conflict = land(sink, sale.model_copy(update={"quantity": 9}))

    assert conflict.outcome == "conflict"
    assert conflict.event is not None
    assert conflict.event.quantity == 3
    assert conflict.event.correlation_id == "run-20261007-001"
    assert sink.count("sales_events", sale.event_id) == 1


def test_the_same_event_id_cannot_also_land_as_inventory() -> None:
    sale = event()
    sink = MemorySink()
    land(sink, sale)

    conflict = land(sink, sale.model_copy(update={"event_type": "inventory.adjusted"}))

    assert conflict.outcome == "conflict"
    assert sink.count("inventory_events", sale.event_id) == 0
    assert sink.count("sales_events", sale.event_id) == 1


def test_inventory_and_agent_events_use_their_own_tables() -> None:
    sale = event()
    sink = MemorySink()

    inventory = land(sink, sale.model_copy(update={"event_id": "evt-inv-0001", "event_type": "inventory.adjusted"}))
    action = land(sink, sale.model_copy(update={"event_id": "evt-agent-0001", "event_type": "agent.action"}))

    assert inventory.table == "inventory_events"
    assert action.table == "agent_actions"


def test_an_unknown_event_type_is_rejected() -> None:
    sale = event()
    sink = MemorySink()

    rejected = land(sink, sale.model_copy(update={"event_type": "promotion.started"}))

    assert rejected.outcome == "rejected"
    assert sink.count("sales_events", sale.event_id) == 0


def test_an_attribute_that_disagrees_with_the_body_is_not_stored() -> None:
    sale = event()
    sink = MemorySink()

    rejected = handle_message(sink, canonical_body(sale), {"correlation_id": "run-other"})

    assert rejected.outcome == "rejected"
    assert rejected.reason == "attribute_mismatch"
    assert sink.count("sales_events", sale.event_id) == 0


def test_trace_preserves_the_correlation_id_and_detects_the_replay() -> None:
    report = run_trace(event(), MemoryPipe(), MemorySink(), timeout_s=1)

    assert report == {
        "event_id": "evt-sale-0001",
        "correlation_id": "run-20261007-001",
        "table": "sales_events",
        "first": "inserted",
        "replay": "duplicate",
        "rows": 1,
    }


def test_trace_conflict_leaves_the_original_row() -> None:
    sale = event()
    sink = MemorySink()
    land(sink, sale.model_copy(update={"quantity": 9}))

    with pytest.raises(BackboneError, match="First delivery was conflict"):
        run_trace(sale, MemoryPipe(), sink, timeout_s=1)

    assert sink.get("sales_events", sale.event_id).quantity == 9
    assert sink.count("sales_events", sale.event_id) == 1


def test_publisher_refuses_an_attribute_unsafe_correlation_id() -> None:
    with pytest.raises(BackboneError, match="correlation_id"):
        message_attributes(event().model_copy(update={"correlation_id": "run,other"}))


def test_formatted_timestamp_matches_the_fixture_instant() -> None:
    sale = event()
    row = {
        "event_id": sale.event_id,
        "correlation_id": sale.correlation_id,
        "event_type": sale.event_type,
        "store_id": sale.store_id,
        "sku": sale.sku,
        "quantity": "3",
        "occurred_at": "2026-10-07T08:01:00.000000Z",
        "source": sale.source,
    }

    assert row_to_event(row) == sale


def test_publish_command_copies_the_correlation_id() -> None:
    sale = event()
    runner = FakeRunner("messageIds: []\n")

    GcloudPipe(config_from_env({}), runner).publish(sale)

    command = runner.commands[0]
    assert command[4] == "store-events"
    assert f"--ordering-key={sale.event_id}" in command
    assert "--attribute=correlation_id=run-20261007-001,event_id=evt-sale-0001,event_type=sale.completed,store_id=store-001" in command
    message = next(part for part in command if part.startswith("--message="))
    assert message == f"--message={canonical_body(sale)}"
    assert format_attributes(message_attributes(sale)) in command[-2]


def test_event_id_stays_a_query_parameter() -> None:
    sale = event().model_copy(update={"event_id": "evt' OR 1=1"})
    runner = FakeRunner("[]")
    sink = BigQuerySink(config_from_env({}), runner)

    assert sink.get("sales_events", sale.event_id) is None

    command = runner.commands[0]
    sql = command[-1]
    assert sale.event_id not in sql
    assert "WHERE event_id = @event_id" in sql
    assert f"--parameter=event_id:STRING:{sale.event_id}" in command


def test_unknown_table_is_rejected_before_a_query() -> None:
    runner = FakeRunner("[]")

    with pytest.raises(BackboneError, match="Unknown table"):
        BigQuerySink(config_from_env({}), runner).get("other_events", "evt-sale-0001")

    assert runner.commands == []


def test_insert_uses_the_sales_table_and_keeps_the_correlation_parameter() -> None:
    sale = event()
    runner = FakeRunner("")

    BigQuerySink(config_from_env({}), runner).insert("sales_events", sale)

    command = runner.commands[0]
    sql = command[-1]
    assert "INSERT INTO `retailtwin-ai-511002.retailtwin.sales_events`" in sql
    assert "WHERE NOT EXISTS" in sql
    assert "--parameter=correlation_id:STRING:run-20261007-001" in command
    assert "streaming" not in sql.lower()


def test_pull_output_decodes_the_event_and_its_correlation_id() -> None:
    sale = event()
    payload = [
        {
            "ackId": "ack-1",
            "message": {
                "data": base64.b64encode(canonical_body(sale).encode()).decode(),
                "attributes": message_attributes(sale),
                "publishTime": "2026-10-08T00:00:00Z",
            },
        }
    ]

    messages = parse_pull_output(json.dumps(payload))

    assert len(messages) == 1
    assert messages[0].ack_id == "ack-1"
    assert messages[0].attributes["correlation_id"] == "run-20261007-001"
    assert parse_event(messages[0].body) == sale


def test_pubsub_uses_the_regional_endpoint() -> None:
    assert command_env()["CLOUDSDK_API_ENDPOINT_OVERRIDES_PUBSUB"] == "https://us-central1-pubsub.googleapis.com/"


def test_config_refuses_another_project() -> None:
    with pytest.raises(BackboneError, match="retailtwin-ai-511002"):
        config_from_env({"GCP_PROJECT_ID": "cn-prj-17cd4"})

    with pytest.raises(BackboneError, match="retailtwin-ai-511002"):
        config_from_env({"GCP_PROJECT_ID": "ess-prj"})

    with pytest.raises(BackboneError, match="us-central1"):
        config_from_env({"GCP_REGION": "us-east1"})
