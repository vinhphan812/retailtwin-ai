# Contributor Licence Provenance — CR12

**Scope:** the authority basis on which the contributions in this repository are covered by the
MIT licence grant asserted in the root `LICENSE` file.

**Status:** `OPEN — INCOMPLETE BY DESIGN`
The record below states what is evidenced in the repository and what is not. No confirmation is
asserted that the repository does not hold.

**Submission SHA referenced throughout:** `920e166f3526947e66ced3644bed40e761a88133`
(`origin/main` HEAD at the time of writing — 386 commits, 29 merges, first commit
`76fbf91ee8c5d69ea589381aa32bdfff081b7641` dated 2026-10-07).

**Related records:**

- `docs/FINAL_SUBMISSION_VALIDATION_CHECKLIST.md` — §6.1 "Licence evidence (CR12)" and row CR12.
- `THIRD_PARTY_NOTICES.md` — third-party provenance only. **It does not address contributor
  authority** and must not be read as doing so.
- Audit `t_57fcdbdf`, report `LICENSE-EVIDENCE-AUDIT-2026-10-25.md` — §2, §3, §5.2, §7.

---

## 1. What this record is, and what it is not

**It is** a per-identity account, derived from git history, of the basis on which each
contributor's contributions are covered by the MIT grant.

**It is not** a confirmation. Where the repository holds no evidence that a contributor
authorised the MIT grant over their contributions, this record says so and leaves the item
open for the repository owner. No contributor has been asked, and no answer has been
fabricated, assumed, or inferred on their behalf.

**It does not change the licence itself.** The licence text lives in the root `LICENSE` file and
is owned by the open licence pull requests (see §2). This record neither authors nor alters it.

---

## 2. Authoritative licence material — and where it is bound

The MIT text referenced by this record is **not present in the tree at the submission SHA**. It
exists only on two open, unmerged pull requests, with byte-identical blobs.

| Item | Value |
|---|---|
| Licence identifier | MIT License (SPDX `MIT`) |
| Copyright line | `Copyright (c) 2026 RetailTwin AI Contributors` |
| Authoritative path | `LICENSE` (repository root) |
| Git blob SHA | `45b8da20817cb3ae9926b65c8d831ed88db9d23f` |
| Content SHA-256 | `1d1e0b4b81b98b360932a440d6857c5f182e8392b18a8058ed4862a0e778f4c7` |
| Size | 1083 bytes, 21 lines |
| Third-party notice | `THIRD_PARTY_NOTICES.md` (repository root) — blob `29dfe959868e3724094fdaf1bd20052199dc2e48`, 5466 bytes |
| Present at submission SHA `920e166f` | **No** — no root `LICENSE`, no root `THIRD_PARTY_NOTICES.md`, no `COPYING`/`NOTICE` |
| Carried by | PR #398 head `ebb70b646f48365bfbb724df71170a09e85442cf` (OPEN) — and PR #397 head `4fae32dea25c43d4af2fd49d86da11f03fb1e172` (OPEN), same blobs |

**Exactly one of PR #397 / PR #398 may be merged.** That choice is the repository owner's and is
not made by this record.

---

## 3. How this record was derived (re-runnable)

Every claim below traces to a command that can be re-run against the submission SHA.

```bash
git shortlog -sne 920e166f3526947e66ced3644bed40e761a88133
git log --format='%an <%ae>' 920e166f3526947e66ced3644bed40e761a88133 | sort | uniq -c | sort -rn
git log --format='%cn <%ce>' 920e166f3526947e66ced3644bed40e761a88133 | sort | uniq -c | sort -rn
git log --format='%B' 920e166f3526947e66ced3644bed40e761a88133 | grep -iE '^signed-off-by' | sort | uniq -c | sort -rn
git log --format='%B' 920e166f3526947e66ced3644bed40e761a88133 | grep -iE '^co-authored-by' | sort | uniq -c | sort -rn
git ls-tree -r --name-only 920e166f3526947e66ced3644bed40e761a88133 \
  | grep -iE '(^|/)(CLA|CONTRIBUTING|AUTHORS|COPYRIGHT|GOVERNANCE)[^/]*$'
git ls-tree --name-only 920e166f3526947e66ced3644bed40e761a88133 \
  | grep -iE '^(LICENSE|THIRD_PARTY_NOTICES|COPYING|NOTICE)'

gh pr view 398 --repo vinhphan812/retailtwin-ai --json number,state,headRefOid,mergeable
gh pr view 397 --repo vinhphan812/retailtwin-ai --json number,state,headRefOid,mergeable
gh api repos/vinhphan812/retailtwin-ai/collaborators --jq '.[] | "\(.login) admin=\(.permissions.admin) push=\(.permissions.push)"'
gh api repos/vinhphan812/retailtwin-ai/license        # 404 at the default branch head (920e166f)
```

> **Reading the output.** The two `git ls-tree … | grep …` commands are expected to print
> **nothing** and exit **non-zero** at `920e166f` — that is `grep` reporting "no match", which is
> the documented finding (no `CLA`/`CONTRIBUTING`/`AUTHORS`/`COPYRIGHT`/`GOVERNANCE`, and no root
> licence or notice). `gh api repos/…/license` is likewise expected to fail with HTTP 404. A
> reviewer should treat **empty output plus a non-zero exit** as the pass condition for these
> three, not as a command error.

Resolving a commit identity to a GitHub account (used throughout §4):

```bash
c=$(git log --format='%H %ae' 920e166f | grep -F '<email>' | head -1 | cut -d' ' -f1)
gh api repos/vinhphan812/retailtwin-ai/commits/$c --jq '.author.login'
gh api users/<login> --jq '"login=\(.login) id=\(.id) name=\(.name) email=\(.email)"'
```

---

## 4. Contributor identities visible in git history

`git shortlog -sne 920e166f` yields **ten distinct author identities**. Six of them are human
commit identities; those six resolve to **four distinct GitHub accounts**. The remaining four
identities are bot or agent accounts (§6).

| # | Author identity (`%an <%ae>`) | Commits | First → last | GitHub account | Account role |
|---|---|---|---|---|---|
| 1 | `Phan Thanh Vinh <58102545+vinhphan812@users.noreply.github.com>` | 127 | 2026-10-07 → 2026-10-23 | `vinhphan812` (id 58102545, display name "Phan Thanh Vinh") | Repository owner — `admin=true`, `push=true` |
| 2 | `Vinh Phan <vinhphan812@gmail.com>` | 103 | 2026-10-12 → 2026-10-22 | `vinhphan812` (id 58102545) — **same account as #1** | Repository owner |
| 3 | `Anh Nguyen <ngocanh310301@gmail.com>` | 55 | 2026-10-08 → 2026-10-20 | `anh-nguyen-3103` (id 201216632) | Collaborator — `push=true`, `admin=false` |
| 4 | `Khoa Pham <71437539+k-pham08@users.noreply.github.com>` | 34 | 2026-10-10 → 2026-10-18 | `k-pham08` (id 71437539) | Collaborator — `push=true`, `admin=false` |
| 5 | `Khoa Pham <j.dangkhoa.118@gmail.com>` | 25 | 2026-10-07 → 2026-10-14 | `k-pham08` (id 71437539) — **same account as #4** | Collaborator |
| 6 | `Trần Thanh Long <at400123@gmail.com>` | 7 | 2026-10-13 → 2026-10-18 | `longshaww` (id 72122574, public email `at400123@gmail.com`) | Collaborator — `push=true`, `admin=false` |
| 7 | `Hermes Agent <agent@hermes>` | 12 | 2026-10-14 → 2026-10-15 | — (local agent identity) | Agent account |
| 8 | `Hermes Agent <hermes@nousresearch.com>` | 10 | 2026-10-19 | — (local agent identity) | Agent account |
| 9 | `RetailTwin Subagent <subagent@retailtwin.local>` | 5 | 2026-10-17 | — (local agent identity) | Agent account |
| 10 | `dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>` | 8 | — | `dependabot[bot]` | Bot account |

### 4.1 Correction to the audit's contributor count

Audit `t_57fcdbdf` §5.2 records "ten distinct human contributors plus bot/agent accounts". That
is not what the history shows. `git shortlog` returns ten author identities **in total**, of
which six are human identities, those six resolve to **four** GitHub accounts, and four are
bot/agent identities. The identity resolution is evidenced by the GitHub account IDs:

- `58102545+vinhphan812@users.noreply.github.com` → account id `58102545` = `vinhphan812`.
  The identity is the same GitHub account as `vinhphan812@gmail.com`.
- `71437539+k-pham08@users.noreply.github.com` → account id `71437539` = `k-pham08`.
  The identity is the same GitHub account as `j.dangkhoa.118@gmail.com`.
- `ngocanh310301@gmail.com` → `anh-nguyen-3103`; `at400123@gmail.com` → `longshaww`.

**Consequence for the owner action in §7:** the set of non-owner human contributors whose
authority must be confirmed is **three** — `anh-nguyen-3103` (Anh Nguyen), `k-pham08`
(Khoa Pham) and `longshaww` (Trần Thanh Long) — **not four**. "Phan Thanh Vinh" is the display
name on the repository owner's own account and needs no separate confirmation.

### 4.2 Attribution trailers present in the history

| Trailer | Count | Signers |
|---|---|---|
| `Signed-off-by` | 31 | `Vinh Phan <vinhphan812@gmail.com>` × 21, `dependabot[bot] <support@github.com>` × 8, `Hermes Coordinator <vinhphan812@gmail.com>` × 2 |
| `Co-authored-by` — human identities | 25 | `Vinh Phan <vinhphan812@gmail.com>` × 9, `Khoa Pham` across four spellings (`k-pham08@users.noreply.github.com` × 4, `j.dangkhoa.118@gmail.com` × 3, `k-pham08@users.noreply.github.com` × 1, `khoapham@users.noreply.github.com` × 1), `Trần Thanh Long <thanhlong.tran@giantgroup.com>` × 6, `Anh Nguyen <ngocanh310301@gmail.com>` × 1 |
| `Co-authored-by` — bot | 8 | `dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>` × 8 |
| `Co-authored-by` — AI tools and local agents | 163 | `Claude Opus 5.5` variants (`noreply@anthropic.com`) × 141, `Hermes Agent` variants × 14, `RetailTwin Subagent` × 4, `RetailTwin Agent` / `retailtwin-bot` / `recovery-bot` / `grok-build` × 4 |

Total `Co-authored-by` trailers: 196.

**No `Signed-off-by` trailer from any non-owner human contributor exists.** The DCO-style
sign-off present in the history comes from the owner and from `dependabot` only.

---

## 5. Authority basis, per contributor

"Authority basis" means the evidence in the repository that the identity held the right to
license the identified contributions under MIT, or the rights to have those contributions
licensed by the repository owner on their behalf.

| Identity / account | Authority basis evidenced in-repo | Status |
|---|---|---|
| `vinhphan812` — Phan Thanh Vinh / Vinh Phan (owner) | Repository owner and sole `admin`; author of all 23 "Merge pull request" merge commits at the submission SHA (the remaining 6 merges are branch synchronisations, not pull-request landings); author of the MIT text and the third-party notice on both open licence PRs; sole author of the human `Signed-off-by` trailers in the history. | **EVIDENCED** for the owner's own contributions (the owner holds copyright in them and grants them). **NOT EVIDENCED** for the authority to grant MIT over the *other* contributors' contributions — see §7. |
| `anh-nguyen-3103` — Anh Nguyen | 55 commits authored under the identity, landing on `main` via pull requests merged by the owner; account holds `push` on the repository; named once as a `Co-authored-by`. | **NOT EVIDENCED.** No CLA, no `CONTRIBUTING`, no `Signed-off-by`, no copyright-holder statement, no governance document. The repository holds no record of this contributor having authorised the MIT grant. |
| `k-pham08` — Khoa Pham | 59 commits across two identities, landing on `main` via pull requests merged by the owner; account holds `push`; named in 9 `Co-authored-by` trailers. | **NOT EVIDENCED** — same absence as above. |
| `longshaww` — Trần Thanh Long | 7 commits authored under the identity, landing on `main` via pull requests merged by the owner; account holds `push`; named in 6 `Co-authored-by` trailers under a second email (`thanhlong.tran@giantgroup.com`). | **NOT EVIDENCED** — same absence as above. |

### 5.1 What the "NOT EVIDENCED" rows mean

For the three non-owner human contributors the repository establishes three things and no more:

1. the contributions exist in this repository's history;
2. the account that authored them had push access;
3. the repository owner merged them.

Merging a pull request is strong practical evidence that the repository owner accepted those
contributions into a repository it intended to license under MIT, and it is the normal basis on
which an inbound-contribution MIT grant operates. It is **not** a record that the contributor
agreed to the grant, and it is not a record of the terms on which they agreed. The repository
holds no CLA, no `CONTRIBUTING` guide, no `Signed-off-by` from these contributors, no
copyright-holder statement and no governance document that would supply the missing record.

Accordingly, this record does **not** assert that the MIT grant covers those contributions, and
does **not** assert that it does not. It records that the question is open.

### 5.2 Scope of the MIT text as written

`THIRD_PARTY_NOTICES.md` states that the root `LICENSE` applies to first-party code only. It
covers third-party provenance. It says nothing about the authority of first-party contributors
and must not be cited as if it did.

---

## 6. Bot and agent identities

| Identity | Commits | Treatment under the MIT grant |
|---|---|---|
| `dependabot[bot]` | 8 | Automated dependency updates. Not a copyright holder; the upstream packages carry their own licences and are inventoried in `THIRD_PARTY_NOTICES.md`. |
| `Hermes Agent <agent@hermes>` | 12 | Local agent identity operated under the repository owner's direction. No separate copyright holder is asserted; the operator (owner) is accountable for the output. |
| `Hermes Agent <hermes@nousresearch.com>` | 10 | As above. |
| `RetailTwin Subagent <subagent@retailtwin.local>` | 5 | As above. |
| `Claude Opus 5.5` and other AI-tool `Co-authored-by` trailers | 137 | Tool attribution in trailers, not authorship of a distinct copyright holder. The human author of the commit is the copyright holder of that commit's content. |

Agent and bot identities therefore introduce no separate contributor-authority gap; the
accountable party is the repository owner.

---

## 7. Outstanding owner actions

These are the actions required to move CR12 from `DECLARED` to `VERIFIED`. **None of them has
been performed, and none is assumed here.**

| # | Action | Owner | Status | Evidence that would close it |
|---|---|---|---|---|
| A1 | Choose **exactly one** of PR #397 / PR #398 to merge as the canonical licence delivery, and close the other to avoid a duplicate licence and duplicate gate-evidence tree. | Repository owner | ⛔ Outstanding — owner decision | The merged PR's SHA recorded here, with the other PR closed |
| A2 | Record contributor-authority confirmation for the MIT grant covering the contributions of the three non-owner human contributors (`anh-nguyen-3103`, `k-pham08`, `longshaww`) — either a CLA adopted and signed, or a written confirmation from each contributor recorded in-repo. | Repository owner | ⛔ Outstanding — owner action | A `CLA` / `CONTRIBUTING` file in the repository carrying the contributors' acceptance, or an equivalent in-repo record, referenced from this document |
| A3 | After A1 and A2, re-cut the submission SHA and re-run CR12 at that SHA; the licence is bound to the *merged* commit, not to a pre-merge head. | Repository owner + reviewer | ⛔ Blocked by A1, A2 | The post-merge SHA recorded in §2 and in `docs/FINAL_SUBMISSION_VALIDATION_CHECKLIST.md` §6.1 |
| A4 | Redploy the Cloud Run service and re-publish the web artefact at the new SHA, and confirm the MIT notice travels with the distributed artefacts. | Dev-ops | ⛔ Blocked by A3 | A live revision serving the new SHA with the licence notice present. Tracked separately on card `t_f34e7fb6`. |

**Until A1, A2 and A3 are complete, CR12 is at most `DECLARED` and never `VERIFIED`.**

---

## 8. Evidence index

| # | Claim | Evidence |
|---|---|---|
| P1 | Ten distinct author identities at the submission SHA | `git shortlog -sne 920e166f` — 10 rows |
| P2 | Six human identities, four bot/agent identities | `git log --format='%an <%ae>' 920e166f \| sort \| uniq -c` — rows 7–10 are `Hermes Agent`, `RetailTwin Subagent`, `dependabot[bot]` |
| P3 | Six human identities resolve to four GitHub accounts | `gh api repos/…/commits/<sha> --jq '.author.login'` per identity → `vinhphan812` × 2, `k-pham08` × 2, `anh-nguyen-3103`, `longshaww` |
| P4 | "Phan Thanh Vinh" is the owner's display name | `gh api users/vinhphan812` → `id=58102545`, `name="Phan Thanh Vinh"`; the noreply address `58102545+…` carries the same account id |
| P5 | Owner is the sole admin | `gh api repos/…/collaborators` → `vinhphan812 admin=true`; all others `admin=false` |
| P6 | No CLA / CONTRIBUTING / AUTHORS / COPYRIGHT / GOVERNANCE | `git ls-tree -r --name-only 920e166f \| grep -iE '(CLA\|CONTRIBUTING\|AUTHORS\|COPYRIGHT\|GOVERNANCE)'` → no matches |
| P7 | No root licence or notice at the submission SHA | `git ls-tree --name-only 920e166f \| grep -iE '^(LICENSE\|THIRD_PARTY_NOTICES\|COPYING\|NOTICE)'` → no matches; `gh api repos/…/license` → HTTP 404 at the default branch head, which is `920e166f` |
| P8 | `Signed-off-by` present only from the owner and `dependabot` | `git log --format='%B' 920e166f \| grep -iE '^signed-off-by' \| sort \| uniq -c` — 21 owner, 8 dependabot, 2 `Hermes Coordinator <vinhphan812@gmail.com>` |
| P9 | Licence blob identity and SHA-256 | `git rev-parse pr398:LICENSE pr397:LICENSE` → `45b8da20…` on both; `git show pr398:LICENSE \| sha256sum` → `1d1e0b4b…84f4c7`; 1083 bytes |
| P10 | Both licence PRs still open | `gh pr view 397/398` → both `OPEN`, heads `4fae32de…` / `ebb70b64…` |
| P11 | Owner authored all 23 pull-request landings | `git log --merges --format='%an\|%s' 920e166f \| grep 'Merge pull request'` → 23 rows, all `Phan Thanh Vinh`; the other 6 merges are branch synchronisations authored by `Vinh Phan`, `Anh Nguyen`, `Khoa Pham` |
| P12 | Licence and notice authored by the owner on both PRs | `git log pr398 --format='%an <%ae> \| %s' -- LICENSE` and `-- THIRD_PARTY_NOTICES.md` → both `Vinh Phan <vinhphan812@gmail.com>` |

---

## 9. Limits of this record

- It covers **first-party contribution authority only**. Third-party provenance is a separate
  question, answered in `THIRD_PARTY_NOTICES.md` and audited in `LICENSE-EVIDENCE-AUDIT-2026-10-25.md`
  §3.
- It does **not** make a legal judgement on whether the MIT grant is enforceable against the
  three non-owner contributors. It records the evidence, and names the evidence that is missing.
- It makes **no** claim about deployment, release-gate acceptance, or the live service.
- The commit counts are as at `920e166f`. Re-run §3 after any merge to refresh them.

---

*Prepared by task `t_86107ed9` (dev-qa) against `origin/main` @ `920e166f3526947e66ced3644bed40e761a88133`,
PR #397 @ `4fae32dea25c43d4af2fd49d86da11f03fb1e172`, PR #398 @ `ebb70b646f48365bfbb724df71170a09e85442cf`.
All GitHub API probes taken 2026-10-25.*
