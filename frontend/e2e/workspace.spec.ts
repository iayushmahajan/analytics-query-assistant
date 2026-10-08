import { expect, test } from "@playwright/test";
import { clarification, result } from "../src/test/fixtures";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith("/health")
      ? { status: "ok" }
      : path.endsWith("/history/1")
        ? result
        : path.endsWith("/history")
          ? [{ id: 1, question: "Gross sales?", dataset: "retail", status: "success",
              row_count: 1, created_at: result.created_at }]
          : path.endsWith("/retail/overview")
            ? { available: false }
            : [];
    await route.fulfill({ json: data });
  });
});

test("retail chart, table, CSV and restored history", async ({ page }) => {
  await page.route("**/api/query", (route) =>
    route.fulfill({ json: {
      ...result,
      columns: ["country", "gross_sales"],
      rows: [["United Kingdom", "100"], ["France", "300"]],
      row_count: 2,
    } }),
  );
  await page.goto("/");
  await page.getByLabel("What would you like to understand?").fill("Gross sales by country");
  await page.getByRole("button", { name: "Analyze sales" }).click();
  await expect(page.getByRole("figure")).toBeVisible();
  await expect(page.locator(".recharts-bar")).toBeVisible();
  await page.getByRole("button", { name: "Table", exact: true }).click();
  await expect(page.getByRole("table")).toContainText("France");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  expect((await download).suggestedFilename()).toBe("sales-analysis.csv");
  await page.getByText("Recent analyses").click();
  await page.getByRole("button", { name: /Gross sales\?/ }).click();
  await expect(page.getByRole("table")).toContainText("£123.45");
});

test("clarification, line chart, and failed query on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let calls = 0;
  await page.route("**/api/query", async (route) => {
    calls++;
    if (calls === 1) return route.fulfill({ json: clarification });
    if (calls === 2) {
      expect(route.request().postDataJSON().clarification[0].answer).toBe("Gross sales");
      return route.fulfill({ json: { ...result,
        columns: ["month", "gross_sales"],
        rows: [["2011-01-01", "100"], ["2011-02-01", "200"]], row_count: 2 } });
    }
    return route.fulfill({ status: 504, json: { error: { message: "The query timed out." } } });
  });
  await page.goto("/");
  await page.getByLabel("What would you like to understand?").fill("Performance");
  await page.getByRole("button", { name: "Analyze sales" }).click();
  await expect(page.getByText("No SQL has been executed.", { exact: false })).toBeVisible();
  await page.getByLabel("Your clarification").fill("Gross sales");
  await page.getByRole("button", { name: "Continue analysis" }).click();
  await expect(page.locator(".recharts-line")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole("button", { name: "Analyze sales" }).click();
  await expect(page.getByRole("alert")).toContainText("timed out");
});
