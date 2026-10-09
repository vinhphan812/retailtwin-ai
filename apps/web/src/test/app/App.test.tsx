// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { notify } from "@/core/notify";
import { App } from "@/app/App";

vi.mock("@/core/notify", () => ({
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  notify: { error: vi.fn(), warning: vi.fn(), success: vi.fn() },
}));

vi.mock("@/scene/StoreScene", () => ({
  StoreScene: () => null,
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// TODO(BE): while apps/api is off (see pickSource, StoreStatus, commerceClient) the app makes no
// request. Bring back "the app shows an API failure without crashing" when the reads come back.
test("calls no API while apps/api is off, and still shows the panel", async () => {
  const fetchMock = vi.fn(async () => {
    throw new TypeError("offline");
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByRole("heading", { name: "Agent Activity" })).toBeTruthy();
  expect(screen.getByRole("main")).toBeTruthy();
  expect(screen.getByRole("textbox", { name: "SKU" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Look up inventory" })).toBeTruthy();
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(fetchMock).not.toHaveBeenCalled();
  expect(notify.error).not.toHaveBeenCalled();
});

test("shows the lens switch with all three lenses, Operations first", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
  render(<App />);
  expect(screen.getByRole("radiogroup", { name: "View" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "Operations" }).getAttribute("aria-checked")).toBe("true");
  expect(screen.getByRole("radio", { name: "Revenue" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "Promotions" })).toBeTruthy();
});
