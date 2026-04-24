import type { HistoryItem } from "../types/query";

type HistoryCardProps = {
    history: HistoryItem[];
    onSelectHistoryItem: (item: HistoryItem) => void;
};

function getStatusClasses(status: string) {
    switch (status) {
        case "validated":
            return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
        case "blocked":
            return "bg-red-500/15 text-red-300 border-red-500/30";
        case "execution_failed":
            return "bg-amber-500/15 text-amber-300 border-amber-500/30";
        default:
            return "bg-slate-500/15 text-slate-300 border-slate-500/30";
    }
}

export function HistoryCard({
    history,
    onSelectHistoryItem,
}: HistoryCardProps) {
    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl">
            <div className="mb-4">
                <p className="text-sm font-medium text-slate-400">Recent activity</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Query history</h2>
            </div>

            <div className="space-y-3">
                {history.length === 0 ? (
                    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 text-sm text-slate-400">
                        No query history yet.
                    </div>
                ) : (
                    history.map((item) => (
                        <button
                            key={item.id}
                            onClick={() => onSelectHistoryItem(item)}
                            className="w-full rounded-xl border border-slate-800 bg-slate-950 p-4 text-left transition hover:border-blue-500 hover:bg-slate-900"
                        >
                            <div className="mb-2 flex items-center justify-between gap-3">
                                <span
                                    className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize ${getStatusClasses(
                                        item.status
                                    )}`}
                                >
                                    {item.status}
                                </span>
                                <span className="text-xs text-slate-500">
                                    {item.execution_time_ms ?? 0} ms
                                </span>
                            </div>

                            <p className="text-sm font-medium text-slate-100">
                                {item.question}
                            </p>

                            <p className="mt-2 text-xs text-slate-500">
                                Rows: {item.row_count ?? 0}
                            </p>
                        </button>
                    ))
                )}
            </div>
        </div>
    );
}