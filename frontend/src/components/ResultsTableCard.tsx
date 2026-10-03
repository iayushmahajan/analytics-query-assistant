import { useMemo, useState } from 'react';
import type { Cell } from '../types/query';
import { downloadCsv, formatCell, label, numeric } from '../lib/results';

type Props = { columns: string[]; rows: Cell[][] };
export function ResultsTableCard({ columns, rows }: Props) {
  const [sort, setSort] = useState<{ index: number; ascending: boolean } | null>(null);
  const sorted = useMemo(() => [...rows].sort((a,b) => {
    if (!sort) return 0;
    const av = a[sort.index], bv = b[sort.index];
    const an = numeric(av), bn = numeric(bv);
    const order = an !== null && bn !== null ? an - bn : String(av ?? '').localeCompare(String(bv ?? ''));
    return sort.ascending ? order : -order;
  }), [rows, sort]);
  return <section aria-label="Result table">
    <div className="mb-3 flex items-center justify-between"><p className="text-sm text-slate-400">{rows.length} returned rows</p>
      <button className="secondary" disabled={!rows.length} onClick={() => downloadCsv(columns, sorted)}>Export CSV</button></div>
    {!rows.length ? <p className="rounded-xl bg-slate-950 p-6 text-slate-400">No matching data for these filters. Try a different date range.</p> :
      <div className="overflow-x-auto rounded-xl border border-slate-700"><table className="w-full text-left text-sm">
        <caption className="sr-only">Query results, sortable by column</caption>
        <thead className="bg-slate-950"><tr>{columns.map((column, index) => <th key={column} aria-sort={sort?.index === index ? sort.ascending ? 'ascending' : 'descending' : 'none'} className="p-3">
          <button className="whitespace-nowrap capitalize" onClick={() => setSort({ index, ascending: sort?.index === index ? !sort.ascending : true })}>{label(column)} {sort?.index === index ? sort.ascending ? '↑' : '↓' : '↕'}</button>
        </th>)}</tr></thead>
        <tbody className="divide-y divide-slate-800">{sorted.map((row, index) => <tr key={index} className="hover:bg-slate-800/50">{row.map((cell, cellIndex) => <td key={cellIndex} className="whitespace-nowrap p-3 tabular-nums text-slate-200">{formatCell(cell, columns[cellIndex])}</td>)}</tr>)}</tbody>
      </table></div>}
  </section>;
}
