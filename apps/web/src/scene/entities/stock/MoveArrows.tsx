import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import type { QuadraticBezierCurve3 } from "three";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import {
  MOVE_ARROW_OPACITY,
  MOVE_ARROW_OUTLINE_OPACITY,
  MOVE_ARROW_OUTLINE_PX,
  MOVE_ARROW_WIDTH_PX,
} from "@/constants/scene.constant";
import { moveColor } from "@/core/utils/theme";

/** Points along a move's line; enough for a smooth arc at any zoom. */
const LINE_POINTS = 40;
/** The outline under the line: dark, so the line reads over light shelves and floor. */
const OUTLINE_COLOR = "#121820";

/**
 * The line materials, made on first use once the theme stylesheet has loaded. Lines are
 * drawn over the shelves (no depth test), so a move between two gondolas is never hidden.
 * `showArrows` fades them.
 */
let materials: { line: LineMaterial; outline: LineMaterial } | null = null;
function lineMaterials() {
  const flat = { transparent: true, depthTest: false, depthWrite: false };
  materials ??= {
    line: new LineMaterial({
      ...flat,
      color: moveColor(),
      linewidth: MOVE_ARROW_WIDTH_PX,
      opacity: MOVE_ARROW_OPACITY,
    }),
    outline: new LineMaterial({
      ...flat,
      color: OUTLINE_COLOR,
      linewidth: MOVE_ARROW_OUTLINE_PX,
      opacity: MOVE_ARROW_OUTLINE_OPACITY,
    }),
  };
  return materials;
}

/** Sets how strongly the move lines show, from 0 to 1. */
export function showArrows(level: number) {
  const { line, outline } = lineMaterials();
  line.opacity = MOVE_ARROW_OPACITY * level;
  outline.opacity = MOVE_ARROW_OUTLINE_OPACITY * level;
}

const NO_RAYCAST = () => null;

/** A move's line along `curve`, and the outline under it, sharing one geometry. */
function lineParts(curve: QuadraticBezierCurve3, line: LineMaterial, outline: LineMaterial) {
  const positions = curve
    .getSpacedPoints(LINE_POINTS)
    .flatMap((point) => point.toArray());
  const geometry = new LineGeometry().setPositions(positions);
  return { geometry, shaft: new Line2(geometry, line), under: new Line2(geometry, outline) };
}

/**
 * One line per move, from where the product stood to where it stands: a solid line of a
 * fixed width on screen over a thin dark outline. It fades with the other marks of the move
 * and never animates on its own. Takes no pointer events and casts no shadow.
 */
export function MoveArrows({ curves }: { curves: QuadraticBezierCurve3[] }) {
  const { line, outline } = lineMaterials();
  const parts = useMemo(() => curves.map((curve) => lineParts(curve, line, outline)), [curves, line, outline]);
  useEffect(() => () => parts.forEach(({ geometry }) => geometry.dispose()), [parts]);
  const size = useThree((state) => state.size);

  useFrame(() => {
    if (!parts.length) return;
    line.resolution.set(size.width, size.height);
    outline.resolution.set(size.width, size.height);
  });

  return (
    <group name="stock-arrows">
      {parts.map(({ shaft, under }, index) => (
        <group key={index} name="stock-move-arrow">
          <primitive object={under} raycast={NO_RAYCAST} renderOrder={3} />
          <primitive object={shaft} raycast={NO_RAYCAST} renderOrder={4} />
        </group>
      ))}
    </group>
  );
}
