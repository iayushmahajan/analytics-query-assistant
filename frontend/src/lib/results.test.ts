import { describe, expect, it } from 'vitest';
import { chartShape, formatCell, toCsv } from './results';
describe('result presentation', () => {
  it('chooses charts only for supported shapes', () => {
    expect(chartShape(['month','revenue'], [['2025-01-01','100'],['2025-02-01','200']])?.kind).toBe('line');
    expect(chartShape(['category','revenue'], [['Books','100'],['Tools','200']])?.kind).toBe('bar');
    expect(chartShape(['id','revenue'], [[1,100],[2,200]])).toBeNull();
    expect(chartShape(['a','b','c'], [['x',1,2],['y',3,4]])).toBeNull();
  });
  it('formats exact numeric strings and nulls', () => {
    expect(formatCell('1234.5','revenue')).toBe('€1,234.50');
    expect(formatCell(null,'value')).toBe('—');
  });
  it('quotes CSV and neutralizes spreadsheet formulas', () => {
    expect(toCsv(['name','amount'], [['a,"b',1],['=HYPERLINK("bad")',null]])).toContain('"a,""b"');
    expect(toCsv(['name'], [['=cmd']])).toContain("'=cmd");
  });
});
