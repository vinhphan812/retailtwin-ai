"""Pub/Sub and BigQuery adapters. Landing uses query DML, not streaming inserts."""

import base64
import json
import os
import subprocess
from typing import Protocol

from retailtwin_api.backbone import (
    TABLES,
    BackboneConfig,
    BackboneError,
    PulledMessage,
    canonical_body,
    format_attributes,
    format_occurred_at,
    message_attributes,
    require_sale,
    row_to_event,
)
from retailtwin_api.schemas import StoreEvent

_QUERY_BYTE_CAP = "100000000"


class CommandRunner(Protocol):
    def run(self, args: list[str]) -> str: ...


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    # Ordering keys are rejected on the global endpoint when the topic stores
    # messages only in us-central1. Publish and pull through that region.
    env["CLOUDSDK_API_ENDPOINT_OVERRIDES_PUBSUB"] = "https://us-central1-pubsub.googleapis.com/"
    return env


class SubprocessRunner:
    def run(self, args: list[str]) -> str:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            env=command_env(),
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise BackboneError(detail or f"Command failed with exit {completed.returncode}.")
        return completed.stdout


def qualified_table(config: BackboneConfig, table: str) -> str:
    config.validated()
    if table not in TABLES:
        raise BackboneError(f"Unknown table {table}.")
    return f"`{config.project}.{config.dataset}.{table}`"


def parameter_flag(name: str, type_name: str, value: str) -> str:
    if any(char in value for char in "\n\r"):
        raise BackboneError(f"{name} contains a newline.")
    return f"--parameter={name}:{type_name}:{value}"


def event_parameters(event: StoreEvent) -> list[tuple[str, str, str]]:
    return [
        ("event_id", "STRING", event.event_id),
        ("correlation_id", "STRING", event.correlation_id),
        ("event_type", "STRING", event.event_type),
        ("store_id", "STRING", event.store_id),
        ("sku", "STRING", event.sku),
        ("quantity", "INT64", str(event.quantity)),
        ("occurred_at", "TIMESTAMP", format_occurred_at(event.occurred_at)),
        ("source", "STRING", event.source),
    ]


def query_command(
    config: BackboneConfig,
    sql: str,
    parameters: list[tuple[str, str, str]],
) -> list[str]:
    command = [
        "bq",
        "--quiet",
        f"--project_id={config.project}",
        f"--location={config.location}",
        "query",
        "--nouse_legacy_sql",
        "--format=prettyjson",
        f"--maximum_bytes_billed={_QUERY_BYTE_CAP}",
    ]
    for name, type_name, value in parameters:
        command.append(parameter_flag(name, type_name, value))
    command.append(sql)
    return command


def parse_query_output(stdout: str) -> list[dict[str, object]]:
    text = stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BackboneError("BigQuery did not return JSON.") from exc
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    raise BackboneError("BigQuery returned an unexpected payload.")


def parse_pull_output(stdout: str) -> list[PulledMessage]:
    text = stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BackboneError("Pub/Sub pull did not return JSON.") from exc
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise BackboneError("Pub/Sub pull returned an unexpected payload.")
    messages: list[PulledMessage] = []
    for item in payload:
        if not isinstance(item, dict):
            raise BackboneError("Pub/Sub pull returned an unexpected message.")
        ack_id = item.get("ackId") or item.get("ack_id")
        raw_message = item.get("message") or {}
        if not isinstance(ack_id, str) or not ack_id:
            raise BackboneError("Pub/Sub pull is missing an ack id.")
        if not isinstance(raw_message, dict):
            raise BackboneError("Pub/Sub pull returned an unexpected message.")
        attributes = raw_message.get("attributes") or {}
        if not isinstance(attributes, dict):
            attributes = {}
        messages.append(
            PulledMessage(
                ack_id=ack_id,
                body=_decode_body(raw_message.get("data") or ""),
                attributes={str(key): str(value) for key, value in attributes.items()},
                publish_time=str(raw_message.get("publishTime") or raw_message.get("publish_time") or ""),
            )
        )
    return messages


class GcloudPipe:
    def __init__(self, config: BackboneConfig, runner: CommandRunner) -> None:
        self.config = config.validated()
        self.runner = runner

    def publish(self, event: StoreEvent) -> None:
        require_sale(event)
        self.runner.run(
            [
                "gcloud",
                "pubsub",
                "topics",
                "publish",
                self.config.topic,
                "--project",
                self.config.project,
                "--quiet",
                f"--message={canonical_body(event)}",
                f"--attribute={format_attributes(message_attributes(event))}",
                f"--ordering-key={event.event_id}",
            ]
        )

    def pull(self, limit: int = 10) -> list[PulledMessage]:
        bounded = min(10, max(1, limit))
        stdout = self.runner.run(
            [
                "gcloud",
                "pubsub",
                "subscriptions",
                "pull",
                self.config.subscription,
                "--project",
                self.config.project,
                "--quiet",
                "--no-auto-ack",
                f"--limit={bounded}",
                "--format=json",
            ]
        )
        return parse_pull_output(stdout)

    def ack(self, ack_id: str) -> None:
        if not ack_id or any(char in ack_id for char in "\n\r"):
            raise BackboneError("Refusing an empty ack id.")
        self.runner.run(
            [
                "gcloud",
                "pubsub",
                "subscriptions",
                "ack",
                self.config.subscription,
                "--project",
                self.config.project,
                "--quiet",
                f"--ack-ids={ack_id}",
            ]
        )


class BigQuerySink:
    def __init__(self, config: BackboneConfig, runner: CommandRunner) -> None:
        self.config = config.validated()
        self.runner = runner

    def get(self, table: str, event_id: str) -> StoreEvent | None:
        sql = (
            "SELECT event_id, correlation_id, event_type, store_id, sku, quantity, "
            "FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%E6SZ', occurred_at) AS occurred_at, source "
            f"FROM {qualified_table(self.config, table)} "
            "WHERE event_id = @event_id"
        )
        rows = self._rows(sql, [("event_id", "STRING", event_id)])
        if not rows:
            return None
        if len(rows) > 1:
            raise BackboneError(f"event_id {event_id} has {len(rows)} rows in {table}.")
        return row_to_event(rows[0])

    def count(self, table: str, event_id: str) -> int:
        sql = (
            "SELECT COUNT(*) AS row_count "
            f"FROM {qualified_table(self.config, table)} "
            "WHERE event_id = @event_id"
        )
        rows = self._rows(sql, [("event_id", "STRING", event_id)])
        if len(rows) != 1:
            raise BackboneError(f"Could not count {event_id} in {table}.")
        return int(rows[0]["row_count"])

    def insert(self, table: str, event: StoreEvent) -> None:
        target = qualified_table(self.config, table)
        sql = (
            "INSERT INTO "
            f"{target} "
            "(event_id, correlation_id, event_type, store_id, sku, quantity, occurred_at, source, ingested_at) "
            "SELECT @event_id, @correlation_id, @event_type, @store_id, @sku, @quantity, "
            "@occurred_at, @source, CURRENT_TIMESTAMP() "
            "FROM (SELECT 1) "
            f"WHERE NOT EXISTS (SELECT 1 FROM {target} WHERE event_id = @event_id)"
        )
        self.runner.run(query_command(self.config, sql, event_parameters(event)))

    def _rows(self, sql: str, parameters: list[tuple[str, str, str]]) -> list[dict[str, object]]:
        stdout = self.runner.run(query_command(self.config, sql, parameters))
        return parse_query_output(stdout)


def _decode_body(raw: object) -> str:
    if not isinstance(raw, str) or raw == "":
        return ""
    try:
        return base64.b64decode(raw).decode("utf-8")
    except (ValueError, UnicodeError):
        return ""
