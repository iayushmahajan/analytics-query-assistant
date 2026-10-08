import {
  Area, AreaChart, CartesianGrid, Legend, Line,
  LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { MarketForecast, RetailOverview } from "../types/query";

const gbp = (value: number) => new Intl.NumberFormat("en-GB", {
  style: "currency", currency: "GBP", maximumFractionDigits: 0,
}).format(value);
const number = (value: number) => new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 }).format(value);
const monthDate = (value: string) => new Date(`${value}T00:00:00Z`).toLocaleDateString("en-GB", {
  month: "short", year: "numeric", timeZone: "UTC",
});
const fullDate = (value: string | null) => value ? new Date(value).toLocaleDateString("en-GB", {
  day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
}) : "Unavailable";
const pointChange = (current?: number | null, previous?: number | null) => {
  if (current == null || previous == null) return "Unavailable";
  const change = current - previous;
  return `${change > 0 ? "+" : ""}${change.toFixed(1)} points`;
};
const methodNames: Record<NonNullable<MarketForecast["method"]>, string> = {
  gradient_boosting: "Gradient boosting",
  last_value: "Previous month",
  three_month_average: "3-month average",
  year_ago: "Same month last year",
};
const methodName = (value: MarketForecast["method"]) => value ? methodNames[value] : "Unavailable";

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="dashboard-empty"><strong>{title}</strong><p>{detail}</p></div>;
}

function GermanyForecast({ forecast }: { forecast: MarketForecast | null }) {
  if (!forecast) return <Empty title="Loading Germany market data" detail="Reading the latest Eurostat observations and forecast…" />;
  if (!forecast.available) return <Empty title="Germany forecast is ready to build" detail="Run the market-data command to import Eurostat observations and train the forecast." />;

  const actualHistory = forecast.history.filter((point) => point.actual != null);
  const latest = actualHistory.at(-1)?.actual;
  const previous = actualHistory.at(-2)?.actual;
  const yearAgo = actualHistory.at(-13)?.actual;
  const performance = actualHistory.map((point, index) => ({
    period: point.period,
    actual: point.actual,
    forecast: index === actualHistory.length - 1 ? point.actual : null,
  }));
  if (forecast.target_period && forecast.predicted_index != null) {
    performance.push({ period: forecast.target_period, actual: null, forecast: forecast.predicted_index });
  }

  return <section className="workspace-section market-workspace" id="forecast">
    <div className="dashboard-title-row">
      <div><p className="eyebrow">MARKET FORECAST</p><h1>Germany retail outlook</h1>
        <p className="dashboard-subtitle">National retail trade volume · seasonally and calendar adjusted · index, 2021=100</p></div>
      <span className="source-pill">Eurostat · monthly</span>
    </div>
    <p className="dataset-separation">This is an independent German market series. It provides current economic context and is not derived from the historical UCI sales records above.</p>
    <div className="kpi-grid market-kpis">
      <div className="kpi-card"><span>Latest observed index</span><strong>{latest?.toFixed(1) ?? "—"}</strong><small>{forecast.training_cutoff ? monthDate(forecast.training_cutoff) : "Latest month"}{forecast.latest_observation_status?.includes("p") ? " · provisional" : ""}</small></div>
      <div className="kpi-card"><span>Monthly change</span><strong>{pointChange(latest, previous)}</strong><small>Latest month versus previous month</small></div>
      <div className="kpi-card"><span>Annual change</span><strong>{pointChange(latest, yearAgo)}</strong><small>Latest month versus the same month one year earlier</small></div>
      <div className="kpi-card forecast-kpi"><span>Next-month forecast</span><strong>{forecast.predicted_index?.toFixed(1) ?? "—"}</strong><small>{forecast.target_period ? monthDate(forecast.target_period) : "Next month"} · {forecast.prediction_lower?.toFixed(1)}–{forecast.prediction_upper?.toFixed(1)} range</small></div>
    </div>
    <div className="dashboard-grid-main">
      <section className="dashboard-card chart-card"><div className="card-head"><div><p className="eyebrow">PERFORMANCE</p><h2>Retail volume index</h2></div><span>Actual history and next month</span></div>
        <div className="large-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={performance} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}><CartesianGrid stroke="#edf0f5" vertical={false}/><XAxis dataKey="period" tickFormatter={monthDate} tick={{ fill: "#788393", fontSize: 11 }} minTickGap={24}/><YAxis domain={["auto", "auto"]} tick={{ fill: "#788393", fontSize: 11 }} width={46}/><Tooltip labelFormatter={(value) => monthDate(String(value))}/><Legend/><Line name="Observed index" type="monotone" dataKey="actual" stroke="#6554ec" strokeWidth={2.5} dot={false} isAnimationActive={false}/><Line name="Forecast" type="monotone" dataKey="forecast" stroke="#e17845" strokeWidth={2.5} strokeDasharray="5 4" dot={{ r: 3 }} connectNulls isAnimationActive={false}/></LineChart></ResponsiveContainer></div>
        <p className="card-note">An index of 100 equals the average retail volume in 2021. This chart measures sales volume across Germany, not revenue in euros.</p>
      </section>
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">FORECAST CHECK</p><h2>Out-of-sample performance</h2></div><span>{forecast.test_months} test months</span></div>
        <div className="backtest-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={forecast.backtest} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}><CartesianGrid stroke="#edf0f5" vertical={false}/><XAxis dataKey="period" tickFormatter={monthDate} tick={{ fill: "#788393", fontSize: 11 }} minTickGap={20}/><YAxis domain={["auto", "auto"]} tick={{ fill: "#788393", fontSize: 11 }} width={42}/><Tooltip labelFormatter={(value) => monthDate(String(value))}/><Legend/><Line name="Actual" type="monotone" dataKey="actual" stroke="#6554ec" strokeWidth={2.5} dot={false} isAnimationActive={false}/><Line name="Forecast" type="monotone" dataKey="predicted" stroke="#46b7b5" strokeWidth={2.5} dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>
        <p className="card-note">These months were held out from method selection. They show how the chosen method performed on later, unseen observations.</p>
      </section>
    </div>
    <div className="dashboard-grid-lower">
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">MODEL EVALUATION</p><h2>Forecast evidence</h2></div><span className={`confidence-badge ${forecast.confidence ?? "insufficient"}`}>{forecast.confidence ?? "unavailable"}</span></div>
        <div className="model-stats"><div><span>Selected method</span><strong>{methodName(forecast.method)}</strong></div><div><span>ML validation MAE</span><strong>{forecast.ml_validation_mae == null ? "—" : `${forecast.ml_validation_mae.toFixed(2)} points`}</strong></div><div><span>Baseline validation MAE</span><strong>{forecast.baseline_validation_mae == null ? "—" : `${forecast.baseline_validation_mae.toFixed(2)} points`}</strong></div><div><span>Test MAE</span><strong>{forecast.test_mae == null ? "—" : `${forecast.test_mae.toFixed(2)} points`}</strong></div><div><span>Test WAPE</span><strong>{forecast.test_wape == null ? "—" : `${(forecast.test_wape * 100).toFixed(1)}%`}</strong></div><div><span>Mean bias</span><strong>{forecast.test_bias == null ? "—" : `${forecast.test_bias > 0 ? "+" : ""}${forecast.test_bias.toFixed(2)} points`}</strong></div><div><span>Baseline test MAE</span><strong>{forecast.baseline_test_mae == null ? "—" : `${forecast.baseline_test_mae.toFixed(2)} points`}</strong></div><div><span>Range coverage</span><strong>{forecast.interval_coverage == null ? "—" : `${Math.round(forecast.interval_coverage * 100)}%`}</strong></div></div>
        <p className="card-note">Gradient boosting is selected only when it beats the strongest simple baseline by at least 5% on validation data.</p>
      </section>
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">DATA SCOPE</p><h2>What this forecast covers</h2></div></div>
        <div className="quality-grid"><div><strong>{number(forecast.observation_count)}</strong><span>monthly observations</span></div><div><strong>{fullDate(forecast.source_updated_at)}</strong><span>Eurostat update</span></div></div>
        <p className="quality-copy">Eurostat publishes one national monthly index for this selection. It has no products, customers, company revenue or regional breakdown, so those views cannot be calculated from this series.</p>
        <p className="card-note">The prediction range is calibrated on validation errors and checked on the test period. Provisional observations can be revised. The forecast is an estimate, not a guaranteed result.</p>
        <a className="source-link" href="https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table" target="_blank" rel="noreferrer">Open the Eurostat dataset ↗</a>
      </section>
    </div>
  </section>;
}

export function RetailDashboard({ overview, forecast, failed }: {
  overview: RetailOverview | null;
  forecast: MarketForecast | null;
  failed: boolean;
}) {
  if (failed) return <Empty title="Sales dashboard unavailable" detail="The database could not load the transaction overview. Check the backend and retry." />;
  if (!overview) return <Empty title="Loading sales data" detail="Preparing the transaction dashboard…" />;
  if (!overview.available) return <Empty title="Sales data is ready to import" detail="Run the retail-data command to import the UCI transaction dataset." />;
  const maxCountry = Math.max(...overview.countries.map((item) => item.gross_sales), 1);
  return <div className="dashboard-stack">
    <section className="workspace-section" id="sales">
      <div className="dashboard-title-row">
        <div><p className="eyebrow">SALES DASHBOARD</p><h1>Historical sales analysis</h1>
          <p className="dashboard-subtitle">International transactions from a UK-based online retailer · {overview.start} to {overview.end}</p></div>
        <span className="source-pill">UCI Online Retail · GBP</span>
      </div>
      <div className="kpi-grid">
        <div className="kpi-card"><span>Gross sales</span><strong>{gbp(overview.gross_sales)}</strong><small>Positive priced invoice lines</small></div>
        <div className="kpi-card"><span>Sales invoices</span><strong>{number(overview.sales_invoices)}</strong><small>Distinct non-cancelled invoices</small></div>
        <div className="kpi-card"><span>Units sold</span><strong>{number(overview.units)}</strong><small>Before returns or refunds</small></div>
        <div className="kpi-card"><span>Excluded lines</span><strong>{number(overview.excluded_lines)}</strong><small>Cancellations, zero-price or non-sale lines</small></div>
      </div>
      <div className="dashboard-grid-main">
        <section className="dashboard-card chart-card"><div className="card-head"><div><p className="eyebrow">PERFORMANCE</p><h2>Monthly gross sales</h2></div><span>GBP · historical</span></div>
          <div className="large-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={overview.months} margin={{ top: 15, right: 10, left: 5, bottom: 0 }}><defs><linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6554ec" stopOpacity={0.28}/><stop offset="100%" stopColor="#6554ec" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#edf0f5" vertical={false}/><XAxis dataKey="month" tick={{ fill: "#788393", fontSize: 11 }} minTickGap={18}/><YAxis tick={{ fill: "#788393", fontSize: 11 }} width={66} tickFormatter={(value: number) => `${Math.round(value/1000)}k`}/><Tooltip formatter={(value) => gbp(Number(value))} contentStyle={{ borderRadius: 12, border: "1px solid #e5e8ef" }}/><Area type="monotone" dataKey="gross_sales" name="Gross sales" stroke="#6554ec" strokeWidth={3} fill="url(#salesFill)" isAnimationActive={false}/></AreaChart></ResponsiveContainer></div>
          <p className="card-note">December 2011 is a partial month. Gross sales exclude cancellation and non-sale lines; returns are not netted.</p>
        </section>
        <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">PRODUCT MIX</p><h2>Top products</h2></div><span>By gross sales</span></div><div className="product-list">{overview.products.slice(0, 6).map((item, index) => <div className="product-row" key={`${item.name}-${index}`}><span className="rank">{String(index + 1).padStart(2, "0")}</span><span className="product-name" title={item.name}>{item.name}</span><strong>{gbp(item.gross_sales)}</strong></div>)}</div><p className="card-note">Product names come from invoice descriptions, not a curated catalog.</p></section>
      </div>
      <div className="dashboard-grid-lower">
        <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">GEOGRAPHY</p><h2>Sales by country</h2></div></div><div className="country-list">{overview.countries.slice(0, 6).map((item) => <div className="country-row" key={item.name}><div><span>{item.name}</span><strong>{gbp(item.gross_sales)}</strong></div><div className="track"><span style={{ width: `${Math.max(2, item.gross_sales/maxCountry*100)}%` }}/></div></div>)}</div></section>
        <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">DATA QUALITY</p><h2>Transaction rules</h2></div></div><div className="quality-grid"><div><strong>{number(overview.source_lines)}</strong><span>source lines</span></div><div><strong>{number(overview.sale_lines)}</strong><span>counted as sales</span></div></div><p className="quality-copy">A sale has a positive quantity and price on a non-cancelled invoice. Values are gross transaction amounts in pounds sterling, not profit or net revenue after returns.</p>{overview.source_sha256 && <p className="card-note">Verified import · SHA-256 {overview.source_sha256.slice(0, 12)}… · {number(overview.dropped_lines)} rejected rows</p>}<a className="source-link" href="https://archive.ics.uci.edu/dataset/352/online%2Bretail" target="_blank" rel="noreferrer">Open the UCI dataset ↗</a></section>
      </div>
    </section>
    <GermanyForecast forecast={forecast}/>
  </div>;
}
