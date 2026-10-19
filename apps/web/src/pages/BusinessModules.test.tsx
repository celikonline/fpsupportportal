// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { BusinessModulesPage } from "./BusinessModules";

afterEach(cleanup);

function mount(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={<BusinessModulesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

it("filters account movements by account tab and search", () => {
  mount("/t/demo/p/demo/business/accounts");
  expect(screen.getByText("İş Bankası")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: "Kasa" }));
  expect(screen.getByText("Ana kasa")).toBeTruthy();
  expect(screen.queryByText("İş Bankası")).toBeNull();
  fireEvent.change(screen.getByLabelText("Hesaplar ara"), {
    target: { value: "tahsilat" },
  });
  expect(screen.getByText("Ana kasa")).toBeTruthy();
});

it("shows product reports as demo and keeps downloads disabled", () => {
  mount("/t/demo/p/demo/business/reports");
  expect(screen.getByText("Fatura özeti")).toBeTruthy();
  expect(
    screen
      .getAllByRole("button", { name: "İndir" })
      .every((button) => (button as HTMLButtonElement).disabled),
  ).toBe(true);
  expect(screen.getByText(/Sentetik demo kayıtları gösteriliyor/)).toBeTruthy();
});
