type ExplanationCardProps = {
    explanation?: string;
};

export function ExplanationCard({ explanation }: ExplanationCardProps) {
    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl">
            <div className="mb-4">
                <p className="text-sm font-medium text-slate-400">Explanation</p>
                <h2 className="mt-1 text-lg font-semibold text-white">What the query does</h2>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <p className="text-sm leading-7 text-slate-200">
                    {explanation || "No explanation available yet."}
                </p>
            </div>
        </div>
    );
}