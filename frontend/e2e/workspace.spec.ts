import { expect, test } from "@playwright/test";
import { clarification, result } from "../src/test/fixtures";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith("/health")
      ? { status: "ok" }
      : path.endsWith("/metadata")
        ? {
            name: "Demo sales",
            currency: "EUR",
            order_count: 6,
            date_start: "2025-01-01",
            date_end: "2025-12-31",
          }
        : path.endsWith("/history/1")
          ? result
          : path.endsWith("/history")
            ? [
                {
                  id: 1,
                  question: "Revenue?",
                  status: "success",
                  row_count: 1,
                  created_at: result.created_at,
                },
              ]
            : [];
    await route.fulfill({ json: data });
  });
});

test("category chart, table, CSV and restored history", async ({ page }) => {
  await page.route("**/api/query", (route) =>
    route.fulfill({
      json: {
        ...result,
        columns: ["category", "revenue"],
        rows: [
          ["Books", "100"],
          ["Electronics", "300"],
        ],
        row_count: 2,
      },
    }),
  );
  await page.goto("/");
  await page
    .getByLabel("What would you like to understand?")
    .fill("Revenue by category");
  await page.getByRole("button", { name: "Analyze sales" }).click();
  await expect(page.getByRole("figure")).toBeVisible();
  await expect(page.locator(".recharts-bar")).toBeVisible();
  await page.getByRole("button", { name: "Table", exact: true }).click();
  await expect(page.getByRole("table")).toContainText("Electronics");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  expect((await download).suggestedFilename()).toBe("sales-analysis.csv");
  await page.getByText("Recent analyses").click();
  await page.getByRole("button", { name: /Revenue\?/ }).click();
  await expect(page.getByRole("table")).toContainText("€123.45");
});

test("clarification, line chart, then failed query clears results on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let calls = 0;
  await page.route("**/api/query", async (route) => {
    calls++;
    if (calls === 1) return route.fulfill({ json: clarification });
    if (calls === 2) {
      expect(route.request().postDataJSON().clarification[0].answer).toBe(
        "Monthly revenue",
      );
      return route.fulfill({
        json: {
          ...result,
          columns: ["month", "revenue"],
          rows: [
            ["2025-01-01", "100"],
            ["2025-02-01", "200"],
          ],
          row_count: 2,
        },
      });
    }
    return route.fulfill({
      status: 504,
      json: { error: { message: "The query timed out." } },
    });
  });
  await page.goto("/");
  await page
    .getByLabel("What would you like to understand?")
    .fill("Performance");
  await page.getByRole("button", { name: "Analyze sales" }).click();
  await expect(
    page.getByText("No SQL has been executed.", { exact: false }),
  ).toBeVisible();
  await page.getByLabel("Your clarification").fill("Monthly revenue");
  await page.getByRole("button", { name: "Continue analysis" }).click();
  await expect(page.locator(".recharts-line")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Analyze sales" }).click();
  await expect(page.getByRole("alert")).toContainText("timed out");
  await expect(page.getByRole("figure")).toHaveCount(0);
});
