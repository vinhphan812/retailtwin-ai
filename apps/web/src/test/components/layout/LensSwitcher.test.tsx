// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MotionGlobalConfig } from "framer-motion";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { LENS } from "@/enums/ui.enum";
import { usePanelStore } from "@/state/panel.store";
import { useUiStore } from "@/state/ui.store";
import { AgentActivityOpenButton, AgentActivityPanel } from "@/components/layout/AgentActivityPanel";
import { LensSwitcher } from "@/components/layout/LensSwitcher";
import { forgetLensReads } from "@/hooks/commerce.hook";

vi.mock("@/components/status/StoreStatus", () => ({ StoreStatus: () => null }));
vi.mock("@/core/notify", () => ({
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  notify: { error: vi.fn(), warning: vi.fn(), info: vi.fn(), success: vi.fn() },
}));

/** A 404 for every route unless a test answers otherwise. */
const fetchMock = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response("{}", { status: 404 }));
const requested = () => fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname + new URL(String(url)).search);

MotionGlobalConfig.skipAnimations = true;

beforeEach(() => {
  forgetLensReads();
  fetchMock.mockReset();
  fetchMock.mockImplementation(async () => new Response("{}", { status: 404 }));
  vi.stubGlobal("fetch", fetchMock);
  usePanelStore.setState({ open: true });
  useUiStore.setState({ lens: LENS.Operations });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderShell() {
  return render(
    <>
      <LensSwitcher />
      <AgentActivityOpenButton />
      <AgentActivityPanel />
    </>,
  );
}

/** The `GET /revenue` reads so far, as their query parameters. */
const revenueReads = () =>
  fetchMock.mock.calls
    .map(([url]) => new URL(String(url)))
    .filter((url) => url.pathname === "/revenue")
    .map((url) => Object.fromEntries(url.searchParams));

test("opening revenue asks apps/api for a grain and a window, never the lens's own window names", async () => {
  // Reads that have not answered yet.
  fetchMock.mockImplementation(() => new Promise<Response>(() => {}));
  renderShell();
  fireEvent.click(screen.getByRole("radio", { name: "Revenue" }));

  expect(await screen.findByRole("heading", { name: "Revenue", level: 1 })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "Today" }).getAttribute("aria-checked")).toBe("true");
  expect(screen.getByText("Reading GET /revenue…")).toBeTruthy();
  await waitFor(() => expect(revenueReads()).toHaveLength(1));
  const today = revenueReads()[0];
  expect(today.period).toBe("hourly");
  expect(Date.parse(today.start)).toBeLessThanOrEqual(Date.parse(today.end));

  fireEvent.click(screen.getByRole("radio", { name: "7 days" }));
  await waitFor(() => expect(revenueReads().map((read) => read.period)).toEqual(["hourly", "daily"]));
  for (const read of revenueReads()) expect(["today", "7d", "30d"]).not.toContain(read.period);
});

test("a failed revenue read shows why, with a retry, instead of figures of 0", async () => {
  fetchMock.mockImplementation(async () =>
    new Response(JSON.stringify({ error: { code: "analytics_unavailable", message: "Revenue analytics are currently unavailable." } }), {
      status: 503,
    }),
  );
  renderShell();
  fireEvent.click(screen.getByRole("radio", { name: "Revenue" }));

  const card = await screen.findByRole("alert", { name: "Revenue unavailable" });
  expect(card.textContent).toContain("BigQuery analytics are unavailable");
  expect(card.textContent).toContain("HTTP 503 · analytics_unavailable");
  expect(card.textContent).toContain("GET /revenue");
  expect(card.textContent).toContain("Live · apps/api");
  // The id sent with the read, to find it in the apps/api logs.
  const sent = new Headers(fetchMock.mock.calls.at(-1)![1]?.headers).get("x-correlation-id");
  expect(sent).toBeTruthy();
  expect(card.textContent).toContain(sent!);
  expect(screen.queryByText("$0")).toBeNull();

  fetchMock.mockImplementation(async () =>
    new Response(
      JSON.stringify({
        store_id: "store-001",
        period: "hourly",
        start: revenueReads()[0].start,
        end: revenueReads()[0].end,
        total_revenue: 120.5,
        total_transactions: 3,
        total_items_sold: 7,
        avg_transaction_value: 40.17,
        currency: "USD",
        buckets: [],
      }),
    ),
  );
  fireEvent.click(within(card).getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("$120.5")).toBeTruthy();
  expect(screen.queryByRole("alert", { name: "Revenue unavailable" })).toBeNull();
  // What apps/api does not serve says so, rather than 0.
  expect(screen.getAllByText("Not served").length).toBeGreaterThanOrEqual(2);
});

test("a revenue read with no sales says so, with a retry, instead of a report of zeros", async () => {
  fetchMock.mockImplementation(async (url) => {
    const query = new URL(String(url)).searchParams;
    return new Response(
      JSON.stringify({
        store_id: "store-001",
        period: query.get("period"),
        start: query.get("start"),
        end: query.get("end"),
        total_revenue: 0,
        total_transactions: 0,
        total_items_sold: 0,
        avg_transaction_value: 0,
        currency: "USD",
        buckets: [],
      }),
    );
  });
  renderShell();
  fireEvent.click(screen.getByRole("radio", { name: "Revenue" }));

  const card = await screen.findByRole("status", { name: "No sales recorded" });
  expect(card.textContent).toContain("GET /revenue served no sales for store-001");
  expect(within(card).getByRole("button", { name: "Retry" })).toBeTruthy();
  expect(screen.queryByText("$0")).toBeNull();
});

test("opening promotions reads GET /promotions, and says when there are none", async () => {
  fetchMock.mockImplementation(async () =>
    new Response(JSON.stringify({ store_id: "store-001", revenue: 0, incremental_revenue: 0, discount_cost: 0, promotions: [] })),
  );
  renderShell();
  fireEvent.click(screen.getByRole("radio", { name: "Promotions" }));

  expect(await screen.findByText("No promotions yet.")).toBeTruthy();
  await waitFor(() => expect(requested()).toContain("/promotions"));
  const filter = screen.getByRole("radiogroup", { name: "Filter by status" });
  fireEvent.click(within(filter).getByRole("radio", { name: /In review/ }));
  expect(await screen.findByText("No promotions with this status.")).toBeTruthy();
});

test("a failed promotions read says why, with a retry, instead of claiming there are none", async () => {
  renderShell();
  fireEvent.click(screen.getByRole("radio", { name: "Promotions" }));

  const card = await screen.findByRole("alert", { name: "Promotions unavailable" });
  expect(card.textContent).toContain("HTTP 404");
  expect(screen.queryByText("No promotions yet.")).toBeNull();
});

test("arrow keys move the lens, and picking one reopens a closed panel", async () => {
  renderShell();
  fireEvent.click(screen.getByRole("button", { name: "Close the Agent Activity panel" }));
  expect(await screen.findByRole("button", { name: "Open the Agent Activity panel" })).toBeTruthy();

  fireEvent.keyDown(screen.getByRole("radio", { name: "Operations" }), { key: "ArrowLeft" });
  expect(useUiStore.getState().lens).toBe(LENS.Promotions);
  expect(usePanelStore.getState().open).toBe(true);
  expect(await screen.findByRole("heading", { name: "Promotions", level: 1 })).toBeTruthy();
});
