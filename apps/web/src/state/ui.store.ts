import { create } from "zustand";
import { ENTITY_TYPE, type EntityType } from "@/enums/scene.enum";
import { LENS, VIEW_MODE, type Lens, type ViewMode } from "@/enums/ui.enum";

type UiStore = {
  selectedEntityId: string | null;
  /** What the selected id names: a product (SKU), a shelf, or a piece of equipment. */
  selectedEntityType: EntityType | null;
  viewMode: ViewMode;
  /** Operations, revenue, or promotions: picks the panel's content. */
  lens: Lens;
  /** Selects an entity, a product unless told otherwise; `null` clears the selection. */
  select: (entityId: string | null, entityType?: EntityType) => void;
  setViewMode: (mode: ViewMode) => void;
  setLens: (lens: Lens) => void;
};

export const useUiStore = create<UiStore>()((set) => ({
  selectedEntityId: null,
  selectedEntityType: null,
  viewMode: VIEW_MODE.Live,
  lens: LENS.Operations,
  select: (selectedEntityId, entityType = ENTITY_TYPE.Product) =>
    set({ selectedEntityId, selectedEntityType: selectedEntityId ? entityType : null }),
  setViewMode: (viewMode) => set({ viewMode }),
  setLens: (lens) => set({ lens }),
}));

/** True while `entityId` is the selected entity of `entityType`. */
export function isSelected(state: Pick<UiStore, "selectedEntityId" | "selectedEntityType">, entityId: string, entityType: EntityType) {
  return state.selectedEntityId === entityId && state.selectedEntityType === entityType;
}

/** The selected product's SKU, or null when nothing or a fixture is selected. */
export function selectedProductId(state: Pick<UiStore, "selectedEntityId" | "selectedEntityType">) {
  return state.selectedEntityType === ENTITY_TYPE.Product ? state.selectedEntityId : null;
}
