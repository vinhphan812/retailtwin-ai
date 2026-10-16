import { useEffect, useMemo } from "react";
import { ConeGeometry, MeshBasicMaterial, Quaternion, TubeGeometry, Vector3, type QuadraticBezierCurve3 } from "three";
import {
  MOVE_ARROW_HEAD_LENGTH,
  MOVE_ARROW_HEAD_RADIUS,
  MOVE_ARROW_OPACITY,
  MOVE_ARROW_RADIUS,
} from "@/constants/scene.constant";
import { changeColor } from "@/core/utils/theme";

const UP = new Vector3(0, 1, 0);

/** Made on first use, once the theme stylesheet has loaded; `showArrows` fades it. */
let arrowMaterial: MeshBasicMaterial | null = null;
function moveArrowMaterial() {
  // Drawn over the shelves, so an arrow between two gondolas is never hidden behind one.
  arrowMaterial ??= new MeshBasicMaterial({
    color: changeColor(),
    transparent: true,
    opacity: MOVE_ARROW_OPACITY,
    depthTest: false,
    depthWrite: false,
  });
  return arrowMaterial;
}

/** Sets how strongly the arrows show, from 0 to 1. */
export function showArrows(level: number) {
  moveArrowMaterial().opacity = MOVE_ARROW_OPACITY * level;
}

const NO_RAYCAST = () => null;

/** A shaft along `curve` and a head at its end, pointing the way the curve arrives. */
function arrowParts(curve: QuadraticBezierCurve3) {
  const shaft = new TubeGeometry(curve, 24, MOVE_ARROW_RADIUS, 6, false);
  const head = new ConeGeometry(MOVE_ARROW_HEAD_RADIUS, MOVE_ARROW_HEAD_LENGTH, 12);
  const direction = curve.getTangent(1).normalize();
  // A cone stands on its base with its tip up: turn it onto the curve, its tip at the end.
  const quaternion = new Quaternion().setFromUnitVectors(UP, direction);
  const position = curve.v2.clone().addScaledVector(direction, -MOVE_ARROW_HEAD_LENGTH / 2);
  return { shaft, head, position, quaternion };
}

/** One arrow per move, from where the product stood to where it stands. Takes no pointer events and casts no shadow. */
export function MoveArrows({ curves }: { curves: QuadraticBezierCurve3[] }) {
  const parts = useMemo(() => curves.map(arrowParts), [curves]);
  useEffect(
    () => () =>
      parts.forEach(({ shaft, head }) => {
        shaft.dispose();
        head.dispose();
      }),
    [parts],
  );
  const material = moveArrowMaterial();
  return (
    <group name="stock-arrows">
      {parts.map(({ shaft, head, position, quaternion }, index) => (
        <group key={index} name="stock-move-arrow">
          <mesh geometry={shaft} material={material} raycast={NO_RAYCAST} renderOrder={3} />
          <mesh
            geometry={head}
            material={material}
            position={position}
            quaternion={quaternion}
            raycast={NO_RAYCAST}
            renderOrder={3}
          />
        </group>
      ))}
    </group>
  );
}
