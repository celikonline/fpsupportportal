// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { AttachmentComposer } from "./Attachments";
import React from "react";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("Clipboard attachment flow", () => {
  it("uploads a pasted image through a scoped draft and blocks publish while scanning", async () => {
    const fetcher = vi.fn().mockImplementation((path: string) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            path.endsWith("/drafts")
              ? { id: "draft-1" }
              : {
                  id: "file-1",
                  filename: "clipboard.png",
                  mimeType: "image/png",
                  size: 100,
                  state: "scanning",
                  reason: "",
                },
          ),
          { status: 201 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    const onDraft = vi.fn();
    const onBusy = vi.fn();
    const file = new File(["image"], "clipboard.png", { type: "image/png" });
    render(
      <AttachmentComposer
        scope="tenants/a/projects/p"
        onDraft={onDraft}
        onBusy={onBusy}
        pasteFiles={[file]}
      />,
    );
    await waitFor(() => expect(onDraft).toHaveBeenCalledWith("draft-1"));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    expect(fetcher.mock.calls[1][0]).toBe(
      "/api/v1/tenants/a/projects/p/drafts/draft-1/uploads",
    );
    expect(fetcher.mock.calls[1][1].body).toBeInstanceOf(FormData);
    expect(onBusy).toHaveBeenCalledWith(true);
  });
});
