# Simulations 500 — ADC token header-case fix: verification record

Kanban task: `t_d8476d4b` (parent), implementation sub-task `t_c1da341d`, review `t_aebc024f`.
Date: 2026-10-25.

## 1. Root cause

`google-auth`'s compute-engine metadata transport reads response headers case-insensitively:

```python
# google/auth/compute_engine/_metadata.py
_helpers.parse_content_type(response.headers["content-type"])   # line 392
metadata_flavor = response.headers.get(_METADATA_FLAVOR_HEADER)   # line 232
```

The GCE metadata server answers with canonical `Content-Type` casing. The stdlib-`urllib` ADC
transport used by the application built its response headers with `dict(response.headers)`, which
preserves the original casing and is **case-sensitive**. The lowercase lookup therefore raised
`KeyError: 'content-type'` during every ADC refresh.

Consequences:

- `google.auth.default(scopes=["https://www.googleapis.com/auth/datastore"])` itself succeeds —
  it returns a compute-engine `Credentials` object. ADC availability, the service account
  `retailtwin-api@retailtwin-ai-511002.iam.gserviceaccount.com` and its `roles/datastore.user`
  binding are all fine.
- The failure occurs later, in `credentials.refresh(request)`, inside the metadata HTTP call.
- `firestore_decisions._ApplicationDefaultTokenProvider` catches the exception and raises
  `DecisionStoreUnavailable`; `firestore_simulations._call` re-raises it as
  `SimulationStoreUnavailable("Simulation-store access token unavailable: DecisionStoreUnavailable")`,
  which the route surfaces as HTTP 500.

Why only the simulations path fails: `firestore_twin.py` (the `/store`, `/inventory` path) refreshes
through `google.auth.transport.requests.Request()`, whose `requests`-backed response exposes
`requests.structures.CaseInsensitiveDict`, so `headers["content-type"]` resolves. The
decisions/simulations/agent-activity/activation-ledger path uses the stdlib `urllib` transport and
does not.

Ruled out (not the cause):

| Hypothesis | Verdict | Evidence |
| --- | --- | --- |
| Service account lacks `roles/datastore.user` | Ruled out | The SA already holds `roles/datastore.user`; ADC returned a valid compute-engine credential. |
| Missing ADC file / metadata server unreachable | Ruled out | `google.auth.default()` succeeded against the metadata server; only `refresh()` failed. |
| Missing `gcloud auth print-access-token` fallback (suggested in the card) | Irrelevant on Cloud Run | Cloud Run has no `gcloud` on `PATH`; the metadata server *is* the ADC source there. The fallback is a local-dev convenience, not the production path. |
| Regression introduced by a recent change | Ruled out | `firestore_simulations.py` and `firestore_decisions.py` are byte-identical between the old and new serving images, and the same 500 is logged for revision `retailtwin-api-00032-zn4` on 2026-10-19. |

## 2. The fix

`apps/api/retailtwin_api/http_headers.py` (new) — `CaseInsensitiveHeaders`, a stdlib-only,
read-only `Mapping[str, str]`:

- keys matched case-insensitively (normalised to lowercase for lookup);
- original casing preserved on iteration, mirroring `requests.structures.CaseInsensitiveDict`;
- `__getitem__`, `get` and `__contains__` all case-insensitive;
- a missing key raises `KeyError` with the *requested* name.

Applied at both `_UrllibAuthResponse` implementations:

```python
self.headers = CaseInsensitiveHeaders(headers)
```

- `apps/api/retailtwin_api/firestore_twin.py`
- `apps/api/retailtwin_api/firestore_decisions.py`

No transport switch, no new dependency, no change to provider selection, IAM or Google
authentication behaviour.

## 3. Regression coverage

### 3.1 Unit level — `apps/api/tests/test_adc_header_case_insensitive.py` (12 tests)

Drives the real `google.auth.compute_engine._metadata.get()` path against the urllib transport with
a canonical `Content-Type` response header.

RED (wrapper reverted to `self.headers = headers`):

```
FAILED ...::TestUrllibAuthResponseHeaders::test_response_headers_are_case_insensitive[_UrllibAuthRequest0]
FAILED ...::TestUrllibAuthResponseHeaders::test_response_headers_are_case_insensitive[_UrllibAuthRequest1]
FAILED ...::TestUrllibAuthResponseHeaders::test_error_response_headers_are_case_insensitive[_UrllibAuthRequest0]
FAILED ...::TestUrllibAuthResponseHeaders::test_error_response_headers_are_case_insensitive[_UrllibAuthRequest1]
FAILED ...::test_google_auth_metadata_lookup_resolves_with_canonical_casing
5 failed, 7 passed
```

GREEN: `12 passed, 1 warning in 0.53s`.

### 3.2 Endpoint level — `apps/api/tests/test_simulations_adc_metadata_reproduction.py` (2 tests)

Exercises the whole production chain against local emulators rather than mocking the application
layer:

- a **GCE metadata-server emulator** answering with canonical `Content-Type` / `Metadata-Flavor`
  casing (the actual production condition);
- a **Firestore REST stub** serving one simulation document (`sim-seed-001`);
- the **real** `google.auth` compute-engine credential, refreshed through the **real**
  `firestore_decisions._UrllibAuthRequest` transport;
- the **real** `FirestoreSimulationRepository` and the **real** FastAPI routes.

ADC source pinning: `google.auth.default` is patched to resolve the compute-engine credential only,
`CLOUDSDK_CONFIG` is pointed at an empty directory (so no ambient Cloud SDK ADC file is discovered)
and `GOOGLE_APPLICATION_CREDENTIALS` is removed. This makes the test deterministic on a developer
machine and matches Cloud Run, where no ADC file exists.

| Test | Asserts |
| --- | --- |
| `test_list_and_detail_return_200` | With the fix: `GET /simulations` and `GET /simulations/sim-seed-001` both return **200**, `total == 1`, and the metadata-server token reaches Firestore as `Bearer <token>` on every request. |
| `test_case_sensitive_response_headers_reproduce_the_500` | With the pre-fix plain-`dict` headers: both routes return **500** — the exact production failure. |

RED at the endpoint level, with the pre-fix sources restored from `origin/main`:

```
$ git checkout origin/main -- apps/api/retailtwin_api/firestore_twin.py \
                            apps/api/retailtwin_api/firestore_decisions.py
$ pytest tests/test_simulations_adc_metadata_reproduction.py -q
FAILED tests/test_simulations_adc_metadata_reproduction.py::TestSimulationsEndpointWithMetadataServer::test_list_and_detail_return_200
1 failed, 1 passed, 1 warning in 1.61s
```

GREEN with the fix restored:

```
$ pytest tests/test_simulations_adc_metadata_reproduction.py tests/test_adc_header_case_insensitive.py -q
14 passed, 1 warning in 1.67s
```

### 3.3 Focused API suite

```
$ pytest tests/test_simulations_adc_metadata_reproduction.py tests/test_adc_header_case_insensitive.py \
           tests/test_firestore_simulations.py tests/test_firestore_decisions.py \
           tests/test_firestore_twin.py tests/test_simulation_routes.py tests/test_simulation.py -q
166 passed, 1 warning in 6.53s
```

## 4. Delivery

| | |
| --- | --- |
| Branch | `fix/simulations-adc-token-header-case` |
| Base | `origin/main` @ `920e166f3526947e66ced3644bed40e761a88133` |
| Head SHA | `7814a3e9af22f504d961e8c01f343f3879690770` |
| Fix commit | `5d98f4bb` (content byte-identical to `6be263b9229af40e0033965e03cb5b404b481004`, the head of PR #414) |
| Test commit | `7814a3e9` — endpoint-level reproduction test |
| PR | https://github.com/vinhphan812/retailtwin-ai/pull/415 (OPEN, MERGEABLE) |
| Supersedes | PR #414 (same fix on a `wt/...` branch); #414 has been commented with the pointer to #415 |
| Diff | 5 files, +676 / −2 |
| IAM changes | none |

Base-branch note: the delivery policy names `master` as the target, but this repository has **no
`master` branch** — `origin/HEAD -> origin/main`, and `main` is the branch protected by the
required-check workflows. PR #415 therefore targets `main`, the repository's actual protected base.

### Changed files

```
 apps/api/retailtwin_api/firestore_decisions.py     |   9 +-
 apps/api/retailtwin_api/firestore_twin.py          |   8 +-
 apps/api/retailtwin_api/http_headers.py            |  61 +++++
 apps/api/tests/test_adc_header_case_insensitive.py | 245 +++++++++++++++++++++
 apps/api/tests/test_simulations_adc_metadata_reproduction.py | 355 +++++++++++++++++++++
 5 files changed, 676 insertions(+), 2 deletions(-)
```

## 5. CI evidence at head `7814a3e9`

```
API Build & Test              pass  9m17s
API E2E Smoke                 pass  1m27s
Build & Test                  pass  11m2s
Canonical Version Consistency pass  36s
Web Build & Test              pass  18s
Detect Changed Files          pass  19s
E2E Smoke                     pass  36s
Repository Hygiene            pass  20s
No conflict markers           pass  15s
```

`Type-check`, `Check branch coverage threshold` and `Enforce critical-path coverage policy` steps
also report `success`.

The authoritative test step (`Run tests with coverage`) reports:

```
apps/api/tests/test_adc_header_case_insensitive.py ............          [  2%]
apps/api/tests/test_simulations_adc_metadata_reproduction.py ..          [ 87%]
============ 1391 passed, 20 skipped, 3 warnings in 250.35s (0:04:10) ============
```

The later `Coverage summary` step re-runs `pytest` with the coverage plugin and reports
`4 failed, 1387 passed, 20 skipped`. Those 4 failures are **pre-existing on `main`** and unrelated —
a `ModuleNotFoundError: No module named 'tests.test_bigquery_sales_history'` collection artefact in
`tests/test_investigator.py`; the identical 4 failures appear on the `main` run for `920e166f`
(`run 39894366821`, 2026-10-23). That step does not gate the job.

Locally (Windows) the full suite reports `1385 passed, 20 skipped, 4 failed`. The 4 local failures
are Windows-environment issues (shell-script executability checks in `tests/test_day0_smoke.py` and a
publisher-cache test in `tests/test_backbone_gcp_pipe.py`) that reproduce identically on a clean
tree with the change stashed.

## 6. Live production status and limitations

The live service still returns **500** on both simulation routes, because the fix is not deployed:

```
500  https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/simulations
500  https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/simulations/sim-seed-001
```

Limitations:

- **No production deployment was made or authorised.** Acceptance criterion 3 is satisfied via the
  faithful local reproduction (section 3.2), which returns 200 on both routes; the live endpoint
  cannot return 200 until #415 is merged and deployed.
- The local reproduction uses emulators for the GCE metadata server and the Firestore REST API. The
  ADC path (`google.auth.compute_engine`), the urllib auth transport, the Firestore repository and
  the FastAPI routes are the real production code.
- The reproduction asserts a single simulation document (`sim-seed-001`) and no decision record, so
  the response stays in the "no decision" state; it exercises the token path, not Firestore
  query semantics.
- The 4 CI `Coverage summary` failures are pre-existing on `main` and are not addressed by this
  change (they belong to `tests/test_investigator.py` collection, outside this defect's scope).
