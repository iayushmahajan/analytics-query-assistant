import { describe, expect, it } from "vitest";
import { chartShape, formatCell, toCsv } from "./results";

describe("result presentation", () => {
  it("chooses charts only for supported shapes", () => {
    expect(chartShape(["period", "retail_index"], [["2026-01-01", "100"], ["2026-02-01", "101"]])?.kind).toBe("line");
    expect(chartShape(["geography", "yearly_change"], [["France", "1"], ["Germany", "2"]])?.kind).toBe("bar");
    expect(chartShape(["id", "value"], [[1, 100], [2, 200]])).toBeNull();
    expect(chartShape(["a", "b", "c"], [["x", 1, 2], ["y", 3, 4]])).toBeNull();
  });

  it("formats indices, index-point changes, percentages, currencies and nulls", () => {
    expect(formatCell("104.2", "retail_index")).toBe("104.2");
    expect(formatCell("-1.25", "yearly_change")).toBe("-1.25 pts");
    expect(formatCell("79.4", "coverage")).toBe("79.4%");
    expect(formatCell("1234.5", "sales", "EUR")).toBe("€1,234.50");
    expect(formatCell("1234.5", "sales")).toBe("1,234.5");
    expect(formatCell(null, "value")).toBe("—");
  });

  it("quotes CSV and neutralizes spreadsheet formulas", () => {
    expect(toCsv(["name", "value"], [['a,"b', 1], ['=HYPERLINK("bad")', null]])).toContain('"a,""b"');
    expect(toCsv(["name"], [["=cmd"]])).toContain("'=cmd");
  });
});
