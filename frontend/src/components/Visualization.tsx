import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { chartShape, label } from "../lib/results";
import type { Cell } from "../types/query";

export function Visualization({
  columns,
  rows,
}: {
  columns: string[];
  rows: Cell[][];
}) {
  const shape = chartShape(columns, rows);
  if (!shape) return null;
  const colors = ["#5b3df5", "#35aaa2", "#e09a42", "#b64c78"];
  const common = (
    <>
      <CartesianGrid stroke="#e2e8f0" vertical={false} />
      <XAxis
        dataKey="name"
        tick={{ fill: "#64748b", fontSize: 11 }}
        minTickGap={24}
      />
      <YAxis tick={{ fill: "#64748b", fontSize: 11 }} width={72} />
      <Tooltip
        contentStyle={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: 8,
          color: "#0f172a",
        }}
      />
    </>
  );
  return (
    <figure
      aria-label={`${shape.kind === "line" ? "Line" : "Bar"} chart of ${shape.measures.map(label).join(" and ")} by ${label(shape.dimension)}`}
    >
      <figcaption className="mb-4 text-sm capitalize text-slate-600">
        {shape.measures.map(label).join(" and ")} by {label(shape.dimension)} · values from
        returned rows
      </figcaption>
      <div className="h-80 min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          {shape.kind === "line" ? (
            <LineChart data={shape.data}>
              {common}
              {shape.measures.map((measure, index) => (
                <Line
                  key={measure}
                  type="monotone"
                  dataKey={measure}
                  name={label(measure)}
                  stroke={colors[index % colors.length]}
                  strokeWidth={measure.includes("gap") ? 1.5 : 2.4}
                  strokeDasharray={measure.includes("gap") ? "5 4" : undefined}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          ) : (
            <BarChart data={shape.data}>
              {common}
              {shape.measures.map((measure, index) => (
                <Bar
                  key={measure}
                  dataKey={measure}
                  name={label(measure)}
                  fill={colors[index % colors.length]}
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
