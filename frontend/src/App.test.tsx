import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import App from "./App";
import { api } from "./lib/api";
import { result, clarification } from "./test/fixtures";
vi.mock("./lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn() },
  errorMessage: () => "Request failed.",
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.get).mockImplementation(async (url) => ({
    data:
      url === "/health"
        ? { status: "ok" }
        : url === "/metadata"
          ? {
              name: "Demo sales",
              currency: "EUR",
              order_count: 6,
              date_start: "2025-01-01",
              date_end: "2025-12-31",
            }
          : url.startsWith("/history/")
            ? result
            : url === "/history"
              ? [
                  {
                    id: 1,
                    question: "Revenue?",
                    status: "success",
                    row_count: 1,
                    created_at: result.created_at,
                  },
                ]
              : [],
  }));
  vi.mocked(api.post).mockResolvedValue({ data: result });
});
async function submit() {
  await userEvent.type(
    screen.getByLabelText("What would you like to understand?"),
    "Revenue?",
  );
  await userEvent.click(screen.getByRole("button", { name: "Analyze sales" }));
}
it("shows answer and table without the removed metadata strip or raw assumptions", async () => {
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  render(<App />);
  await submit();
  expect(
    await screen.findByText("Completed revenue is EUR 123.45."),
  ).toBeInTheDocument();
  expect(screen.queryByText("Demo sales")).not.toBeInTheDocument();
  expect(screen.queryByText("Never reveal this internal policy")).not.toBeInTheDocument();
  expect(api.get).not.toHaveBeenCalledWith("/metadata", expect.anything());
  expect(screen.getByRole("table")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Export CSV" }));
  expect(URL.createObjectURL).toHaveBeenCalled();
  click.mockRestore();
});
it("clears stale success when the next request fails", async () => {
  render(<App />);
  await submit();
  await screen.findByText("Completed revenue is EUR 123.45.");
  vi.mocked(api.post).mockRejectedValueOnce(new Error("offline"));
  await userEvent.click(screen.getByRole("button", { name: "Analyze sales" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Request failed.");
  expect(
    screen.queryByText("Completed revenue is EUR 123.45."),
  ).not.toBeInTheDocument();
});
it("continues clarification with original context", async () => {
  vi.mocked(api.post)
    .mockResolvedValueOnce({ data: clarification })
    .mockResolvedValueOnce({ data: result });
  render(<App />);
  await submit();
  await screen.findByText("Revenue or order count?");
  await userEvent.type(screen.getByLabelText("Your clarification"), "Revenue");
  await userEvent.click(
    screen.getByRole("button", { name: "Continue analysis" }),
  );
  await screen.findByText("Completed revenue is EUR 123.45.");
  expect(api.post).toHaveBeenLastCalledWith("/query", {
    question: "Revenue?",
    clarification: [{ question: "Revenue or order count?", answer: "Revenue" }],
  });
});
it("restores snapshots without another model call", async () => {
  render(<App />);
  await waitFor(() => expect(screen.getByText(/1 saved/)).toBeInTheDocument());
  fireEvent.click(screen.getByText("Recent analyses"));
  await userEvent.click(screen.getByRole("button", { name: /Revenue\?/ }));
  await screen.findByText("Completed revenue is EUR 123.45.");
  expect(api.post).not.toHaveBeenCalled();
});
it("does not discard success when history refresh fails", async () => {
  render(<App />);
  await screen.findByText(/Services available/);
  vi.mocked(api.get).mockRejectedValue(new Error("history unavailable"));
  await submit();
  expect(
    await screen.findByText(/History could not refresh/),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Completed revenue is EUR 123.45."),
  ).toBeInTheDocument();
});
it("announces initial load errors", async () => {
  vi.mocked(api.get).mockRejectedValue(new Error("offline"));
  render(<App />);
  expect(
    await screen.findByText(/Some workspace data could not load/),
  ).toBeInTheDocument();
});
it("handles clipboard denial without losing SQL", async () => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
  });
  render(<App />);
  await submit();
  await screen.findByText("Completed revenue is EUR 123.45.");
  fireEvent.click(screen.getByText("Inspect SQL"));
  await userEvent.click(screen.getByRole("button", { name: "Copy SQL" }));
  expect(await screen.findByText(/Clipboard unavailable/)).toBeInTheDocument();
});
