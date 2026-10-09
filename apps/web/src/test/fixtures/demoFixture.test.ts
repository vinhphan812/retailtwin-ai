import { describe, expect, it } from "vitest";
import { parseStoreState } from "@/core/api/validate";
import { demoStoreState } from "@/fixtures/demoFixture";
import { toSceneStore } from "@/scene/layout";
import { buildStock } from "@/scene/entities/stock/Stock";
import { FIXTURE_P001 } from "@/constants/twin.constant";

describe("demo store state", () => {
  it("passes the GET /store contract and places every product", () => {
    const { state, issues } = parseStoreState(demoStoreState());
    expect(issues).toEqual([]);
    const scene = toSceneStore(state);
    expect(scene.issues).toEqual([]);
    expect(scene.store.products).toHaveLength(state.products.length);
  });

  it("keeps P001 as the API fixture serves it", () => {
    expect(demoStoreState().products.find((product) => product.sku === "P001")).toEqual(FIXTURE_P001);
  });

  it("draws items for every product that has stock, and none for a stockout", () => {
    const state = demoStoreState();
    const batches = buildStock(toSceneStore(state).store);
    const drawn = new Set(Object.values(batches).flatMap((items) => items.map((item) => item.productId)));
    for (const product of state.products) {
      expect(drawn.has(product.sku)).toBe(product.shelf_quantity > 0 && product.facings > 0);
    }
  });

  it("returns a new object per call", () => {
    const state = demoStoreState();
    state.products[0].facings = 99;
    expect(demoStoreState().products[0].facings).toBe(FIXTURE_P001.facings);
  });
});
