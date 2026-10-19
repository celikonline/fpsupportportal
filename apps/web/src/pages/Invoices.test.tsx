// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, expect, it } from "vitest";
import { InvoicesPage } from "./Invoices";

afterEach(cleanup);

function mount(path = "/t/demo/p/demo/invoices") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={<InvoicesPage base="/t/demo/p/demo" />} />
      </Routes>
    </MemoryRouter>,
  );
}

it("shows the outgoing demo list and filters by invoice or account name", () => {
  mount();
  expect(screen.getByText("DEMO-2026-0018")).toBeTruthy();
  expect(screen.queryByText("DEMO-2026-0017")).toBeNull();
  fireEvent.change(screen.getByLabelText("Fatura ara"), {
    target: { value: "Mavi Kırtasiye" },
  });
  expect(screen.getByText("DEMO-2026-0018")).toBeTruthy();
  expect(screen.queryByText("DEMO-2026-0016")).toBeNull();
});

it("shows incoming invoices and filters to draft invoices", () => {
  mount("/t/demo/p/demo/invoices/incoming");
  expect(screen.getByText("DEMO-2026-0017")).toBeTruthy();
  expect(screen.queryByText("DEMO-2026-0018")).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "Taslaklar" }));
  expect(screen.getByText("DEMO-2026-0013")).toBeTruthy();
  expect(screen.queryByText("DEMO-2026-0017")).toBeNull();
});

it("keeps live invoice actions disabled until the product API is connected", () => {
  mount();
  expect(screen.getByRole("button", { name: "Yeni fatura" })).toHaveProperty(
    "disabled",
    true,
  );
  expect(screen.getByRole("button", { name: "Dışa aktar" })).toHaveProperty(
    "disabled",
    true,
  );
  expect(
    screen.getByText(/Canlı FaturaPort\/e-belge bağlantısı henüz yapılmadı/),
  ).toBeTruthy();
});

it("filters invoice lists by read and printed state", () => {
  mount("/t/demo/p/demo/invoices/incoming");
  fireEvent.change(screen.getByLabelText("Okunma durumu"), {
    target: { value: "Okunmadı" },
  });
  expect(screen.getByText("DEMO-2026-0017")).toBeTruthy();
  expect(screen.queryByText("DEMO-2026-0014")).toBeNull();
  fireEvent.change(screen.getByLabelText("Yazdırılma durumu"), {
    target: { value: "Yazdırıldı" },
  });
  expect(screen.queryByText("DEMO-2026-0017")).toBeNull();
});

it("separates invoice and dispatch drafts as in the reference portal", () => {
  mount("/t/demo/p/demo/invoices/drafts");
  expect(screen.getByText("DEMO-2026-0013")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: "İrsaliyeler" }));
  expect(screen.getByText("IRS-DEMO-0004")).toBeTruthy();
  expect(screen.queryByText("DEMO-2026-0013")).toBeNull();
  expect(screen.getByText("Taslak irsaliyeler")).toBeTruthy();
});
