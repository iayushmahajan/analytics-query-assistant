import { useEffect, useState } from "react";
import { api, errorMessage } from "./lib/api";
import type {
  ClarificationTurn,
  ExampleItem,
  Health,
  HistoryItem,
  QueryResponse,
} from "./types/query";
import { QueryInputCard } from "./components/QueryInputCard";
import { HistoryCard } from "./components/HistoryCard";
import { AnalysisResult } from "./components/AnalysisResult";

function App() {
  const [question, setQuestion] = useState("");
  const [examples, setExamples] = useState<ExampleItem[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [answer, setAnswer] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const config = { signal: controller.signal };
    void Promise.allSettled([
      api.get<ExampleItem[]>("/examples", config),
      api.get<HistoryItem[]>("/history", config),
      api.get<Health>("/health", {
        ...config,
        validateStatus: (status) => status === 200 || status === 503,
      }),
    ]).then(([ex, hist, state]) => {
      if (controller.signal.aborted) return;
      if (ex.status === "fulfilled") setExamples(ex.value.data);
      if (hist.status === "fulfilled") setHistory(hist.value.data);
      if (state.status === "fulfilled") setHealth(state.value.data);
      if ([ex, hist, state].some((item) => item.status === "rejected"))
        setNotice(
          "Some workspace data could not load. You can retry history below or reload the page.",
        );
      setInitializing(false);
    });
    return () => controller.abort();
  }, []);

  async function refreshHistory() {
    try {
      setHistory((await api.get<HistoryItem[]>("/history")).data);
    } catch {
      setNotice(
        "History could not refresh. Your current analysis is still available.",
      );
    }
  }
  async function run(
    originalQuestion = question,
    clarification: ClarificationTurn[] = [],
  ) {
    if (busy || !originalQuestion.trim()) return;
    setBusy(true);
    setResult(null);
    setError("");
    setNotice("");
    setAnswer("");
    try {
      const response = await api.post<QueryResponse>("/query", {
        question: originalQuestion.trim(),
        clarification,
      });
      setResult(response.data);
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
    await refreshHistory();
  }
  async function restore(item: HistoryItem) {
    if (busy) return;
    setBusy(true);
    setResult(null);
    setError("");
    setNotice("");
    setAnswer("");
    try {
      const response = await api.get<QueryResponse>(`/history/${item.id}`);
      setResult(response.data);
      setQuestion(response.data.question);
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  const clarificationQuestion = result?.plan?.clarification_question;
  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
      <header className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-400">
            Analytics Query Assistant
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
            Sales, understood.
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Explore your data. See the reasoning. Inspect the evidence.
          </p>
        </div>
        <span role="status" className="badge">
          {initializing
            ? "Checking services…"
            : health?.status === "ok"
              ? "Services available · AI ready"
              : health?.provider === "unavailable" ||
                  health?.provider === "model_not_loaded" ||
                  health?.provider === "not_configured"
                ? "AI provider unavailable"
                : "Service attention needed"}
        </span>
      </header>
      <div className="space-y-5">
        <QueryInputCard
          question={question}
          examples={examples}
          isLoading={busy}
          onQuestionChange={setQuestion}
          onSubmit={() => void run()}
          onClear={() => {
            setResult(null);
            setError("");
            setAnswer("");
          }}
        />
        {notice && (
          <p
            role="status"
            className="rounded-xl border border-amber-800 bg-amber-950/30 p-4 text-sm text-amber-200"
          >
            {notice}
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-xl border border-red-800 bg-red-950/30 p-4 text-sm text-red-200"
          >
            {error}
          </p>
        )}
        <div aria-live="polite" aria-busy={busy}>
          {result?.status === "needs_clarification" && (
            <section
              className="panel border-amber-700"
              aria-label="Clarification required"
            >
              <h2 className="text-lg font-semibold">
                One detail before we query
              </h2>
              <p className="mt-2 text-slate-300">{clarificationQuestion}</p>
              <p className="mt-1 text-xs text-slate-400">
                Original question: {result.question} · No SQL has been executed.
              </p>
              {result.clarification.length >= 3 ? (
                <p className="mt-4 text-amber-200">
                  Please start a new question with the details gathered so far.
                </p>
              ) : (
                <form
                  className="mt-4 flex flex-col gap-3 sm:flex-row"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (clarificationQuestion)
                      void run(result.question, [
                        ...result.clarification,
                        { question: clarificationQuestion, answer },
                      ]);
                  }}
                >
                  <label className="sr-only" htmlFor="clarification">
                    Your clarification
                  </label>
                  <input
                    id="clarification"
                    className="input"
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    maxLength={2000}
                  />
                  <button
                    className="primary shrink-0"
                    disabled={busy || !answer.trim()}
                  >
                    Continue analysis
                  </button>
                </form>
              )}
            </section>
          )}
          {(result?.status === "blocked" || result?.status === "failed") && (
            <section role="alert" className="panel border-amber-700">
              <h2 className="font-semibold">
                {result.status === "blocked"
                  ? "Request not executed"
                  : "Analysis unavailable"}
              </h2>
              <p className="mt-2 text-slate-300">
                {result.error?.message ?? result.plan?.explanation}
              </p>
            </section>
          )}
          {result?.status === "success" && (
            <AnalysisResult
              key={result.request_id}
              result={result}
              onFollowUp={setQuestion}
              disabled={busy}
            />
          )}
        </div>
        <HistoryCard
          history={history}
          isLoading={busy}
          onRefresh={() => void refreshHistory()}
          onSelectHistoryItem={(item) => void restore(item)}
        />
      </div>
      <footer className="mt-8 text-xs leading-relaxed text-slate-500">
        Synthetic sales data · EUR · Shared demonstration workspace, no private
        accounts. Questions go to the AI provider. Do not enter personal or
        confidential information.
      </footer>
    </main>
  );
}
export default App;
