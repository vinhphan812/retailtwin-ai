// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

test("reads apps/api by default, and shows an API failure without crashing", async () => {
  const fetchMock = vi.fn(async (_url: RequestInfo | URL): Promise<Response> => {
    throw new TypeError("offline");
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await waitFor(() => {
    expect(notify.error).toHaveBeenCalledWith(
      "The API request failed.",
      expect.objectContaining({ message: "The API is unreachable." }),
    );
  });
  const paths = fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname);
  expect(paths).toContain("/store");
  expect(paths).toContain("/health");
  expect(screen.getByRole("heading", { name: "Agent Activity" })).toBeTruthy();
  expect(screen.getByRole("main")).toBeTruthy();
  expect(screen.getByRole("textbox", { name: "SKU" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Look up inventory" })).toBeTruthy();
});

test("shows the lens switch with all three lenses, Operations first", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
  render(<App />);
  expect(screen.getByRole("radiogroup", { name: "View" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "Operations" }).getAttribute("aria-checked")).toBe("true");
  expect(screen.getByRole("radio", { name: "Revenue" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "Promotions" })).toBeTruthy();
});
