type ResultsTableCardProps = {
    columns: string[];
    rows: unknown[][];
};

export function ResultsTableCard({ columns, rows }: ResultsTableCardProps) {
    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl">
            <div className="mb-4">
                <p className="text-sm font-medium text-slate-400">Results</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Data table</h2>
            </div>

            {columns.length === 0 ? (
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-sm text-slate-400">
                    No results to display yet.
                </div>
            ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="min-w-full divide-y divide-slate-800 bg-slate-950 text-sm">
                        <thead className="bg-slate-900">
                            <tr>
                                {columns.map((column) => (
                                    <th
                                        key={column}
                                        className="whitespace-nowrap px-4 py-3 text-left font-semibold text-slate-200"
                                    >
                                        {column}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            {rows.map((row, rowIndex) => (
                                <tr key={rowIndex} className="hover:bg-slate-900/60">
                                    {row.map((cell, cellIndex) => (
                                        <td
                                            key={`${rowIndex}-${cellIndex}`}
                                            className="whitespace-nowrap px-4 py-3 text-slate-300"
                                        >
                                            {cell === null ? "null" : String(cell)}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}