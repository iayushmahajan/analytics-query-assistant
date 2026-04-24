function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
          <div className="mb-6">
            <p className="text-sm uppercase tracking-widest text-slate-400">
              Analytics Query Assistant
            </p>
            <h1 className="mt-2 text-3xl font-bold">
              Phase 0 Setup Complete
            </h1>
            <p className="mt-3 text-slate-300">
              Frontend is running. Backend and PostgreSQL will connect through Docker.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
              <p className="text-sm text-slate-400">Frontend</p>
              <p className="mt-2 font-semibold text-emerald-400">React + Vite</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
              <p className="text-sm text-slate-400">Backend</p>
              <p className="mt-2 font-semibold text-blue-400">FastAPI</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
              <p className="text-sm text-slate-400">Database</p>
              <p className="mt-2 font-semibold text-purple-400">PostgreSQL</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;