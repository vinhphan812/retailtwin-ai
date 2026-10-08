# Store events

Day-0 analytical backbone for issue #7. ADR [0005](../../docs/adr/0005-land-each-normalized-store-event-once.md) is the decision.

`POST /events` does not publish. The API still starts without Google Cloud credentials. Landing a row does not change the Live Twin, and this subscription does not start the Observer.

## Contract

The message body is the normalized store event in [data/schemas/store-event.schema.json](../../data/schemas/store-event.schema.json). `occurred_at` is the event timestamp.

| | |
| --- | --- |
| Project | `retailtwin-ai-511002` |
| Region | `us-central1` |
| Topic | `store-events` |
| Subscription | `store-events-analytics` (pull, ordering on, no expiration, no push endpoint) |
| Dataset | `retailtwin` |
| `sale.completed` | `sales_events` |
| `inventory.*` | `inventory_events` |
| `agent.*` | `agent_actions` |

Attributes `event_id`, `correlation_id`, `event_type`, and `store_id` copy the body. The ordering key is `event_id`. Ordered publish and pull use the `us-central1` Pub/Sub endpoint, because the global endpoint rejects an ordering key when the topic stores messages only in that region.

One `event_id` is one stored row across the three tables. The same normalized payload is a duplicate and does not add a row. A different payload does not replace the stored row. `correlation_id` on the row is the published value.

The publisher emits `sale.completed` only. Inserts are BigQuery query jobs, not streaming inserts, so they stay on the on-demand query allowance. There is no reservation.

The committed fixture is [data/synthetic/sale-completed.json](../../data/synthetic/sale-completed.json): event `evt-sale-0001`, correlation `run-20261007-001`, store `store-001`, SKU `P001`, quantity 3.

## Apply and check

The topic and the empty dataset come from the cloud foundation. This script adds the subscription and the three tables. It refuses every project except `retailtwin-ai-511002` and every region except `us-central1`. It does not create keys or change IAM.

```bash
CONFIRM_GCP_STORE_EVENTS=yes infrastructure/gcp/apply-store-events.sh
infrastructure/gcp/verify-store-events.sh
```

`verify-store-events.sh` only reads the project. Exit 0 means the topic, subscription, dataset, and tables match. Exit 1 is any mismatch.

## Publish and trace

From `apps/api`, with the API virtualenv and Application Default access through `gcloud`:

```bash
python -m retailtwin_api.backbone_cli smoke
```

The command publishes the fixture, lands it, publishes the same event again, and checks that the replay is a duplicate. The trace keeps one row and the correlation id `run-20261007-001`. A second smoke run reports the first delivery as `duplicate` as well. `publish` sends the fixture without consuming it.

The day-0 command uses the operator's project credentials. `retailtwin-api` stays the runtime publisher and does not receive BigQuery write or subscription pull access here.
