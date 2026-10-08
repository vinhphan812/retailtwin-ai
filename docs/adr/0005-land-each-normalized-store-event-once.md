# 0005. Land each normalized store event once

Date: 2026-10-08

## Status

Accepted

## Context

Issue #7 needs an event backbone that can trigger and explain an autonomous run. The domain model already fixes the minimum store event: `event_id`, `correlation_id`, `event_type`, `store_id`, `sku`, `quantity`, `occurred_at`, and `source`. ADR 0003 keeps `POST /events` in process memory and does not publish. The foundation record ADR 0004, on the open cloud-foundation change, puts Pub/Sub topic `store-events` and an empty BigQuery dataset `retailtwin` in `us-central1` and leaves the subscription and the tables to this issue. This record is numbered 0005 so it does not take 0004.

A replay of the same event id has to be visible as a duplicate. BigQuery has no unique constraint. Pub/Sub exactly-once delivery deduplicates a service message id, not a second publish of the same event. Streaming inserts and a Pub/Sub BigQuery subscription are billed outside the on-demand query allowance the foundation stays inside, and both would store a second row unless something else noticed.

Publishing from `POST /events` was set aside. That would replace the acceptance rule in ADR 0003 and would make the API process depend on Google Cloud credentials. A Pub/Sub schema registry entry was set aside too. The registry takes Avro or Protocol Buffer, which would be a second contract beside the JSON shape already in the domain model.

## Decision

The normalized store event is the Pub/Sub message body. Attributes `event_id`, `correlation_id`, `event_type`, and `store_id` copy those fields. The ordering key is `event_id`. `occurred_at` is the event timestamp.

Topic `store-events` keeps the foundation storage limit of `us-central1`. Subscription `store-events-analytics` is a pull subscription with message ordering, a 60 second ack deadline, 7 day retention, and no expiration. It has no push endpoint.

Dataset `retailtwin` gains three day-partitioned tables, clustered by `store_id` and `sku`:

- `sales_events` receives `sale.completed`
- `inventory_events` receives `inventory.*`
- `agent_actions` receives `agent.*`

The day-0 publisher emits `sale.completed` only. The lander writes a row with a query job, not a streaming insert. `ingested_at` is the write time and is not part of identity.

One `event_id` is one stored event across those tables. The same normalized payload is a duplicate and does not add a row. A different payload is a conflict and does not replace the stored row. `correlation_id` on the stored row is the published `correlation_id`. An attribute that disagrees with the body is rejected and is not stored.

`POST /events` still does not publish. This path does not change inventory, write the Live Twin, or start the Observer.

## Consequences

- A fixture can be published, consumed, and queried. Replaying that event id returns duplicate and leaves one row. The correlation id is the same on the message and the row.
- Landing cost stays on the on-demand query allowance. No reservation and no streaming insert are added.
- Ordered publish uses the `us-central1` Pub/Sub endpoint. The topic storage policy rejects an ordering key sent to the global endpoint.
- The API still starts without Google Cloud credentials. ADR 0003 stays in force.
- `retailtwin-api` remains the runtime publisher from the foundation decision. This record does not grant that account BigQuery write or subscription pull, and it does not create a key. The day-0 smoke command uses the operator's existing project credentials.
- `inventory_events` and `agent_actions` use the same envelope and stay empty until those event types are published. Product performance, simulation results, and the Observer remain later work.
- Foundation gate #10 stays open. Firestore, Gemini, and Cloud Run are still required, and a store event does not yet start an investigation.
- Duplicate detection is the lander. A second insert that bypasses the lander can add a row, because BigQuery does not enforce the key. The smoke check counts rows for the fixture event id.
- Pull request:
- Issue: https://github.com/vinhphan812/retailtwin-ai/issues/7
- Supersedes:
- Superseded by:
