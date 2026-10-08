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
          className="block text-lg font-semibold text-slate-900"
        >
          What would you like to understand?
        </label>
        <p id="question-hint" className="mt-1 text-sm text-slate-500">
          Ask about historical gross sales, units, invoices, products or countries. This dataset ends in 2011.
        </p>
        <textarea
          id="question"
          aria-describedby="question-hint"
          maxLength={2000}
          value={question}
          disabled={isLoading}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="How did monthly gross sales change during 2011?"
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
            <span role="status" className="text-sm text-slate-500">
              Interpreting, querying and calculating insights…
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
