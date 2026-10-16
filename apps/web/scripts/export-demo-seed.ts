/**
 * Writes the demo store (`fixtures/demo/store.ts`, what `?twin=demo` and `/demo` show) to
 * `data/seed/demo-store.json`, in the shape apps/api loads as its store fixture
 * (`FixtureFile` in `apps/api/retailtwin_api/schemas.py`): `{ store_id, version, products }`.
 *
 *   npm run seed:export
 *
 * The test `test/fixtures/demo/demoSeed.test.ts` fails when the committed file and the demo
 * store drift apart, so run this after changing the demo store.
 */
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { demoSeedJson } from "../src/fixtures/demo/seed";

const DEMO_SEED_PATH = fileURLToPath(new URL("../../../data/seed/demo-store.json", import.meta.url));

writeFileSync(DEMO_SEED_PATH, demoSeedJson());
console.log(`Wrote ${DEMO_SEED_PATH}`);
