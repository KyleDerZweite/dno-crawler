import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { api } from "@/lib/api";
import { PublicSearchPanel } from "./PublicSearchPanel";

vi.mock("@/lib/api", () => ({ api: { publicSearch: { search: vi.fn() } } }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe("public search dependency contracts", () => {
  it("validates coordinates and preserves decimal-comma payloads and empty results", async () => {
    vi.mocked(api.publicSearch.search).mockResolvedValue({ found: false, has_data: false });
    render(<MemoryRouter><PublicSearchPanel /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Coordinates" }));
    const search = screen.getByRole("button", { name: "Search" });
    fireEvent.change(screen.getByPlaceholderText(/Latitude/), { target: { value: "91" } });
    fireEvent.change(screen.getByPlaceholderText(/Longitude/), { target: { value: "6,9578" } });
    expect(search).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText(/Latitude/), { target: { value: "50,9413" } });
    fireEvent.keyDown(screen.getByPlaceholderText(/Latitude/), { key: "Enter" });
    expect(await screen.findByText("No DNO Found")).toBeInTheDocument();
    expect(api.publicSearch.search).toHaveBeenCalledWith({
      coordinates: { latitude: 50.9413, longitude: 6.9578 }, years: [2025, 2024],
    });
  });

  it("recovers from rate limiting and preserves the nested DNO import route", async () => {
    vi.mocked(api.publicSearch.search)
      .mockRejectedValueOnce({ response: { status: 429 } })
      .mockResolvedValueOnce({ found: true, has_data: false,
        dno: { id: 42, slug: "test-netz", name: "Test Netz", status: "pending" } });
    render(<MemoryRouter><PublicSearchPanel showImportLinkForSkeleton /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "DNO Name" }));
    fireEvent.change(screen.getByPlaceholderText(/DNO Name/i), { target: { value: "Test Netz" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText(/Rate limit exceeded/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Test Netz")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Import Data" })).toHaveAttribute("href", "/dnos/42");
    expect(screen.queryByText(/Rate limit exceeded/)).not.toBeInTheDocument();
  });
});
