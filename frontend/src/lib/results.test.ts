import { describe, expect, it } from "vitest";
import { chartShape, formatCell, toCsv } from "./results";
describe("result presentation", () => {
  it("chooses charts only for supported shapes", () => {
    expect(
      chartShape(
        ["month", "gross_sales"],
        [
          ["2011-01-01", "100"],
          ["2011-02-01", "200"],
        ],
      )?.kind,
    ).toBe("line");
    expect(
      chartShape(
        ["country", "gross_sales"],
        [
          ["France", "100"],
          ["United Kingdom", "200"],
        ],
      )?.kind,
    ).toBe("bar");
    expect(
      chartShape(
        ["id", "gross_sales"],
        [
          [1, 100],
          [2, 200],
        ],
      ),
    ).toBeNull();
    expect(
      chartShape(
        ["a", "b", "c"],
        [
          ["x", 1, 2],
          ["y", 3, 4],
        ],
      ),
    ).toBeNull();
  });
  it("formats exact numeric strings and nulls", () => {
    expect(formatCell("1234.5", "gross_sales")).toBe("£1,234.50");
    expect(formatCell("1234.5", "gross_sales", "GBP")).toBe("£1,234.50");
    expect(formatCell(null, "value")).toBe("—");
  });
  it("quotes CSV and neutralizes spreadsheet formulas", () => {
    expect(
      toCsv(
        ["name", "amount"],
        [
          ['a,"b', 1],
          ['=HYPERLINK("bad")', null],
        ],
      ),
    ).toContain('"a,""b"');
    expect(toCsv(["name"], [["=cmd"]])).toContain("'=cmd");
  });
});
