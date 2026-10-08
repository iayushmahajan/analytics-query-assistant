import type { HistoryItem } from "../types/query";

type Props = {
  history: HistoryItem[];
  isLoading: boolean;
  onRefresh: () => void;
  onSelectHistoryItem: (item: HistoryItem) => void;
};
export function HistoryCard({
  history,
  isLoading,
  onRefresh,
  onSelectHistoryItem,
}: Props) {
  return (
    <details className="panel">
      <summary className="cursor-pointer font-semibold text-slate-900">
        Recent analyses{" "}
        <span className="ml-2 text-sm font-normal text-slate-500">
          {history.length} saved · shared query history
        </span>
      </summary>
      <button
        className="secondary my-4"
        disabled={isLoading}
        onClick={onRefresh}
      >
        Refresh history
      </button>
      {history.length === 0 ? (
        <p className="text-sm text-slate-500">No saved analyses yet.</p>
      ) : (
        <ul className="grid gap-2 md:grid-cols-2">
          {history.map((item) => (
            <li key={item.id}>
              <button
                disabled={isLoading}
                onClick={() => onSelectHistoryItem(item)}
                className="w-full rounded-xl border border-slate-200 p-3 text-left hover:border-violet-400 disabled:opacity-50"
              >
                <span className="block text-sm text-slate-800">
                  {item.question}
                </span>
                <span className="mt-1 block text-xs text-slate-500">
                  Eurostat · {item.status.replaceAll("_", " ")} · {item.row_count ?? 0}{" "}
                  {item.row_count === 1 ? "row" : "rows"} ·{" "}
                  {new Date(item.created_at).toLocaleDateString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
