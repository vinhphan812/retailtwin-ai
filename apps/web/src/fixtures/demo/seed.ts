import { demoStoreState } from "./store";

/** One product of apps/api's store fixture (`FixtureProduct`): the twin fields, no names or prices. */
export type SeedProduct = {
  sku: string;
  shelf_id: string;
  slot_id: string;
  facings: number;
  shelf_quantity: number;
  backroom_quantity: number;
};

/** apps/api's store fixture (`FixtureFile`), as `STORE_FIXTURE_PATH` loads it. */
export type StoreSeed = { store_id: string; version: string; products: SeedProduct[] };

/**
 * The demo store as an apps/api store fixture, committed as `data/seed/demo-store.json`
 * (`npm run seed:export`) so the API can serve what `/demo` shows.
 */
export function demoSeed(): StoreSeed {
  const { store_id, version, products } = demoStoreState();
  return {
    store_id,
    version,
    products: products.map(({ sku, shelf_id, slot_id, facings, shelf_quantity, backroom_quantity }) => ({
      sku,
      shelf_id,
      slot_id,
      facings,
      shelf_quantity,
      backroom_quantity,
    })),
  };
}

/** `demoSeed()` as the committed file holds it: two-space JSON with a final newline. */
export function demoSeedJson(): string {
  return `${JSON.stringify(demoSeed(), null, 2)}\n`;
}
