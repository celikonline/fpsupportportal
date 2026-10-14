// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { ApiKeysPage } from "./ApiKeys";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("API key screen", () => {
  it("shows a new secret once and never stores it in the list cache", async () => {
    const secret =
      "fpsk_123456abcdef_abcdefghijklmnopqrstuvwxyzABCDEFGH12345678";
    const item = {
      id: "key-1",
      name: "ERP",
      prefix: "fpsk_123456abcdef",
      mode: "read",
      createdAt: "2026-10-14T00:00:00Z",
      expiresAt: "2027-01-14T00:00:00Z",
      lastUsedAt: null,
      revokedAt: null,
    };
    let created = false;
    const fetcher = vi
      .fn()
      .mockImplementation((_path: string, options: RequestInit) => {
        if (options.method === "POST") {
          created = true;
          return Promise.resolve(
            new Response(JSON.stringify({ ...item, key: secret }), {
              status: 201,
            }),
          );
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: created ? [item] : [],
              activeCount: created ? 1 : 0,
            }),
            { status: 200 },
          ),
        );
      });
    vi.stubGlobal("fetch", fetcher);
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <MemoryRouter>
        <QueryClientProvider client={client}>
          <ApiKeysPage
            scope="tenants/t/projects/p"
            base="/t/t/p/p"
            projectName="Test"
            canWrite
            mfaEnabled
          />
        </QueryClientProvider>
      </MemoryRouter>,
    );
    await screen.findByText("Henüz API anahtarınız yok");
    fireEvent.click(screen.getByRole("button", { name: /Yeni gizli anahtar/ }));
    fireEvent.change(screen.getByPlaceholderText("Örn. ERP entegrasyonu"), {
      target: { value: "ERP" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Anahtarı oluştur" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByDisplayValue(secret)).toBeTruthy();
    await waitFor(() => expect(screen.getByText("ERP")).toBeTruthy());
    expect(
      JSON.stringify(client.getQueryData(["api-keys", "tenants/t/projects/p"])),
    ).not.toContain(secret);
    fireEvent.click(within(dialog).getByRole("button", { name: "Tamam" }));
    expect(screen.queryByDisplayValue(secret)).toBeNull();
  });
});
