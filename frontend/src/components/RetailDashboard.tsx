import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { RetailOverview } from "../types/query";

const number = (value: number) => new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(value);
const monthDate = (value: string) => new Date(`${value}T00:00:00Z`).toLocaleDateString("en", {
  month: "short", year: "numeric", timeZone: "UTC",
});
const fullDate = (value: string | null) => value ? new Date(value).toLocaleDateString("en", {
  day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
}) : "Unavailable";
const signed = (value: number | null, suffix = " pts") => value == null
  ? "—"
  : `${value > 0 ? "+" : ""}${number(value)}${suffix}`;

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="dashboard-empty"><strong>{title}</strong><p>{detail}</p></div>;
}

export function RetailDashboard({ overview, failed }: {
  overview: RetailOverview | null;
  failed: boolean;
}) {
  if (failed) return <Empty title="Market dashboard unavailable" detail="The database could not load the Eurostat overview. Check the backend and retry." />;
  if (!overview) return <Empty title="Loading retail market data" detail="Preparing the latest Eurostat indicators…" />;
  if (!overview.available) return <Empty title="Eurostat data is ready to import" detail="Run the eurostat-data command to populate the market intelligence workspace." />;

  const visibleCountries = overview.countries.slice(0, 7);
  const completeness = overview.observation_count + overview.missing_cells
    ? overview.observation_count / (overview.observation_count + overview.missing_cells) * 100
    : null;
  const germany = overview.countries.find((country) => country.code === "DE");
  if (germany && !visibleCountries.some((country) => country.code === "DE")) visibleCountries.push(germany);

  return <section className="workspace-section dashboard-stack" id="overview">
    <div className="dashboard-title-row">
      <div><p className="eyebrow">MARKET OVERVIEW</p><h1>European retail intelligence</h1>
        <p className="dashboard-subtitle">Monthly retail sales-volume indices for Germany, the EU-27 and all EU member states</p></div>
      <span className="source-pill">Eurostat · 2021=100</span>
    </div>
    <div className="scope-banner"><strong>One source, one analytical model.</strong><span>All dashboard metrics, anomaly flags and natural-language results come from the same Eurostat dataset.</span></div>
    <div className="kpi-grid">
      <div className="kpi-card"><span>Germany retail index</span><strong>{overview.germany_value == null ? "—" : number(overview.germany_value)}</strong><small>{overview.latest_period ? monthDate(overview.latest_period) : "Latest month"}{overview.germany_provisional ? " · provisional" : ""}</small></div>
      <div className="kpi-card"><span>Monthly movement</span><strong className={(overview.germany_monthly_change ?? 0) < 0 ? "negative" : "positive"}>{signed(overview.germany_monthly_change)}</strong><small>Germany versus the previous month</small></div>
      <div className="kpi-card"><span>Annual movement</span><strong className={(overview.germany_yearly_change ?? 0) < 0 ? "negative" : "positive"}>{signed(overview.germany_yearly_change)}</strong><small>Germany versus the same month last year</small></div>
      <div className="kpi-card"><span>EU country rank</span><strong>{overview.germany_rank ? `${overview.germany_rank} of ${overview.ranked_country_count}` : "—"}</strong><small>Ranked by latest annual movement</small></div>
    </div>

    <div className="dashboard-grid-main">
      <section className="dashboard-card chart-card"><div className="card-head"><div><p className="eyebrow">PERFORMANCE</p><h2>Germany and EU-27</h2></div><span>Retail volume index</span></div>
        <div className="large-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={overview.history} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}><CartesianGrid stroke="#edf0f5" vertical={false}/><XAxis dataKey="period" tickFormatter={monthDate} tick={{ fill: "#788393", fontSize: 11 }} minTickGap={28}/><YAxis domain={["auto", "auto"]} tick={{ fill: "#788393", fontSize: 11 }} width={46}/><Tooltip labelFormatter={(value) => monthDate(String(value))}/><Legend/><Line name="Germany" type="monotone" dataKey="germany" stroke="#5b46e8" strokeWidth={2.7} dot={false} connectNulls isAnimationActive={false}/><Line name="EU-27" type="monotone" dataKey="eu" stroke="#4bb5ad" strokeWidth={2.3} dot={false} connectNulls isAnimationActive={false}/></LineChart></ResponsiveContainer></div>
        <p className="card-note">An index of 100 equals average retail volume in 2021. The measure is adjusted for seasonal and calendar effects and does not represent revenue in euros.</p>
      </section>
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">CATEGORY VIEW</p><h2>Germany by retail segment</h2></div><span>Latest available month</span></div>
        <div className="category-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={overview.categories} layout="vertical" margin={{ left: 6, right: 14 }}><CartesianGrid stroke="#edf0f5" horizontal={false}/><XAxis type="number" domain={["dataMin - 3", "dataMax + 3"]} tick={{ fill: "#788393", fontSize: 10 }}/><YAxis type="category" dataKey="name" width={128} tick={{ fill: "#657083", fontSize: 10 }}/><Tooltip formatter={(value) => [`${number(Number(value))} index`, "Retail index"]}/><Bar dataKey="value" fill="#7765ef" radius={[0, 5, 5, 0]} isAnimationActive={false}/></BarChart></ResponsiveContainer></div>
        <div className="category-movements">{overview.categories.map((category) => <div key={category.code}><span>{category.name}</span><strong className={(category.yearly_change ?? 0) < 0 ? "negative" : "positive"}>{signed(category.yearly_change)}</strong></div>)}</div>
      </section>
    </div>

    <div className="dashboard-grid-lower">
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">BENCHMARK</p><h2>EU country ranking</h2></div><span>Annual index-point movement</span></div>
        <div className="ranking-list">{visibleCountries.map((country) => <div className={`ranking-row ${country.code === "DE" ? "current" : ""}`} key={country.code}><span className="rank">{String(country.rank).padStart(2, "0")}</span><span className="country-name">{country.name}{country.provisional ? " *" : ""}</span><strong className={country.yearly_change < 0 ? "negative" : "positive"}>{signed(country.yearly_change)}</strong></div>)}</div>
        <p className="card-note">Countries are compared on the same total-retail category and reporting month. An asterisk marks a provisional value.</p>
      </section>
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">CHANGE DETECTION</p><h2>Unusual movements</h2></div><span>Most extreme recent scores</span></div>
        {overview.anomalies.length ? <div className="anomaly-list">{overview.anomalies.slice(0, 6).map((item, index) => <div className="anomaly-row" key={`${item.geography}-${item.category}-${item.period}-${index}`}><span className={`anomaly-direction ${item.direction}`}>{item.direction === "increase" ? "↑" : "↓"}</span><div><strong>{item.geography} · {item.category}</strong><small>{monthDate(item.period)} · {signed(item.monthly_change)} · score {number(Math.abs(item.score))}{item.provisional ? " · provisional" : ""}</small></div></div>)}</div> : <p className="quality-copy">No movements exceeded the robust anomaly threshold during the latest 24 months.</p>}
        <p className="card-note">A flag requires an absolute robust score of at least 3.5 against up to 36 preceding monthly changes. It identifies unusual movement, not its cause.</p>
      </section>
    </div>

    <section className="dashboard-card data-scope-card" id="quality"><div className="card-head"><div><p className="eyebrow">DATA QUALITY</p><h2>Coverage and provenance</h2></div><span>Updated {fullDate(overview.source_updated_at)}</span></div>
      <div className="scope-stats"><div><strong>{overview.observation_count.toLocaleString()}</strong><span>observations</span></div><div><strong>{overview.geography_count}</strong><span>geographies</span></div><div><strong>{overview.category_count}</strong><span>retail categories</span></div><div><strong>{overview.provisional_count.toLocaleString()}</strong><span>provisional observations</span></div><div><strong>{completeness == null ? "—" : `${number(completeness)}%`}</strong><span>requested-cell completeness</span></div><div><strong>{overview.ranked_country_count} / 27</strong><span>countries in latest ranking</span></div></div>
      <p className="quality-copy">Coverage runs from {fullDate(overview.earliest_period)} to {fullDate(overview.latest_period)}. Monthly and annual changes are index-point differences. Volatility and anomaly scores are derived locally from the imported observations.</p>
      {overview.source_sha256 && <p className="card-note">Source snapshot SHA-256 {overview.source_sha256.slice(0, 16)}… · {overview.missing_cells.toLocaleString()} unavailable source cells retained as missing</p>}
      <a className="source-link" href="https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table" target="_blank" rel="noreferrer">Open the Eurostat dataset and methodology ↗</a>
    </section>
  </section>;
}
