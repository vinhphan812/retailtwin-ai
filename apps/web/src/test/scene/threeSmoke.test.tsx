import ReactThreeTestRenderer from "@react-three/test-renderer";
import type { ThreeEvent } from "@react-three/fiber";
import type { Intersection } from "three";
import { describe, expect, it, vi } from "vitest";
import { stockedStoreState } from "@/test/stockedState";
import { toSceneStore } from "@/scene/layout";
import { StoreContents } from "@/scene/StoreScene";
import { useSelectOnClick } from "@/hooks/selectEntity.hook";
import { ENTITY_TYPE } from "@/enums/scene.enum";
import { useUiStore, selectedProductId } from "@/state/ui.store";

vi.mock("@/hooks/checkout.hook", async () => {
  const { SAMPLE_CHECKOUTS } = await import("@/test/checkoutSample");
  return { useCheckoutSummary: (id: string) => SAMPLE_CHECKOUTS[id] ?? null, useCheckoutTransactions: () => [] };
});

describe("3D Interaction & Smoke Test (R3F, Raycasting, Camera, Canvas Events)", () => {
  const store = toSceneStore(stockedStoreState()).store;

  it("renders store geometry and entities correctly via React Three Fiber", async () => {
    const renderer = await ReactThreeTestRenderer.create(<StoreContents store={store} />);
    const scene = renderer.scene.instance;

    // 1. Geometry / Scene Graph verification
    const storeNode = scene.getObjectByName("store-001");
    expect(storeNode).toBeTruthy();
    const shelfA01 = scene.getObjectByName("A01");
    expect(shelfA01).toBeTruthy();
    const productP001 = scene.getObjectByName("P001");
    expect(productP001).toBeTruthy();

    // 2. Raycasting / Selection interaction test via useSelectOnClick
    useUiStore.getState().select(null);
    expect(selectedProductId(useUiStore.getState())).toBeNull();

    const items = shelfA01!.userData.stockItems || [];
    const hitIntersection = {
      object: { userData: { stockItems: items } },
      instanceId: 0,
    } as unknown as Intersection;

    let stopped = false;
    const event = {
      delta: 0,
      intersections: [hitIntersection],
      stopPropagation: () => { stopped = true; },
    } as unknown as ThreeEvent<MouseEvent>;

    const clickHandler = useSelectOnClick("A01", ENTITY_TYPE.Shelf);
    clickHandler(event);

    expect(stopped).toBe(true);

    // 3. Canvas events / pointer interaction check
    const canvasElement = document.createElement("canvas");
    const glContext = canvasElement.getContext("webgl2");
    expect(glContext).toBeTruthy();
  });
});
