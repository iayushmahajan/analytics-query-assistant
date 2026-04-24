import { useEffect, useMemo, useState } from "react";
import { api } from "./lib/api";
import type { ExampleItem, HistoryItem, QueryResponse } from "./types/query";
import { QueryInputCard } from "./components/QueryInputCard";
import { ExamplePromptsCard } from "./components/ExamplePromptsCard";
import { QueryStatusCard } from "./components/QueryStatusCard";
import { ExplanationCard } from "./components/ExplanationCard";
import { SqlPreviewCard } from "./components/SqlPreviewCard";
import { ResultsTableCard } from "./components/ResultsTableCard";
import { HistoryCard } from "./components/HistoryCard";

const initialResult: QueryResponse | null = null;

function App() {
  const [question, setQuestion] = useState("");
  const [examples, setExamples] = useState<ExampleItem[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [result, setResult] = useState<QueryResponse | null>(initialResult);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function loadExamples() {
    const response = await api.get<ExampleItem[]>("/examples");
    setExamples(response.data);
  }

  async function loadHistory() {
    const response = await api.get<HistoryItem[]>("/history");
    setHistory(response.data);
  }

  useEffect(() => {
    void loadExamples();
    void loadHistory();
  }, []);

  async function runQuery(customQuestion?: string) {
    if (isLoading) return;

    const finalQuestion = (customQuestion ?? question).trim();
    if (!finalQuestion) return;

    setIsLoading(true);
    setErrorMessage("");

    try {
      const response = await api.post<QueryResponse>("/query", {
        question: finalQuestion,
      });

      setQuestion(finalQuestion);
      setResult(response.data);
      await loadHistory();
    } catch (error: any) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail;

      if (status === 429) {
        setErrorMessage(
          "Too many requests. Please wait a moment before trying another query."
        );
      } else {
        setErrorMessage(
          detail || "Something went wrong while running the query."
        );
      }
    } finally {
      setIsLoading(false);
    }
  }

  function clearResults() {
    setResult(null);
    setErrorMessage("");
  }

  async function copySql() {
    if (!result?.generated_sql) return;
    await navigator.clipboard.writeText(result.generated_sql);
  }

  function selectHistoryItem(item: HistoryItem) {
    setResult({
      id: item.id,
      question: item.question,
      generated_sql: item.generated_sql,
      explanation: item.explanation,
      status: item.status,
      columns: [],
      rows: [],
      row_count: item.row_count ?? 0,
      execution_time_ms: item.execution_time_ms ?? 0,
      created_at: item.created_at,
    });
    setQuestion(item.question);
  }

  const status = useMemo(() => result?.status, [result]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-8 rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 p-8 shadow-2xl">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.2em] text-slate-400">
                Analytics Query Assistant
              </p>
              <h1 className="mt-3 text-4xl font-bold tracking-tight text-white">
                Business questions to validated SQL
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
                Ask analytics questions in plain English. The backend generates,
                validates, and executes safe read-only SQL against your
                e-commerce database.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Backend
                </p>
                <p className="mt-1 text-sm font-semibold text-white">FastAPI</p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Database
                </p>
                <p className="mt-1 text-sm font-semibold text-white">PostgreSQL</p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Model
                </p>
                <p className="mt-1 text-sm font-semibold text-white">GPT-4.1</p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Status
                </p>
                <p className="mt-1 text-sm font-semibold text-emerald-400">
                  Ready
                </p>
              </div>
            </div>
          </div>
        </div>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {errorMessage}
          </div>
        )}

        <div className="grid gap-6 xl:grid-cols-[1.4fr_0.8fr]">
          <div className="space-y-6">
            <QueryInputCard
              question={question}
              isLoading={isLoading}
              onQuestionChange={setQuestion}
              onSubmit={() => void runQuery()}
              onClear={clearResults}
            />

            <ExamplePromptsCard
              examples={examples}
              isLoading={isLoading}
              onSelectExample={(value) => {
                setQuestion(value);
              }}
            />

            <QueryStatusCard
              status={status}
              rowCount={result?.row_count}
              executionTimeMs={result?.execution_time_ms}
            />

            <ExplanationCard explanation={result?.explanation} />

            <SqlPreviewCard sql={result?.generated_sql} onCopy={() => void copySql()} />

            <ResultsTableCard
              columns={result?.columns ?? []}
              rows={result?.rows ?? []}
            />
          </div>

          <div className="space-y-6">
            <HistoryCard history={history} onSelectHistoryItem={selectHistoryItem} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;