import { describe, expect, it } from "vitest";
import { EXTERIOR_VIEW, MAX_DISTANCE_FACTOR, ORBIT_TARGET, SIMULATION_ZOOM } from "@/constants/camera.constant";
import { exteriorLevel, simulationView } from "@/scene/camera/exterior";

/** Zoom at `times` the distance that fits the store, with the cap `useFitCamera` sets. */
const zoom = (times: number, fitted = 20) => ({ distance: fitted * times, maxDistance: fitted * MAX_DISTANCE_FACTOR });

describe("exteriorLevel", () => {
  it("leaves the store open at the fitted view and closer", () => {
    expect(exteriorLevel(zoom(1))).toBe(0);
    expect(exteriorLevel(zoom(0.3))).toBe(0);
    expect(exteriorLevel(zoom(EXTERIOR_VIEW.from))).toBe(0);
  });

  it("closes it up fully from the far end of the range out to the zoom cap", () => {
    expect(exteriorLevel(zoom(EXTERIOR_VIEW.to))).toBe(1);
    expect(exteriorLevel(zoom(MAX_DISTANCE_FACTOR))).toBe(1);
  });

  it("eases in between, rising with the distance", () => {
    const mid = exteriorLevel(zoom((EXTERIOR_VIEW.from + EXTERIOR_VIEW.to) / 2));
    expect(mid).toBeCloseTo(0.5);
    expect(exteriorLevel(zoom(EXTERIOR_VIEW.from + 0.05))).toBeLessThan(mid);
  });

  it("stays open without a zoom cap", () => {
    expect(exteriorLevel({ distance: 50, maxDistance: Infinity })).toBe(0);
    expect(exteriorLevel({ distance: 50, maxDistance: 0 })).toBe(0);
  });

  it("does not depend on the window size, only on the zoom against the fit", () => {
    expect(exteriorLevel(zoom(1.5, 12))).toBeCloseTo(exteriorLevel(zoom(1.5, 40)));
  });
});

describe("simulationView", () => {
  /** A camera `times` the fitted distance from the orbit target, along `direction`. */
  const at = (times: number, direction: [number, number, number] = [0.6, 0.48, 0.64], fitted = 20) => {
    const length = Math.hypot(...direction);
    const position = direction.map((value, axis) => ORBIT_TARGET[axis] + (value / length) * fitted * times) as [
      number,
      number,
      number,
    ];
    return { position, zoom: zoom(times, fitted) };
  };

  it("brings the camera in from the closed building, a little closer than the fitted view", () => {
    const { position, zoom: z } = at(2);
    const view = simulationView(position, z)!;
    const [x, y, zz] = view.position.map((value, axis) => value - ORBIT_TARGET[axis]);
    expect(Math.hypot(x, y, zz)).toBeCloseTo(20 * SIMULATION_ZOOM);
    expect(view.target).toEqual(ORBIT_TARGET);
    // The store opens: no roof at the new distance.
    expect(exteriorLevel({ distance: 20 * SIMULATION_ZOOM, maxDistance: z.maxDistance })).toBe(0);
  });

  it("keeps the direction the camera looks at the store from", () => {
    const direction: [number, number, number] = [-0.3, 0.5, 0.8];
    const { position, zoom: z } = at(1.8, direction);
    const view = simulationView(position, z)!;
    const offset = view.position.map((value, axis) => value - ORBIT_TARGET[axis]);
    const before = position.map((value, axis) => value - ORBIT_TARGET[axis]);
    const unit = (v: number[]) => v.map((value) => value / Math.hypot(...v));
    unit(offset).forEach((value, axis) => expect(value).toBeCloseTo(unit(before)[axis]));
  });

  it("leaves a camera that already sees inside the store where it is", () => {
    expect(simulationView(at(1).position, at(1).zoom)).toBeNull();
    expect(simulationView(at(EXTERIOR_VIEW.from).position, at(EXTERIOR_VIEW.from).zoom)).toBeNull();
    expect(simulationView(at(0.5).position, at(0.5).zoom)).toBeNull();
  });
});
