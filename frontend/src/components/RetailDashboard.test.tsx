import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { RetailDashboard } from "./RetailDashboard";
import type { RetailOverview } from "../types/query";
import { marketForecast as forecast } from "../test/fixtures";

const overview: RetailOverview = {
  available: true, source: "UCI Online Retail · CC BY 4.0", currency: "GBP",
  start: "2010-12-01", end: "2011-12-09", source_lines: 100,
  sale_lines: 90, excluded_lines: 10, sales_invoices: 20,
  gross_sales: 12345, units: 350,
  imported_at: "2026-10-08T10:00:00Z", source_sha256: "abcdef0123456789", dropped_lines: 2,
  months: [{ month: "2011-01", gross_sales: 12345, units: 350 }],
  products: [{ name: "Paper star", gross_sales: 2345, units: 30 }],
  countries: [{ name: "United Kingdom", gross_sales: 12345, units: 350 }],
};

it("shows the current Germany forecast with out-of-sample evidence", () => {
  render(<RetailDashboard overview={overview} forecast={forecast} failed={false} />);
  expect(screen.getAllByText("£12,345").length).toBeGreaterThan(0);
  expect(screen.getByText("Historical sales analysis")).toBeInTheDocument();
  expect(screen.getByText("Germany retail outlook")).toBeInTheDocument();
  expect(screen.getByText(/independent German market series/)).toBeInTheDocument();
  expect(screen.getByText("+1.0 points")).toBeInTheDocument();
  expect(screen.getByText("+12.0 points")).toBeInTheDocument();
  expect(screen.getByText("Gradient boosting")).toBeInTheDocument();
  expect(screen.getByText("2.1%")).toBeInTheDocument();
  expect(screen.getByText(/Aug 2026 · provisional/)).toBeInTheDocument();
  expect(screen.getByText(/has no products, customers/)).toBeInTheDocument();
  expect(screen.getByText(/not a guaranteed result/)).toBeInTheDocument();
});

it("explains how to build a missing market forecast", () => {
  render(<RetailDashboard overview={overview} forecast={{ ...forecast, available: false }} failed={false} />);
  expect(screen.getByText("Germany forecast is ready to build")).toBeInTheDocument();
});

it("keeps a forecast request failure separate from the retail overview", () => {
  render(<RetailDashboard overview={overview} forecast={null} failed={false} />);
  expect(screen.getByText("Historical sales analysis")).toBeInTheDocument();
  expect(screen.getByText("Loading Germany market data")).toBeInTheDocument();
});
