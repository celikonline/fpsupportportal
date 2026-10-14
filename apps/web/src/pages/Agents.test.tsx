// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { AgentsPage } from "./Agents";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function mount(stale = false) {
  const work = { id: "work", ticketId: "ticket", state: "solution_review", version: 4, ticketVersion: 3, assigneeId: 2, solution: "Verified fix", reason: "Acceptance criteria", ticket: { id: "ticket", version: stale ? 4 : 3, status: "in_progress", number: "FP-0001", title: "Support" } };
  const fetcher = vi.fn(async (path: string, options: RequestInit) => {
    if (options.method === "POST") return new Response(JSON.stringify({ ...work, state: "done" }));
    if (path.endsWith("/automation")) return new Response(JSON.stringify({ enabled: false, botId: 3, externalAgentIds: [2], instructions: "", modelReady: false, model: "" }));
    if (path.endsWith("/members")) return new Response(JSON.stringify([{ id: 1, name: "PO", role: "lead" }, { id: 2, name: "Worker", role: "agent" }, { id: 3, name: "Bot", role: "agent" }]));
    return new Response(JSON.stringify({ results: [work], total: 1 }));
  });
  vi.stubGlobal("fetch", fetcher);
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AgentsPage scope="tenants/t/projects/p" base="/t/t/p/p" role="lead" archived={false} /></QueryClientProvider></MemoryRouter>);
  return fetcher;
}

it("publishes a solution only through explicit PO approval with both versions", async () => {
  const fetcher = mount();
  await screen.findByText("Verified fix");
  fireEvent.change(screen.getByLabelText("Değerlendirme / kabul koşulları"), { target: { value: "Tests verified" } });
  fireEvent.click(screen.getByRole("button", { name: "Onayla ve müşteriye yayınla" }));
  await waitFor(() => expect(fetcher.mock.calls.some(([, options]) => options.method === "POST")).toBe(true));
  const [, options] = fetcher.mock.calls.find(([, options]) => options.method === "POST")!;
  expect(JSON.parse(String(options.body))).toMatchObject({ action: "approve", version: 4, ticketVersion: 3, reason: "Tests verified" });
  expect((screen.getByLabelText("Otomatik müşteri yanıtlarını etkinleştir") as HTMLInputElement).disabled).toBe(true);
});

it("requires reevaluation when a solution refers to an older ticket version", async () => {
  mount(true);
  await screen.findByText("Verified fix");
  expect(screen.queryByRole("button", { name: "Onayla ve müşteriye yayınla" })).toBeNull();
  expect(screen.getByText(/Çözümden sonra talep değişti/)).toBeTruthy();
});
