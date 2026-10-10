/**
 * A color of the App.css `@theme` palette, for code that cannot use CSS, such as
 * three.js materials. Read once per token, so call it after the stylesheet has
 * loaded (while rendering, not at module load). `fallback` stands in where there is
 * no document or the token is missing.
 */
const cache = new Map<string, string>();

export function themeColor(token: string, fallback: string): string {
  let color = cache.get(token);
  if (color === undefined) {
    const value = typeof document === "undefined"
      ? ""
      : getComputedStyle(document.documentElement).getPropertyValue(token).trim();
    color = value || fallback;
    if (value) cache.set(token, color);
  }
  return color;
}

/** Status colors of the palette, for the 3D scene. */
export const goodColor = () => themeColor("--color-good", "#0ca30c");
export const warningColor = () => themeColor("--color-warning", "#fab219");

/** Glow color of the selected entity, from the `--color-selection` theme token. */
export const selectionColor = () => themeColor("--color-selection", "#ffffff");

/** Halo color of a product with an open anomaly, from the `--color-anomaly` theme token. */
export const anomalyColor = () => themeColor("--color-anomaly", "#ec835a");
