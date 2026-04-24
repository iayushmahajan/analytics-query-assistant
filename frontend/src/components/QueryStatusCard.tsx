type QueryStatusCardProps = {
    status?: string;
    rowCount?: number;
    executionTimeMs?: number;
};

function getStatusClasses(status?: string) {
    switch (status) {
        case "validated":
            return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
        case "blocked":
            return "bg-red-500/15 text-red-300 border-red-500/30";
        case "execution_failed":
            return "bg-amber-500/15 text-amber-300 border-amber-500/30";
        case "needs_review":
            return "bg-yellow-500/15 text-yellow-300 border-yellow-500/30";
        default:
            return "bg-slate-500/15 text-slate-300 border-slate-500/30";
    }
}

export function QueryStatusCard({
    status,
    rowCount,
    executionTimeMs,
}: QueryStatusCardProps) {
    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl">
            <div className="mb-4">
                <p className="text-sm font-medium text-slate-400">Query status</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Execution summary</h2>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                    <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Status</p>
                    <span
                        className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold capitalize ${getStatusClasses(
                            status
                        )}`}
                    >
                        {status ?? "not run"}
                    </span>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                    <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Row count</p>
                    <p className="text-lg font-semibold text-white">{rowCount ?? 0}</p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                    <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Execution time</p>
                    <p className="text-lg font-semibold text-white">
                        {executionTimeMs ?? 0} ms
                    </p>
                </div>
            </div>
        </div>
    );
}