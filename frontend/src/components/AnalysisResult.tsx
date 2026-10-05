import { lazy, Suspense, useState } from "react";
import type { QueryResponse } from "../types/query";
import { chartShape, formatCell, label, numeric } from "../lib/results";
import { ResultsTableCard } from "./ResultsTableCard";
import { SqlPreviewCard } from "./SqlPreviewCard";
const Visualization = lazy(() =>
  import("./Visualization").then((module) => ({
    default: module.Visualization,
  })),
);

export function AnalysisResult({
  result,
  onFollowUp,
  disabled,
}: {
  result: QueryResponse;
  onFollowUp: (question: string) => void;
  disabled: boolean;
}) {
  const [view, setView] = useState<"chart" | "table">(
    chartShape(result.columns, result.rows) ? "chart" : "table",
  );
  const { plan, analysis, metric_definition: metric } = result;
  const chart = chartShape(result.columns, result.rows);
  return (
    <div className="space-y-5">
      <section className="panel" aria-label="Analysis answer">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl font-semibold text-white">
            {metric?.name ?? "Analysis"}
          </h2>
          <span className="badge">
            {result.row_count} rows ·{" "}
            {(result.timings.total_ms / 1000).toFixed(1)}s processing
          </span>
        </div>
        <p className="mt-3 text-lg leading-relaxed text-slate-100">
          {analysis?.answer ??
            (result.row_count
              ? "Query complete. Explore the returned data below."
              : "No matching records were returned.")}
        </p>
        <p className="mt-2 text-xs text-slate-400">
          SQL passed structural checks. AI interpretation and findings may
          contain errors; inspect the assumptions.
        </p>
        {result.rows.length === 1 && (
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {result.columns.map(
              (column, i) =>
                numeric(result.rows[0][i]) !== null && (
                  <div
                    className="rounded-xl border border-slate-700 bg-slate-950 p-4"
                    key={column}
                  >
                    <p className="text-sm capitalize text-slate-400">
                      {label(column)}
                    </p>
                    <p className="mt-2 text-2xl font-semibold tabular-nums text-teal-300">
                      {formatCell(result.rows[0][i], column)}
                    </p>
                  </div>
                ),
            )}
          </div>
        )}
        {result.possibly_truncated && (
          <p className="mt-4 text-sm text-amber-300">
            The result reached the row cap and may be incomplete. Narrow the
            question before drawing conclusions.
          </p>
        )}
        {result.warnings.map((warning) => (
          <p
            role="status"
            className="mt-3 text-sm text-amber-300"
            key={warning}
          >
            {warning}
          </p>
        ))}
      </section>
      <section className="panel">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">Explore results</h2>
          {chart && (
            <div className="flex gap-2" role="group" aria-label="Result view">
              <button
                className="secondary"
                aria-pressed={view === "chart"}
                onClick={() => setView("chart")}
              >
                Chart
              </button>
              <button
                className="secondary"
                aria-pressed={view === "table"}
                onClick={() => setView("table")}
              >
                Table
              </button>
            </div>
          )}
        </div>
        {chart && view === "chart" ? (
          <Suspense fallback={<p role="status">Loading chart…</p>}>
            <Visualization columns={result.columns} rows={result.rows} />
          </Suspense>
        ) : (
          <ResultsTableCard columns={result.columns} rows={result.rows} />
        )}
      </section>
      {analysis && (
        <section className="panel">
          <h2 className="font-semibold">AI findings</h2>
          {(
            [
              ["Key findings", analysis.findings],
              ["Trends", analysis.trends],
              ["Notable observations", analysis.anomalies],
              ["Caveats", analysis.caveats],
            ] as const
          )
            .filter(([, items]) => items.length)
            .map(([title, items]) => (
              <div className="mt-4" key={title}>
                <h3 className="text-sm font-semibold text-slate-300">
                  {title}
                </h3>
                <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-400">
                  {items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}
          <div className="mt-4 flex flex-wrap gap-2">
            {analysis.follow_up_questions.map((q) => (
              <button
                className="chip"
                key={q}
                disabled={disabled}
                onClick={() => onFollowUp(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </section>
      )}
      <details className="panel" open>
        <summary className="cursor-pointer font-semibold">
          Interpretation & assumptions
        </summary>
        <p className="mt-3 text-sm text-slate-300">{plan?.interpretation}</p>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
          {[
            ["Metric definition", metric?.calculation],
            ["Date range", plan?.date_range],
            ["Currency", "EUR · single-currency synthetic dataset"],
            ["Canonical statuses", metric?.included_statuses.join(", ") || "Not applicable"],
            [
              "Applied filters (AI interpretation)",
              plan?.filters.join("; ") || "No additional filters",
            ],
            ["Source tables (SQL verified)", plan?.source_tables.join(", ")],
          ].map(([name, value]) => (
            <div key={name}>
              <dt className="text-slate-500">{name}</dt>
              <dd className="mt-1 break-words text-slate-200">{value}</dd>
            </div>
          ))}
        </dl>
        {!!plan?.assumptions.length && (
          <ul className="mt-4 list-disc pl-5 text-sm text-slate-400">
            {plan.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        )}
        <p className="mt-4 text-xs text-slate-500">
          Generation {result.timings.generation_ms}ms · SQL{" "}
          {result.timings.execution_ms}ms · Findings{" "}
          {result.timings.analysis_ms}ms · Saved{" "}
          {new Date(result.created_at).toLocaleString()}
        </p>
      </details>
      <SqlPreviewCard sql={result.generated_sql} />
    </div>
  );
}
