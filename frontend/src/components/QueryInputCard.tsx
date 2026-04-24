type QueryInputCardProps = {
    question: string;
    isLoading: boolean;
    onQuestionChange: (value: string) => void;
    onSubmit: () => void;
    onClear: () => void;
};

export function QueryInputCard({
    question,
    isLoading,
    onQuestionChange,
    onSubmit,
    onClear,
}: QueryInputCardProps) {
    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl">
            <div className="mb-4">
                <p className="text-sm font-medium text-slate-400">Ask a business question</p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                    Natural language to SQL
                </h2>
            </div>

            <div className="space-y-4">
                <textarea
                    value={question}
                    onChange={(e) => onQuestionChange(e.target.value)}
                    placeholder="Example: Show total revenue by country"
                    className="min-h-[120px] w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-blue-500"
                />

                <div className="flex flex-wrap gap-3">
                    <button
                        onClick={onSubmit}
                        disabled={isLoading || !question.trim()}
                        className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700"
                    >
                        {isLoading ? "Running..." : "Run query"}
                    </button>

                    <button
                        onClick={onClear}
                        className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-slate-800"
                    >
                        Clear results
                    </button>
                </div>
            </div>
        </div>
    );
}