# Third-Party Notices

This file records the licensing and attribution status of third-party material
redistributed inside this repository. It supplements — and does not replace —
the [MIT License](LICENSE) that covers the first-party source code in this
repository.

## First-party source code

All first-party source, documentation, scripts, tests, and workflow definitions
in this repository are licensed under the MIT License. See [LICENSE](LICENSE).

## Bundled 3D assets (`apps/web/public/models/`)

Eleven third-party 3D asset packs are committed under
`apps/web/public/models/`. **Every one of them is released under the Creative
Commons Zero (CC0 1.0 Universal) public-domain dedication**, which places no
restriction on redistribution and is compatible with redistribution inside an
MIT-licensed repository. Each pack retains its own upstream `License.txt`
verbatim in its directory, so the authoritative per-asset terms travel with the
files.

| Asset pack | Author / distributor | Upstream license | Upstream source | Local path |
|---|---|---|---|---|
| Car Kit (3.1) | Kenney (www.kenney.nl) | CC0 1.0 | https://kenney.nl | `apps/web/public/models/kenney-car-kit/` |
| City Kit Commercial (2.1) | Kenney (www.kenney.nl) | CC0 1.0 | https://kenney.nl | `apps/web/public/models/kenney-city-commercial/` |
| City Kit Roads (2.2) | Kenney (www.kenney.nl) | CC0 1.0 | https://kenney.nl | `apps/web/public/models/kenney-city-roads/` |
| City Kit Suburban (2.0) | Kenney (www.kenney.nl) | CC0 1.0 | https://kenney.nl | `apps/web/public/models/kenney-city-suburban/` |
| Food Kit (2.0) | Kenney (www.kenney.nl) | CC0 1.0 | https://kenney.nl | `apps/web/public/models/kenney-food/` |
| Furniture Kit (2.0) | Kenney (www.kenney.nl) | CC0 1.0 | https://kenney.nl | `apps/web/public/models/kenney-furniture/` |
| Mini Market Kit | Kenney (www.kenney.nl) | CC0 1.0 | https://kenney.nl | `apps/web/public/models/kenney-mini-market/` |
| Nature Kit (2.1) | Kenney (www.kenney.nl) | CC0 1.0 | https://kenney.nl | `apps/web/public/models/kenney-nature/` |
| Low Poly Vehicles Pack | Daniel Quevedo | CC0 1.0 | https://opengameart.org/content/low-poly-vehicles-pack | `apps/web/public/models/quevedo-vehicles/` |
| Snackies | The Loafbrr | CC0 1.0 | https://loafbrr.itch.io/ | `apps/web/public/models/snackies/` |
| House Plants | Tiny Treats (Isa Lousberg) | CC0 1.0 | https://tinytreats.itch.io/house-plants | `apps/web/public/models/tinytreats/` |

Notes on individual packs, taken from the retained `License.txt` files:

- The Kenney packs state that crediting "Kenney" or "www.kenney.nl" is
  **not a requirement** under CC0. No attribution is claimed as mandatory.
- `quevedo-vehicles/bus.glb` is a derivative of the upstream `Bus.fbx`, converted
  to binary glTF and recolored to match the Kenney vehicle pieces. The
  modification is disclosed in that pack's `License.txt`.
- `tinytreats/` contains house-plant models obtained from the Poly Pizza mirror;
  the pack's `License.txt` records that each source page was marked CC0 and
  lists the per-file source URLs.

### Scope and limits of this verification

- Provenance was verified **from the `License.txt` files committed in this
  repository**, which are the artifacts actually redistributed here. Each of the
  eleven directories contains exactly one such file; no asset pack ships without
  its upstream terms.
- Upstream URL reachability and the full chain of title for each pack were
  **not** independently re-verified as part of this offline review, because that
  would require fetching the upstream distribution pages. This file therefore
  asserts the terms **as recorded in-repository**, not a re-attestation of
  upstream hosting.
- These packs are **demo/visual assets for the 3D Digital Twin UI**. They are
  not part of the submission-gate evidence set and carry no claim about
  production data, deployment, or release-gate acceptance.

## Third-party software dependencies

Third-party software is **not vendored** into this repository. It is resolved
at build/install time from the ecosystem registries and is therefore governed by
its own upstream licenses:

- JavaScript/TypeScript packages are declared in `apps/web/package.json` and
  pinned by the committed lockfile; each package retains its own license.
- Python packages are declared in `apps/api/pyproject.toml` and resolved by the
  package index; each distribution retains its own license.

No dependency source is copied into the repository tree, so none of them is
redistributed under this repository's MIT grant. The `LICENSE` file at the
repository root applies to the first-party code only.

## Relationship to the submission-gate evidence set

This file is a licensing/provenance record. It is **not** part of the
submission-gate evidence set and does not assert anything about gate execution,
deployment, or final-SHA acceptance. The canonical retained gate evidence and
its checksum manifest live at
`docs/evidence/submission-gates/2026-10-22T1556Z/`; see that directory's
`README.md` for the exact provenance, verification commands, and the explicit
offline/non-deployment limitation.

## License texts

The full text of the MIT License is in [LICENSE](LICENSE). The full text of the
Creative Commons Zero 1.0 Universal public-domain dedication is published at
<https://creativecommons.org/publicdomain/zero/1.0/>; each asset pack's own
`License.txt` in this repository reproduces the upstream terms as distributed.
