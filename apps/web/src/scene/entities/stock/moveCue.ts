import { Matrix4, Vector3 } from "three";
import { MOVE_TWEEN_MS } from "@/constants/twin.constant";
import { ENTITY_TYPE } from "@/enums/scene.enum";
import type { SlotRef } from "@/core/twin/stateDiff";
import { entityMatrix } from "@/scene/utils/transform";
import type { RecentChange } from "@/state/twin.store";
import type { SlotFixture, StoreFixture } from "@/types/scene.type";
import { surfaceMatrix, surfacesOf } from "./surfaces";

/**
 * The scene's cue for the moves of a recent change: `offsets` take each moved product's
 * items from their destination back to their source slot.
 */
export type MoveCue = {
  at: number;
  offsets: Map<string, Vector3>;
};

type SlotFrame = { toWorld: Matrix4; slot: SlotFixture };

/** A slot's surface frame in world space, or null when the layout has no such slot. */
function slotFrame(store: StoreFixture, { shelf_id, slot_id }: SlotRef): SlotFrame | null {
  const shelf = store.shelves.find((item) => item.shelfId === shelf_id);
  const holder = shelf
    ? { kind: ENTITY_TYPE.Shelf, fixture: shelf }
    : store.equipment.map((item) => ({ kind: item.kind, fixture: item })).find(({ fixture }) => fixture.equipmentId === shelf_id);
  const slot = holder?.fixture.slots.find((item) => item.slotId === slot_id);
  const surface = holder && slot ? surfacesOf(holder.kind)[slot.surface] : undefined;
  if (!holder || !slot || !surface) return null;
  const toWorld = entityMatrix(holder.fixture.position, holder.fixture.rotationY).multiply(surfaceMatrix(surface));
  return { toWorld, slot };
}

/** Middle of a slot's front edge on its surface, in world space. */
function slotCenter({ toWorld, slot }: SlotFrame): Vector3 {
  return new Vector3(slot.offset, 0, 0).applyMatrix4(toWorld);
}

/**
 * The cue for the moves in `change` on `store`, the state on screen, or null when there
 * is none to show. A move counts only while the product still stands where the move put
 * it and both slots are in the layout.
 */
export function moveCueOf(store: StoreFixture, change: RecentChange | null): MoveCue | null {
  if (!change || change.diff.moved.length === 0) return null;
  const placed = new Map(store.products.map((product) => [product.productId, product]));
  const offsets = new Map<string, Vector3>();
  for (const move of change.diff.moved) {
    const product = placed.get(move.sku);
    if (product?.shelfId !== move.to.shelf_id || product.slotId !== move.to.slot_id) continue;
    const from = slotFrame(store, move.from);
    const to = slotFrame(store, move.to);
    if (!from || !to) continue;
    offsets.set(move.sku, slotCenter(from).sub(slotCenter(to)));
  }
  return offsets.size ? { at: change.at, offsets } : null;
}

/** How far a move's tween has come at `now`, from 0 to 1. */
export function moveProgress(at: number, now: number): number {
  return Math.min(1, Math.max(0, (now - at) / MOVE_TWEEN_MS));
}

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

/**
 * `matrix` shifted back toward its source by what is left of the tween at `progress`,
 * written into `out`. At 1 it is `matrix` itself: the end of the tween is the state.
 */
export function tweenMatrix(matrix: Matrix4, offset: Vector3, progress: number, out = new Matrix4()): Matrix4 {
  const left = 1 - easeInOut(Math.min(1, Math.max(0, progress)));
  return out.makeTranslation(offset.x * left, offset.y * left, offset.z * left).multiply(matrix);
}
