import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { RetailDashboard } from "./RetailDashboard";
import type { ProductForecast, RetailOverview } from "../types/query";

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
const forecasts: ProductForecast[] = [
  { stock_code: "A1", description: "Paper star", forecast_week: "2011-12-05",
    training_cutoff: "2011-11-28", predicted_units: 35, prediction_lower: 28, prediction_upper: 42,
    baseline_units: 30, model_mae: 4, baseline_mae: 8, test_mae: 5,
    baseline_test_mae: 8, test_wape: 0.18, test_bias: 1.5, interval_coverage: 0.75,
    validation_weeks: 8, test_weeks: 8, confidence: "supported",
    method: "gradient_boosting", history: [],
    backtest: [{ week: "2011-11-28", actual: 32, predicted: 34 }] },
  { stock_code: "B2", description: "Gift bag", forecast_week: "2011-12-05",
    training_cutoff: "2011-11-28", predicted_units: 12, prediction_lower: 2, prediction_upper: 22,
    baseline_units: 12, model_mae: 10, baseline_mae: 5, test_mae: 6,
    baseline_test_mae: 6, test_wape: 0.6, test_bias: -2, interval_coverage: 0.625,
    validation_weeks: 8, test_weeks: 8, confidence: "limited",
    method: "four_week_average", history: [],
    backtest: [{ week: "2011-11-28", actual: 11, predicted: 12 }] },
];

it("shows real sales and the selected forecast's measured error", () => {
  render(<RetailDashboard overview={overview} forecasts={forecasts} failed={false} />);
  expect(screen.getAllByText("£12,345").length).toBeGreaterThan(0);
  expect(screen.getByText("Gross sales")).toBeInTheDocument();
  expect(screen.getByText(/Eight validation weeks/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Gift bag/ }));
  expect(screen.getByText("4-week average")).toBeInTheDocument();
  expect(screen.getAllByText("6 units")).toHaveLength(2);
  expect(screen.getByText("60%")).toBeInTheDocument();
});
