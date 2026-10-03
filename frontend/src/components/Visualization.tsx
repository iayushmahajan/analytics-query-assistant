import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { chartShape, label } from '../lib/results';
import type { Cell } from '../types/query';

export function Visualization({ columns, rows }: { columns: string[]; rows: Cell[][] }) {
  const shape = chartShape(columns, rows);
  if (!shape) return null;
  const common = <><CartesianGrid stroke="#263449" vertical={false}/><XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} minTickGap={24}/><YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} width={72}/><Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }} /></>;
  return <figure aria-label={`${shape.kind === 'line' ? 'Line' : 'Bar'} chart of ${label(shape.measure)} by ${label(shape.dimension)}`}>
    <figcaption className="mb-4 text-sm capitalize text-slate-300">{label(shape.measure)} by {label(shape.dimension)} · values from returned rows</figcaption>
    <div className="h-80 min-w-0"><ResponsiveContainer width="100%" height="100%">
      {shape.kind === 'line' ? <LineChart data={shape.data}>{common}<Line type="monotone" dataKey="value" name={label(shape.measure)} stroke="#2dd4bf" strokeWidth={2} isAnimationActive={false}/></LineChart> :
      <BarChart data={shape.data}>{common}<Bar dataKey="value" name={label(shape.measure)} fill="#2dd4bf" radius={[4,4,0,0]} isAnimationActive={false}/></BarChart>}
    </ResponsiveContainer></div>
  </figure>;
}
