import { describe, expect, it } from "vitest";
import { FIXTURE_P001 } from "@/constants/twin.constant";
import { demoSeed, demoSeedJson } from "@/fixtures/demo/seed";
import { demoStoreState } from "@/fixtures/demo/store";
import committed from "../../../../../../data/seed/demo-store.json?raw";

describe("demo store seed (data/seed/demo-store.json)", () => {
  it("is the demo store as committed; run `npm run seed:export` after changing it", () => {
    expect(committed).toBe(demoSeedJson());
  });

  it("has apps/api's FixtureFile shape: the six twin fields per product, nothing else", () => {
    const seed = demoSeed();
    expect(Object.keys(seed)).toEqual(["store_id", "version", "products"]);
    expect(seed.version).toMatch(/^v\d+$/);
    for (const product of seed.products) {
      expect(Object.keys(product)).toEqual(["sku", "shelf_id", "slot_id", "facings", "shelf_quantity", "backroom_quantity"]);
    }
    expect(seed.products).toHaveLength(demoStoreState().products.length);
  });

  it("holds unique SKUs and slots, P001 as the API fixture has it, and no P017", () => {
    const { store_id, products } = demoSeed();
    expect(store_id).toBe(FIXTURE_P001.store_id);
    expect(new Set(products.map((product) => product.sku)).size).toBe(products.length);
    expect(new Set(products.map((product) => product.slot_id)).size).toBe(products.length);
    const { sku, shelf_id, slot_id, facings, shelf_quantity, backroom_quantity } = FIXTURE_P001;
    expect(products[0]).toEqual({ sku, shelf_id, slot_id, facings, shelf_quantity, backroom_quantity });
    // The demand-surge scenario adds P017 itself (the flagship reset).
    expect(products.some((product) => product.sku === "P017")).toBe(false);
  });
});
