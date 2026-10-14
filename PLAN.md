# PLAN — Issue #38 [I04][P0] Build Alert and Opportunity UI

Branch: `feat/issue-38-alert-opportunity-ui` (from `main` @ cd03039)

Decisions agreed on 2026-10-14:
- Scope: FE + align the `Anomaly` type to the contract BE already serves. Wiring `GET /anomalies` (client, `anomalySource`) stays in #95. The PR uses `Refs #38` (the E2E check needs BE).
- Lifecycle: derived from agent events (`run.store`) correlated by `correlation_id`.
- Opportunity vs alert: by `anomaly_type` (`demand_surge` = opportunity, anything else = alert).
- Placement: a section in the Operations lens, above the Agent Activity timeline.

## 1. Problem and root cause

Once a business condition (for example a demand surge on P017) triggers the agent, the operator sees only a 3D halo and lines in the timeline. No list shows the "alerts/opportunities" that are open, their severity, which SKU or shelf they are on, or how far the agent has handled them.

Current state:
- **FE** has `anomaly.store` (`setAll` / `raise` / `resolve`), the halo (`Stock`), `AnomalyList` in the product card, `ProductDetailsDialog`, and `ui.store.select` / `focusEntity`. It has no list of all anomalies and no lifecycle.
- **The FE `Anomaly` type is an old proposal** (`kind: stockout | low_stock | sales_drop`, `slot_id`, `context_version`, `correlation_id`). It does not match what `apps/api` serves (`schemas.py`):
  - `Anomaly { anomaly_id, anomaly_type (stockout | demand_surge | slow_moving | excess_inventory | price_anomaly | shelf_violation), severity (low | medium | high | critical), store_id, sku?, shelf_id?, title, description, detected_at, event_ids[], metadata{} }`
  - `AnomaliesResponse { anomalies, total, detected_since? }`
- **BE lacks the fields needed for a lifecycle.** `Anomaly` has no `correlation_id` (nor `context_version` or `slot_id`). The demand-surge detector (`demand_surge.py`) does not write an anomaly anywhere yet, and the Observer (#12) is still open, so the E2E check "publish demand spike → alert appears" cannot pass on the FE alone.
- `run.store` (the Agent Activity timeline) is filled only by tests and the demo run. Its FE `ActivityEntry` already has `correlation_id`.

## 2. Files to change or add

| File | Change | Why |
|---|---|---|
| `apps/web/src/enums/anomaly.enum.ts` | `ANOMALY_TYPE` (the 6 BE values) replaces `ANOMALY_KIND`; add `critical` to `ANOMALY_SEVERITY`; add `ANOMALY_CATEGORY` (alert / opportunity) + `categoryOf(type)`; add `ALERT_LIFECYCLE` (detected → investigating → planning → guarding → acting → verifying) | Match the BE contract; classify opportunities |
| `apps/web/src/types/anomaly.type.ts` | Fields BE serves are required (`anomaly_type`, `title`, `description`, `event_ids`, `metadata`; `sku` / `shelf_id` may be null). FE proposals become optional with `TODO(BE)`: `correlation_id?`, `slot_id?`, `context_version?`. `AnomaliesResponse` = `{ anomalies, total, detected_since? }` | Align with `GET /anomalies` |
| `apps/web/src/state/anomaly.store.ts` | Keep `setAll` / `raise` / `resolve`; add `readError` + `fail(message)` (`setAll` clears it); `anomaliesOf` / `worstSeverities` skip anomalies with no SKU | A failed read is visible; #95 calls `fail()` |
| `apps/web/src/core/anomaly/lifecycle.ts` (new) | `alertLifecycle(anomaly, activity)`: the latest correlated entry → lifecycle step; `sortAlerts` (severity desc, then `detected_at` desc); `alertTarget(anomaly, twin)` → `{entityId, entityType}` or null (SKU first, else shelf/equipment, using the same rule as `agentFocusOf`) | Pure logic, unit-tested |
| `apps/web/src/components/layout/AlertsSection.tsx` (new) | "Alerts & opportunities" section: count, Alert/Opportunity chip, severity, title, SKU/shelf, time, lifecycle step bar. Clicking an item → `select(...)` (camera flies) + filter the timeline by `correlation_id`. States: empty, failed read (keeps the last list), Simulation view (anomalies describe Live), target not in the twin (cannot be selected) | The issue's UI |
| `apps/web/src/components/layout/AgentActivityPanel.tsx` | Mount `AlertsSection` in `OperationsView`; when an alert is selected, the timeline shows only its correlation, with a "Show all" chip | Link alert ↔ timeline |
| `apps/web/src/state/ui.store.ts` | `focusedCorrelationId` + `focusAlert(id \| null)`; a new user selection clears it | Shared timeline filter state |
| `apps/web/src/components/twin/AnomalyList.tsx`, `ProductDetailsDialog.tsx`, `ProductInspector.tsx` | Read `anomaly_type` / `title` instead of `kind`; show the "older twin state" note only when `context_version` is present | Follow the new type |
| `apps/web/src/core/utils/theme.ts`, `src/app/App.css`, `ProductDetailsDialog.css` | Add the `--color-anomaly-critical` token + fallback, `data-severity="critical"` | New severity |
| `apps/web/src/fixtures/demo/anomalies.ts` | Rewrite in the BE shape with deterministic `title` / `description` taken from the shelf figures (no LLM). Add one `demand_surge` opportunity on a stocked SKU (P017 is deliberately absent from the demo store). Drop `low_stock` (BE has no such type). Every severity sits on a stocked product. The P003 anomaly's `correlation_id` matches the demo run | Demo shows a full lifecycle |
| `apps/web/src/fixtures/demo/agentRun.ts` | The demo run uses a fixed `DEMO_RUN_ID` as `correlation_id` (ids stay unique because the replay resets the store) | Correlates with the P003 alert |
| `apps/web/src/core/twin/devSources.ts`, `simulateAnomaly.ts` | `twin.raise(sku, type, severity)` uses `AnomalyType` | Follow the new type |
| `apps/web/src/i18n/locales/en.ts` | Keys `anomaly.type.*`, `anomaly.severity.critical`, `alerts.*` (title, category, lifecycle, empty, unavailable, simulation, notInTwin, showAll) | i18n |
| `apps/web/README.md` | "Alerts & opportunities" section: schema, provenance (title/description/severity come from the BE detector, lifecycle from correlated agent events), failure path, BE fields still missing | DoD: schema/provenance documented |
| Tests (see §5) | New + updated | |

Out of scope: `client.anomalies()`, `anomalySource`, polling / back-off (#95); `client.agentEvents` (#94); BE writing anomalies from the detector or adding `correlation_id` (#79 / #12 / #30); SSE.

## 3. Steps, in order (one commit each)

1. `refactor(web): align Anomaly with the served GET /anomalies contract (#38)`: enum, type, store (`readError` / `fail`), theme critical, consumer components, demo fixtures, devSources, i18n; fix the existing tests. Tests green.
2. `feat(web): derive alert lifecycle from correlated agent events (#38)`: `core/anomaly/lifecycle.ts` + unit tests; demo run with a fixed correlation id.
3. `feat(web): add the Alerts & opportunities section to Operations (#38)`: `AlertsSection`, `ui.store.focusAlert`, timeline filter, CSS; component tests.
4. `docs(web): document alert/opportunity schema, provenance and failure path (#38)`: README.
5. Run the full check (§5) and a browser check under `?twin=demo`; update `PLAN.md` if anything changed.
6. (After you confirm) post comments: on #79 (BE: add `correlation_id`, `slot_id`, `context_version`; write demand-surge anomalies into `anomalies`; resolve on VERIFY PASS) and on #95 (the type is aligned; `anomalySource` calls `setAll` / `fail`).

## 4. Risks and impact

- **Type change touches many places** (halo, product card, details dialog, devSources, demo, tests). `tsc` catches every one; the halo and selection tests keep guarding regressions.
- **Demo anomalies change**: P004 / P007 (low stock) lose their anomaly. `StoreStatus` still lists them as low stock from the twin figures. The README's manual-check notes are updated.
- **`sku` may be null** in BE (for example `shelf_violation`): the halo and `anomaliesOf` skip it; the alert focuses its shelf instead.
- **Lifecycle depends on `correlation_id`**, which BE does not serve yet. Until it does, a real alert stays at "Detected". This is honest (no made-up state), but the lifecycle does not move outside demo/tests. It is requested in #79.
- **No "Resolved" step in the list**: an anomaly that BE resolves leaves `GET /anomalies`, so it leaves the list. The final visible step is "Verifying". The FE does not keep a history of its own, to avoid making up state.
- **Panel layout**: the section sits above the timeline, so it has a max height and scrolls inside itself so the timeline is not pushed out.
- Production / apps/api path: unchanged (no new call); the store stays empty → the section shows "No open alerts".

## 5. Test plan

New tests:
- `src/test/core/anomaly/lifecycle.test.ts`
  - no correlated entry, or no `correlation_id` → `detected`
  - each stage maps to the right step (DETECT → detected, INVESTIGATE → investigating, PLAN / SIMULATE → planning, GUARD → guarding, ACT → acting, VERIFY → verifying)
  - the latest entry by `ts` wins; entries from another correlation are ignored
  - `categoryOf`: `demand_surge` → opportunity, the other types → alert
  - `sortAlerts` orders by severity, then time; `alertTarget` gives the SKU, else shelf / equipment, else null when the target is not in the twin
- `src/test/components/layout/AlertsSection.test.tsx`
  - an alert appears with no prompt as soon as the store receives it (`raise`), with the right SKU and category chip
  - the lifecycle moves as `run.store.append` brings correlated entries; `resolve` removes it
  - clicking selects the right SKU / shelf (`ui.store`) and filters the timeline by correlation; "Show all" clears the filter
  - `fail("…")` shows the unavailable notice and keeps the last list; `setAll` clears it
  - Simulation view: shows the "describes Live" note and no list
  - a SKU missing from the twin: the item cannot be selected and is labeled
- Updated: `scene/anomaly.test.tsx`, `ProductDetails.test.tsx`, `fixtures/demo/demo.test.ts` (types match the shelf figures, there is one opportunity, every severity on a stocked product, P003 correlates with the demo run), `devSources.test.ts`, `simulationBinding.test.tsx`.

Commands (in `apps/web`, the same as CI `web.yml`):
- `npm test`
- `npm run build` (`tsc --noEmit` + `vite build`: the project's type check; there is no separate linter)
- `npm run test:coverage`
- Manual: `npm run dev` → `/?twin=demo`, `twin.agentRun()` in the console; check that the P003 alert moves through its steps, clicking it flies the camera there, and the timeline filters.

Issue acceptance criteria, expected:
- [x] (FE) Alert / Opportunity UI with severity, status, SKU / shelf link, lifecycle; selecting focuses 3D
- [ ] (E2E) "Publish demand spike → alert appears without prompt" needs BE: detector → `anomalies`, `correlation_id`, + #95. Left open, PR uses `Refs #38`.
