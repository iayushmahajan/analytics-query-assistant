import type { ExampleItem } from "../types/query";

type Props = {
  question: string;
  isLoading: boolean;
  examples: ExampleItem[];
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
  onClear: () => void;
};
export function QueryInputCard({
  question,
  isLoading,
  examples,
  onQuestionChange,
  onSubmit,
  onClear,
}: Props) {
  return (
    <section className="panel">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <label
          htmlFor="question"
          className="block text-lg font-semibold text-white"
        >
          What would you like to understand?
        </label>
        <p id="question-hint" className="mt-1 text-sm text-slate-400">
          Ask about revenue, orders, customers or product sales. Revenue
          includes completed orders.
        </p>
        <textarea
          id="question"
          aria-describedby="question-hint"
          maxLength={2000}
          value={question}
          disabled={isLoading}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="How did monthly revenue change during 2025?"
          className="input mt-4 min-h-24"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button className="primary" disabled={isLoading || !question.trim()}>
            {isLoading ? "Analyzing…" : "Analyze sales"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={isLoading}
            onClick={onClear}
          >
            Clear results
          </button>
          {isLoading && (
            <span role="status" className="text-sm text-slate-400">
              Interpreting, querying and preparing findings…
            </span>
          )}
        </div>
      </form>
      <div className="mt-4 flex flex-wrap gap-2" aria-label="Example questions">
        {examples.map((example) => (
          <button
            key={example.id}
            className="chip"
            disabled={isLoading}
            onClick={() => onQuestionChange(example.question)}
          >
            {example.question}
          </button>
        ))}
      </div>
    </section>
  );
}
