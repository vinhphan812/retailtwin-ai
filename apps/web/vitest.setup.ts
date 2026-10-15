import "./src/i18n";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// Mock localStorage for zustand persist middleware (jsdom may not fully implement Storage)
const store: Record<string, string> = {};
(globalThis as unknown as { localStorage: Storage }).localStorage = {
  getItem: (key: string) => (key in store ? store[key] : null),
  setItem: (key: string, value: string) => { store[key] = value; },
  removeItem: (key: string) => { delete store[key]; },
  clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
  key: (i: number) => Object.keys(store)[i] || null,
  get length() { return Object.keys(store).length; },
} as Storage;

// Mock HTMLCanvasElement.getContext for Three.js tests in jsdom
if (typeof HTMLCanvasElement !== "undefined") {
  HTMLCanvasElement.prototype.getContext = function (
    contextType: string,
    _attributes?: CanvasRenderingContext2DSettings | ImageBitmapRenderingContextSettings | WebGLRenderingContextSettings | WebGL2RenderingContextSettings
  ) {
    if (contextType === "2d" || contextType === "webgl" || contextType === "webgl2") {
      return {
        canvas: this,
        drawingBufferWidth: this.width || 800,
        drawingBufferHeight: this.height || 600,
      } as unknown as CanvasRenderingContext2D | WebGLRenderingContext | WebGL2RenderingContext;
    }
    return null;
  } as unknown as HTMLCanvasElement["getContext"];
}
