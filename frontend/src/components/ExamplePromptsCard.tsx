import type { ExampleItem } from "../types/query";

type ExamplePromptsCardProps = {
    examples: ExampleItem[];
    isLoading: boolean;
    onSelectExample: (question: string) => void;
};

export function ExamplePromptsCard({
    examples,
    isLoading,
    onSelectExample,
}: ExamplePromptsCardProps) {
    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl">
            <div className="mb-4">
                <p className="text-sm font-medium text-slate-400">Starter prompts</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Examples</h2>
            </div>

            <div className="grid gap-3">
                {examples.map((example) => (
                    <button
                        key={example.id}
                        onClick={() => onSelectExample(example.question)}
                        disabled={isLoading}
                        className="rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-left text-sm text-slate-200 transition hover:border-blue-500 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {example.question}
                    </button>
                ))}
            </div>
        </div>
    );
}