# Contributing to RetailTwin AI

Thank you for contributing. This file is short on purpose: it states only what a contributor needs
to know about the terms on which contributions are accepted.

---

## 1. Licensing of contributions

All contributions to this repository are licensed under the **MIT Licence**.

Before your contribution is merged, you must have accepted the
[Individual Contributor Licence Agreement](CLA.md) (`CLA.md` at the repository root). The CLA is an
**inbound** agreement: it covers contributions already in the repository's history as well as
future ones, so the project's licence grant is complete for the whole of the first-party code.

### How to accept

Either form is valid, and both are recorded in the repository:

1. **Sign the register** — add a signature line to the acceptance register at `CLA.md` §5,
   naming your GitHub account, your preferred display name and the date, then open a pull request
   against `CLA.md`.
2. **Confirm in writing** — post the confirmation in the acceptance-request issue opened for you
   by the project owner. A public comment there, made under the GitHub account that authored the
   contributions, is an in-repository written confirmation.

The register at `CLA.md` §5 is the authoritative record of who has accepted. The project owner
maintains it and attributes each acceptance to its actual source.

### What the CLA asks you to confirm

That your contributions are your original work, that you hold the right to license them under the
MIT Licence, and that you have not introduced conflicting obligations. Where a contribution
includes third-party code, that code is inventoried in `THIRD_PARTY_NOTICES.md` and remains under
its own licence — the CLA does not extend to it.

Third-party dependencies are not covered by the CLA. They are listed in
`THIRD_PARTY_NOTICES.md` with their own licences.

---

## 2. The MIT Licence text

The MIT Licence text lives at the repository root as `LICENSE`. It applies to the project's
first-party code only. `THIRD_PARTY_NOTICES.md` records third-party provenance separately.

---

## 3. How a contribution is made

The project's development workflow is documented in
[`docs/DEVELOPMENT_WORKFLOW.md`](docs/DEVELOPMENT_WORKFLOW.md) — the issue → branch → pull
request → ADR workflow, the merge-safety rules, and the vocabulary used for maturity.

In short:

1. Open or claim an issue before starting work.
2. Work on a branch; do not commit directly to `main`.
3. Open a pull request that references the issue.
4. Wait for the required CI checks and a reviewer approval. Do not merge your own pull request.

---

## 4. Where the licence evidence is recorded

| Document | What it holds |
|---|---|
| [`CLA.md`](CLA.md) | The Individual Contributor Licence Agreement and its acceptance register (§5). |
| [`docs/licensing/CONTRIBUTOR-LICENSE-PROVENANCE.md`](docs/licensing/CONTRIBUTOR-LICENSE-PROVENANCE.md) | The per-contributor evidence index behind the licence grant, including the commands that reproduce every claim. |
| [`docs/FINAL_SUBMISSION_VALIDATION_CHECKLIST.md`](docs/FINAL_SUBMISSION_VALIDATION_CHECKLIST.md) §6.1 | The licence-evidence state of the project and the outstanding owner actions. |
| [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) | Third-party provenance only. |

---

*Questions about licensing: raise an issue and ask. Do not assume an answer — the project records
only what has actually been confirmed.*
