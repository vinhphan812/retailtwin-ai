# Submission License Evidence Audit — Issue #367 (RetailTwin AI)

**Audit date:** 2026-10-25
**Auditor task:** `t_57fcdbdf` (board `retailtwin-ai`)
**Submission SHA under audit:** `920e166f3526947e66ced3644bed40e761a88133`
(`origin/main` HEAD, merge of PR #392 — the exact SHA deployed to Cloud Run as revision
`retailtwin-api-00053-6k7`, image `gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:9eae4b6e2a9557c253f7cb328c52e2eb384b835da2728a17a71d5133410d564a`).

---

## 1. Headline result

**At the exact submission SHA there is NO licence file and NO third-party notice file in the
repository.** Competition requirement **CR12 "License declared" is NOT satisfied at the
submission SHA**. The MIT licence text and the third-party notice exist only on two **open,
unmerged** pull requests and are therefore not part of the submitted tree.

The licence material that does exist on the open PRs is accurate, complete and internally
consistent for the material it covers. Three unresolved compliance questions remain (see §7),
one of which is a genuine obligation gap in the distributed container image.

---

## 2. Authoritative licence file — what exists and where

### 2.1 At the submission SHA `920e166f` — ABSENT

```
$ git ls-tree --name-only 920e166f3526947e66ced3644bed40e761a88133
.dockerignore  .env.example  .firebaserc  .github  .gitignore
CHANGELOG.md  Dockerfile  README.md  VERSION
apps  assets  contracts  data  docs  firebase.json  g02-evidence.json
infrastructure  scripts  services  tests
```

* No `LICENSE`.
* No `THIRD_PARTY_NOTICES.md` (nor any `NOTICE*` / `COPYING*`).
* The only licence-shaped files in the whole tree are the eleven bundled 3D asset
  `License.txt` files under `apps/web/public/models/<pack>/License.txt`.

Corroborating state at the same SHA:

| Evidence | Value | Source |
|---|---|---|
| README `## License` section | "This repository does not currently declare a license file. Add the chosen license at the repository root before public release." | `git show 920e166f:README.md` (lines 167–169) |
| Submission checklist CR12 | `| CR12 | License declared | README says "does not currently declare a license" | 🔴 MISSING |` | `git show 920e166f:docs/FINAL_SUBMISSION_VALIDATION_CHECKLIST.md` (line 231) |
| Checklist summary | "**Competition requirements (CR01–CR12):** 2 confirmed, 1 missing (license), rest 🟡/🔴" | same file, line 250 |
| GitHub repo license metadata | `licenseInfo: null`; `GET /repos/…/license` → HTTP 404 | `gh repo view` / GitHub REST API, 2026-10-25 |
| Issue #367 body | "License declared: NO (missing)"; deliverable "LICENSE file committed" unticked | `gh issue view 367` |

**Judges inspecting the public repository at the submitted SHA see no licence at all**, and
GitHub's own licence detector reports none.

### 2.2 On the open pull requests — PRESENT, MIT

| Item | Value |
|---|---|
| Licence identifier | **MIT License** (SPDX: `MIT`) |
| Copyright line | `Copyright (c) 2026 RetailTwin AI Contributors` |
| File path | `LICENSE` (repository root) |
| Blob SHA (git) | `45b8da20817cb3ae9926b65c8d831ed88db9d23f` |
| Content SHA-256 | `1d1e0b4b81b98b360932a440d6857c5f182e8392b18a8058ed4862a0e778f4c7` |
| Size | 1083 bytes / 21 lines |
| Third-party notice | `THIRD_PARTY_NOTICES.md` (repository root) — blob `29dfe959868e3724094fdaf1bd20052199dc2e48`, 5466 bytes |
| PR #398 (primary candidate) | head `ebb70b646f48365bfbb724df71170a09e85442cf`, branch `retailtwin-ai/t_225ec2bc-issue-367-final-submission-validation-ch`, state OPEN, mergeable CLEAN, exact-head CI green (API Build & Test, API E2E Smoke, Web Build & Test, Repository Hygiene, No conflict markers, Canonical Version Consistency pass; Container image scan + Secrets scan skipped — docs-only path filter) |
| PR #397 (duplicate) | head `4fae32dea25c43d4af2fd49d86da11f03fb1e172`, branch `docs/pr-388-evidence-only`, state OPEN, exact-head CI green |
| Identity check | `LICENSE` and `THIRD_PARTY_NOTICES.md` blobs are **byte-identical on both PRs** (same git blob SHAs and same content SHA-256). No licence-text conflict between them. |

Both PRs also update `README.md` (`## License` → "This repository is licensed under the
[MIT License](LICENSE).") and the checklist CR12 row to `🟢 DECLARED` with evidence text
naming `LICENSE` and `THIRD_PARTY_NOTICES.md`.

> ⚠️ **Duplicate-delivery hazard (owner decision, already flagged on `t_225ec2bc`):** PR #397 and
> PR #398 both add `LICENSE` and `THIRD_PARTY_NOTICES.md` with identical content. **Only one may
> be merged.** Both also add overlapping `docs/evidence/submission-gates/2026-10-22T1556Z/` gate
> evidence, so merging both creates a duplicate-evidence tree.

> ⚠️ **Transient inconsistency resolved at head:** the earlier commit `95b1ab5c` added `LICENSE`
> but left README saying "does not currently declare a license file". That was corrected in
> `49ae9f31` / `ebb70b64`; the PR #398 head is internally consistent.

---

## 3. Required notices / obligations identified

`THIRD_PARTY_NOTICES.md` (PR #398 head) records three obligation classes. All three were
independently re-verified against the tree at the submission SHA.

### 3.1 Bundled 3D asset packs — CC0 1.0, no attribution owed

Eleven packs are committed under `apps/web/public/models/`. Each directory contains exactly one
upstream `License.txt`, reproduced verbatim:

| Pack | Author / distributor | Upstream licence | Local path |
|---|---|---|---|
| Car Kit (3.1) | Kenney | CC0 1.0 | `apps/web/public/models/kenney-car-kit/` |
| City Kit Commercial (2.1) | Kenney | CC0 1.0 | `apps/web/public/models/kenney-city-commercial/` |
| City Kit Roads (2.2) | Kenney | CC0 1.0 | `apps/web/public/models/kenney-city-roads/` |
| City Kit Suburban (2.0) | Kenney | CC0 1.0 | `apps/web/public/models/kenney-city-suburban/` |
| Food Kit (2.0) | Kenney | CC0 1.0 | `apps/web/public/models/kenney-food/` |
| Furniture Kit (2.0) | Kenney | CC0 1.0 | `apps/web/public/models/kenney-furniture/` |
| Mini Market Kit | Kenney | CC0 1.0 | `apps/web/public/models/kenney-mini-market/` |
| Nature Kit (2.1) | Kenney | CC0 1.0 | `apps/web/public/models/kenney-nature/` |
| Low Poly Vehicles Pack | Daniel Quevedo | CC0 1.0 | `apps/web/public/models/quevedo-vehicles/` |
| Snackies | The Loafbrr | CC0 1.0 | `apps/web/public/models/snackies/` |
| House Plants | Tiny Treats (Isa Lousberg) | CC0 1.0 | `apps/web/public/models/tinytreats/` |

Verification performed:
* All eleven `License.txt` files at `920e166f` were read; every one carries an explicit
  CC0 / "Creative Commons Zero" / "public domain" dedication. No pack carries a
  share-alike, attribution-required, or non-commercial term.
* Two derivative disclosures are present and correct: `quevedo-vehicles/bus.glb` is documented as
  a converted/recoloured derivative of upstream `Bus.fbx`; `tinytreats/` lists per-file Poly
  Pizza source URLs.
* Kenney's own text states crediting is **"not a requirement"**, so the MIT grant may cover
  these files without an attribution duty.
* **Distribution path confirmed live:** all eleven `License.txt` files are served from the
  production Firebase Hosting site — `GET https://retailtwin-ai-511002.web.app/models/<pack>/License.txt`
  → **HTTP 200** for all eleven packs (2026-10-25). The upstream terms therefore travel with the
  redistributed binaries.

### 3.2 Third-party software dependencies — not vendored

No third-party source code is copied into the repository tree (verified: no `vendor/`,
`third_party/`, `node_modules/` or bundled dependency source in `git ls-tree -r 920e166f`;
only first-party `apps/`, `services/`, `scripts/`, `contracts/`, `data/`).
Dependencies are resolved at build/install time from upstream registries and retain their own
licences.

* **JavaScript/TypeScript** — `apps/web/package.json` + committed `apps/web/package-lock.json`
  (1316 packages) and `apps/web/pnpm-lock.yaml`.
  Licence distribution across the lockfile: MIT 977 · Apache-2.0 187 · ISC 74 · BSD-3-Clause 33 ·
  MPL-2.0 12 · BSD-2-Clause 10 · BlueOak-1.0.0 9 · Python-2.0 2 · 0BSD 2 · MIT-0 1 ·
  CC-BY-4.0 1 · public domain 1 · CC0-1.0 1 · compound (BSD-2/MIT/Apache) 1 ·
  (MIT OR CC0-1.0) 1 · BSD 1.
  * All eleven **runtime** dependencies are MIT: `@heroui/react`, `@react-three/drei`,
    `@react-three/fiber`, `framer-motion`, `i18next`, `react`, `react-dom`, `react-i18next`,
    `react-router`, `three`, `zustand`.
  * The 12 MPL-2.0 entries (`lightningcss*`) and the 1 CC-BY-4.0 entry (`caniuse-lite`) are
    **devDependencies**. They are **absent from the served production bundle** — grep over the
    live chunks `index-D8uGJXnc.js`, `r3f-CTBnF4LB.js`, `three-Id9b4xN8.js`, `ui-D2XMZhda.js`
    for `lightningcss` and `caniuse` returned 0 hits in every chunk.
  * Three lockfile entries carry **no `license` field**: `fuzzy@0.1.3` (dev),
    `valid-url@1.0.9` (dev), `webgl-constants@1.1.1` (runtime, via `three`). Upstream tarballs
    were downloaded and inspected: `fuzzy` ships `LICENSE-MIT` (MIT, Matt York);
    `valid-url` ships an MIT `LICENSE` (Odysseas Tsatalos / oDesk);
    `webgl-constants` ships an MIT `LICENSE` (Tim van Scherpenzeel). All three are MIT.
  * In-band licence headers survive the production build for the bundled third-party code:
    `three-Id9b4xN8.js` carries `/** @license Copyright 2010-2024 Three.js Authors
    SPDX-License-Identifier: MIT */`; `r3f-CTBnF4LB.js` carries `Copyright (c) Facebook, Inc.
    and its affiliates.` (react-three — MIT). `react-D3-mXIO.js` is currently **not served as
    JavaScript** (HTTP 200 but `content-type: text/html`, 698 bytes — the SPA fallback); the
    React chunk referenced by `index.html` is therefore not actually being delivered. This is a
    deployment-integrity observation, not a licence defect, but it is recorded because it
    affects whether the React licence header is reachable by a judge.
* **Python** — `apps/api/pyproject.toml` + committed `apps/api/uv.lock` (68 packages).
  `uv.lock` carries **no licence metadata** (0 occurrences of `license`), so the lockfile cannot
  be used as licence evidence. In the deployed image, however, the resolved wheels do carry
  their upstream texts: **118 upstream `LICENSE*` files under `*.dist-info/licenses/`** inside
  `/app/.venv` (verified inside the live digest `9eae4b6e…`), including Apache-2.0 texts for
  `google_cloud_pubsub`, `google_auth`, `grpcio`, `googleapis_common_protos`, and a `NOTICE`
  for `requests`. The only `dist-info` without a licence file is the project's own
  `retailtwin_api-0.1.0.dist-info` — i.e. first-party code, correctly carrying the repo's own
  grant instead.

### 3.3 First-party code — MIT

All first-party source, docs, scripts, tests and workflows would be covered by the root MIT
grant once merged. `THIRD_PARTY_NOTICES.md` scopes this correctly: "The `LICENSE` file at the
repository root applies to the first-party code only."

---

## 4. Internal consistency check — PASS at the PR heads

| Check | PR #398 head `ebb70b64` | PR #397 head `4fae32de` |
|---|---|---|
| `LICENSE` present at root, MIT text intact | ✅ blob `45b8da20` | ✅ identical blob |
| `THIRD_PARTY_NOTICES.md` present at root | ✅ blob `29dfe959` | ✅ identical blob |
| README `## License` links to `LICENSE` | ✅ "This repository is licensed under the [MIT License](LICENSE)." | ✅ same |
| Checklist CR12 evidence text names `LICENSE` + `THIRD_PARTY_NOTICES.md` | ✅ | ✅ |
| Checklist CR12 status | ✅ `🟢 DECLARED` | ✅ `🟢 DECLARED` |
| Checklist summary line consistent with row | ✅ "license declared; deployment-dependent requirements remain 🟡/🔴" | ✅ same |
| `THIRD_PARTY_NOTICES.md` asset table matches the 11 on-disk packs, paths, authors, licences | ✅ all 11 verified | ✅ identical file |
| Notice scope statement honest about limits | ✅ explicitly states upstream URLs / chain of title were **not** re-verified offline | ✅ same |
| No licence claim in the notice about the submission gate / deployment | ✅ explicitly disclaims | ✅ same |

**No internal contradiction found in the licence material on either PR head.**

---

## 5. Suitability for distribution — ONE REAL GAP + TWO OBSERVATIONS

### 5.1 🔴 GAP — the distributed container image ships no MIT notice and no third-party notice

`.dockerignore` at `920e166f` excludes the licence material from the build context:

```
7: README.md
8: LICENSE
9: CONTRIBUTING.md
12: *.md
```

The `Dockerfile` copies `apps/api/`, `data/`, `services/` and `VERSION` into `/app` — i.e. the
image redistributes **substantial portions of the MIT-licensed first-party source** — but copies
no licence text.

Verified inside the live image `gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:9eae4b6e…`:

```
$ docker run --rm --entrypoint sh <image> -c 'ls -la /app; find / -maxdepth 5 -iname "LICENSE*" -o -iname "NOTICE*"'
/app: .venv  VERSION  apps  data  services      ← no LICENSE, no NOTICE
/usr/local/lib/python3.11/LICENSE.txt             ← CPython base-image licence only
```

(The only `LICENSE*` file in the image is the CPython interpreter licence that ships with the
base image.)

**Obligation:** MIT requires that "The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software." The container ships substantial
portions of the Software without the MIT notice. The same applies to the source-form web
artefacts: the Firebase `dist` carries no repository-level `LICENSE` or
`THIRD_PARTY_NOTICES.md` — `GET https://retailtwin-ai-511002.web.app/LICENSE` returns the SPA
`index.html` (HTTP 200, `text/html`), not a licence file. (The eleven CC0 asset notices *are*
served correctly.)

**Remediation (one-line class of fix):** stop excluding `LICENSE` from the Docker build context
and copy it into `/app`, and publish `LICENSE` + `THIRD_PARTY_NOTICES.md` as static files under
`apps/web/public/` so Vite copies them into `dist`. Filed as follow-up card `t_1f0a4c2e`.

*Interpretation caveat, stated rather than silently resolved:* whether the container image counts
as a "copy" requiring the notice is a legal judgement, not a build fact. The safest reading is
that it does, because the image contains the first-party source verbatim. This is flagged for
the maintainer/owner rather than decided unilaterally.

### 5.2 🟡 OBSERVATION — no contributor-authority record (blocks CR12 sign-off)

The MIT text asserts `Copyright (c) 2026 RetailTwin AI Contributors`. The repository has **no
CLA, no CONTRIBUTING file, no copyright-holder statement and no governance document**
(`git ls-tree -r 920e166f` → no `CLA*`, `CONTRIBUTING*`, `AUTHORS*`, `COPYRIGHT*`), and
`git shortlog -sne 920e166f` shows **ten distinct human contributors** plus bot/agent accounts
(Vinh Phan, Anh Nguyen, Khoa Pham ×2 identities, Phan Thanh Vinh, Trần Thanh Long ×2 identities,
Hermes agents, dependabot).

`THIRD_PARTY_NOTICES.md` covers *third-party* provenance but says **nothing** about whether every
contributor had authority to license their contributions under MIT. The reviewer already required
this ("License provenance remains unverified… do not represent CR12 as fully verified until that
evidence exists", `t_225ec2bc` comment, 2026-10-23). The `THIRD_PARTY_NOTICES.md` file added
since then does **not** close that gap — it is scoped to third-party material only.

**Unresolved compliance question (owner input required):** confirm in writing that the
repository owner (Vinh Phan, sole GitHub owner of `vinhphan812/retailtwin-ai`) holds authority
to grant MIT over all contributions, or obtain equivalent confirmation from the other human
contributors. Until then CR12 cannot be marked 🟢 **VERIFIED** even after merge — only
🟢 **DECLARED**.

### 5.3 🟡 OBSERVATION — `uv.lock` carries no licence metadata

`apps/api/uv.lock` has zero licence fields, so it is not usable as dependency-licence evidence
and CI cannot machine-check Python dependency licences from it. The deployed image does retain
the upstream texts (118 files), so distribution is covered in practice; only the *lockfile-as-
evidence* route is missing.

### 5.4 ℹ️ OBSERVATION — CR12 wording drift between PR head and submission SHA

The checklist on the PR heads states CR12 🟢 DECLARED. That statement is only true **once the PR
is merged**. On the submission SHA `920e166f` the same row is 🔴 MISSING and is internally
consistent with the tree. Any sign-off artefact that cites "CR12 DECLARED" must cite the
post-merge SHA, not `920e166f`.

---

## 6. Evidence index

| # | Claim | Evidence |
|---|---|---|
| E1 | No `LICENSE` at submission SHA | `git ls-tree --name-only 920e166f` — no LICENSE entry |
| E2 | No `THIRD_PARTY_NOTICES.md` at submission SHA | same command; `git ls-tree -r --name-only 920e166f \| grep -i notice` → empty |
| E3 | README states no licence declared | `git show 920e166f:README.md` lines 167–169 |
| E4 | Checklist CR12 = 🔴 MISSING at submission SHA | `git show 920e166f:docs/FINAL_SUBMISSION_VALIDATION_CHECKLIST.md` line 231 |
| E5 | GitHub detects no licence | `gh repo view vinhphan812/retailtwin-ai --json licenseInfo` → `null`; `GET /repos/vinhphan812/retailtwin-ai/license` → 404 (2026-10-25) |
| E6 | MIT `LICENSE` blob + SHA-256 | blob `45b8da20…`, SHA-256 `1d1e0b4b…84f4c7`, 1083 B, identical on PR #397 and #398 heads |
| E7 | `THIRD_PARTY_NOTICES.md` blob | `29dfe959…`, 5466 B, identical on PR #397 and #398 heads |
| E8 | PR #398 head + CI | `ebb70b646f48365bfbb724df71170a09e85442cf`; `gh pr checks 398` → 7 pass, 2 skipped (docs-only filter) |
| E9 | PR #397 head + CI | `4fae32dea25c43d4af2fd49d86da11f03fb1e172`; `gh pr checks 397` → 7 pass, 2 skipped |
| E10 | 11 × CC0 asset licences | `head`/`grep` of all `apps/web/public/models/*/License.txt` at `920e166f`; each states CC0 |
| E11 | Asset notices served in production | `curl` → HTTP 200 for all 11 `https://retailtwin-ai-511002.web.app/models/<pack>/License.txt` (2026-10-25) |
| E12 | JS licence distribution + runtime set | `apps/web/package-lock.json` parsed (1316 packages); all 11 runtime deps MIT |
| E13 | MPL-2.0 / CC-BY-4.0 not in shipped bundle | grep `lightningcss` / `caniuse` over live chunks → 0 hits in all 5 chunks |
| E14 | 3 lockfile entries without licence field are MIT | npm tarball inspection: `fuzzy` `LICENSE-MIT`; `valid-url` MIT `LICENSE`; `webgl-constants` MIT `LICENSE` (Tim van Scherpenzeel) |
| E15 | Python deps carry upstream licences in the image | `docker run` on `sha256:9eae4b6e…`: 118 `*.dist-info/licenses/LICENSE*`; Apache-2.0 texts for pubsub/google-auth/grpcio/common-protos; `requests` NOTICE present |
| E16 | Container ships no first-party licence | `docker run … ls -la /app` → no LICENSE/NOTICE; only `/usr/local/lib/python3.11/LICENSE.txt` (CPython) |
| E17 | `.dockerignore` excludes `LICENSE` and `*.md` | `git show 920e166f:.dockerignore` lines 7–12 |
| E18 | Web hosting serves no repository licence | `curl https://retailtwin-ai-511002.web.app/LICENSE` → 200 `text/html` (SPA `index.html`) |
| E19 | `uv.lock` has no licence metadata | `git show 920e166f:apps/api/uv.lock \| grep -c license` → 0 |
| E20 | No CLA / copyright-holder record; 10 human contributors | `git ls-tree -r 920e166f` (no CLA/CONTRIBUTING/AUTHORS); `git shortlog -sne 920e166f` |
| E21 | In-band third-party headers in production bundle | `three-Id9b4xN8.js` → `@license … Three.js Authors … MIT`; `r3f-CTBnF4LB.js` → `Copyright (c) Facebook, Inc.` |
| E22 | React chunk not served as JS | `GET /assets/react-D3-mXIO.js` → 200 but `content-type: text/html`, 698 B (SPA fallback) |

---

## 7. Discrepancies and unresolved compliance questions (explicit, not interpreted away)

1. **CR12 unsatisfied at the submission SHA.** `920e166f` has no licence. The MIT text and the
   notice exist only on open PRs #397 and #398. Until one is merged and a new submission SHA is
   built and deployed, the submitted artefact is unlicensed.
2. **Two PRs carry the same licence material.** Byte-identical `LICENSE` and
   `THIRD_PARTY_NOTICES.md` blobs. **Exactly one may be merged.** The choice between #397 and
   #398 (and the associated duplicate `docs/evidence/…` gate-evidence trees) is an owner
   decision — PR #398 is the one that carries the consolidated
   `docs/evidence/submission-gates/2026-10-22T1556Z/` tree and a `SHA256SUMS.txt` manifest, and
   is the task lineage's designated canonical delivery.
3. **No contributor-authority record.** Ten human contributors, no CLA, no copyright-holder
   statement, no governance file. The MIT grant's authority is unverified. **Owner confirmation
   required**; `THIRD_PARTY_NOTICES.md` does not cover this.
4. **MIT notice not included in the distributed container image** (nor in the hosted web
   artefact). `.dockerignore` strips `LICENSE` and `*.md`; the image ships first-party source
   without the notice. Flagged as an obligation gap with the legal-judgement caveat in §5.1.
   Remediation is mechanical but the change is not made unilaterally by an audit card.
5. **Shipped web bundle ships the CC0 asset notices but not the repository licence**, and the
   React vendor chunk currently resolves to the SPA HTML fallback rather than JavaScript
   (E22) — judges following the bundle licence headers will not find React's header.
6. **`uv.lock` carries no licence metadata**, so Python dependency licences cannot be verified
   from the lockfile (only from the built image).
7. **No CI check enforces licence presence or licence consistency.** `git grep -ni licen
   920e166f -- .github` → no matches. Nothing in CI would have caught the missing `LICENSE` at
   `920e166f`, and nothing will prevent a future regression. A minimal `CR12` guard (root
   `LICENSE` exists, README links it, `THIRD_PARTY_NOTICES.md` present, every bundled asset
   directory has a `License.txt`) would close the loop cheaply.

---

## 8. Recommended remediation order

1. Owner selects the canonical licence delivery — **PR #398** (`ebb70b64`) — and closes PR #397
   to remove the duplicate evidence tree. *(owner decision)*
2. Owner records contributor-authority confirmation for the MIT grant (CLA or written
   confirmation covering the human contributors). *(owner decision)*
3. Merge the licence PR → new `main` SHA; **the submission SHA changes** and the Cloud Run
   deployment must be redone at the new SHA (the current live revision
   `retailtwin-api-00053-6k7` serves `920e166f`, which has no licence).
4. Ship `LICENSE` (+ `THIRD_PARTY_NOTICES.md`) inside the container image and into the web
   `dist` — follow-up card `t_1f0a4c2e` (dev-ops).
5. Add a CI licence-presence/consistency guard so CR12 cannot silently regress.
6. Only then mark CR12 🟢 **VERIFIED** in the checklist, citing the post-merge SHA and the
   revision that serves it.

---

*Prepared by `t_57fcdbdf` (coordinator) against `origin/main` @ `920e166f3526947e66ced3644bed40e761a88133`,
PR #398 @ `ebb70b646f48365bfbb724df71170a09e85442cf`, PR #397 @ `4fae32dea25c43d4af2fd49d86da11f03fb1e172`,
live image `sha256:9eae4b6e2a9557c253f7cb328c52e2eb384b835da2728a17a71d5133410d564a`, and live hosts
`retailtwin-ai-511002.web.app` / `retailtwin-api-5rgtvr4gpa-uc.a.run.app`, all probed 2026-10-25.*
