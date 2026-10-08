import { useState } from "react";

export function SqlPreviewCard({ sql }: { sql: string }) {
  const [notice, setNotice] = useState("");
  async function copy() {
    try {
      await navigator.clipboard.writeText(sql);
      setNotice("SQL copied.");
    } catch {
      setNotice("Clipboard unavailable. Select and copy the SQL below.");
    }
  }
  return (
    <details className="panel">
      <summary className="cursor-pointer font-semibold">Inspect SQL</summary>
      <div className="my-3 flex items-center gap-3">
        <button className="secondary" onClick={() => void copy()}>
          Copy SQL
        </button>
        <span role="status" className="text-sm text-slate-500">
          {notice}
        </span>
      </div>
      <pre className="overflow-x-auto rounded-xl bg-slate-50 p-4 text-sm leading-6 text-violet-700">
        <code>{sql}</code>
      </pre>
    </details>
  );
}
