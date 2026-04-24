type SqlPreviewCardProps = {
    sql?: string;
    copied: boolean;
    onCopy: () => void;
};

export function SqlPreviewCard({ sql, copied, onCopy }: SqlPreviewCardProps) {
    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                    <p className="text-sm font-medium text-slate-400">Generated SQL</p>
                    <h2 className="mt-1 text-lg font-semibold text-white">SQL preview</h2>
                </div>

                <button
                    onClick={onCopy}
                    disabled={!sql}
                    className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {copied ? "Copied" : "Copy SQL"}
                </button>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-4">
                <pre className="whitespace-pre-wrap break-words text-sm leading-7 text-emerald-300">
                    {sql || "SQL will appear here after running a query"}
                </pre>
            </div>
        </div>
    );
}