import { describe, it, expect, vi, afterEach } from "vitest";
import { api, setCsrf, command } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("API security transport", () => {
  it("sends CSRF with same-origin session and preserves retry idempotency", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetcher);
    setCsrf("csrf-test");
    await command("tenants/a/projects/p/tickets", { title: "x" }, "stable-key");
    const [path, options] = fetcher.mock.calls[0];
    expect(path).toBe("/api/v1/tenants/a/projects/p/tickets");
    expect(options.credentials).toBe("same-origin");
    expect(options.headers.get("X-CSRFToken")).toBe("csrf-test");
    expect(options.headers.get("Idempotency-Key")).toBe("stable-key");
    expect(options.headers.has("X-Tenant-ID")).toBe(false);
  });
  it("surfaces a denied operation rather than treating error as success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Erişim reddedildi" }), {
          status: 403,
        }),
      ),
    );
    await expect(api("x")).rejects.toThrow("Erişim reddedildi");
  });
});
