import { describe, expect, it, vi } from "vitest";
import { createWoodTexture } from "@/scene/entities/woodTexture";

/**
 * Regression test for the jsdom 30 canvas setup used by procedural Three.js
 * textures. It verifies actual drawing paths, not merely getContext's shape.
 */
describe("jsdom canvas texture harness", () => {
  it("provides a usable mocked 2D context to the procedural wood texture", () => {
    const original = HTMLCanvasElement.prototype.getContext;
    const fillRect = vi.fn();
    const fillStyleAssignments: string[] = [];
    const ctx = {
      createLinearGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
      fillRect,
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      fill: vi.fn(),
      ellipse: vi.fn(),
      set fillStyle(value: string) { fillStyleAssignments.push(value); },
      get fillStyle() { return fillStyleAssignments.at(-1) ?? ""; },
      set strokeStyle(_value: string) {},
      set lineWidth(_value: number) {},
      set globalAlpha(_value: number) {},
    } as unknown as CanvasRenderingContext2D;

    const getContext = vi.fn((kind: string) => (kind === "2d" ? ctx : null));
    HTMLCanvasElement.prototype.getContext = getContext as typeof HTMLCanvasElement.prototype.getContext;
    try {
      const texture = createWoodTexture();
      expect(texture).not.toBeNull();
      expect(getContext).toHaveBeenCalledWith("2d");
      expect(fillRect).toHaveBeenCalled();
      expect(fillStyleAssignments.length).toBeGreaterThan(0);
      texture?.dispose();
    } finally {
      HTMLCanvasElement.prototype.getContext = original;
    }
  });
});
