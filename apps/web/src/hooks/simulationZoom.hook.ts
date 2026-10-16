import type { CameraControls } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useEffect } from "react";
import { prefersReducedMotion } from "@/core/utils/motion";
import { VIEW_MODE } from "@/enums/ui.enum";
import { simulationView } from "@/scene/camera/exterior";
import { useUiStore } from "@/state/ui.store";
import type { Tuple3 } from "@/types/scene.type";
import { flyTo } from "./focusSelection.hook";

/**
 * Pressing Simulation while zoomed out to the closed building flies the camera in a little
 * closer than the fitted view (`simulationView`), so the roof lifts and the proposal's changes
 * show. Nearer than that, the camera stays where the user put it. Must run inside the R3F
 * Canvas, next to the default CameraControls.
 */
export function useSimulationZoom() {
  const controls = useThree((state) => state.controls) as CameraControls | null;
  const camera = useThree((state) => state.camera);

  useEffect(
    () =>
      useUiStore.subscribe((ui, before) => {
        if (!controls || ui.viewMode === before.viewMode || ui.viewMode !== VIEW_MODE.Simulation) return;
        const view = simulationView(camera.position.toArray() as Tuple3, {
          distance: controls.distance,
          maxDistance: controls.maxDistance,
        });
        if (view) flyTo(controls, view, !prefersReducedMotion());
      }),
    [controls, camera],
  );
}
