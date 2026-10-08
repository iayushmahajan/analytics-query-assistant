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

export function RetailDashboard({ overview, forecast, failed }: {
  overview: RetailOverview | null;
  forecast: MarketForecast | null;
  failed: boolean;
}) {
  if (failed) return <Empty title="Retail dashboard unavailable" detail="The database could not load the retail overview. Check the backend and retry." />;
  if (!overview) return <Empty title="Loading retail workspace" detail="Preparing sales and forecast summaries…" />;
  if (!overview.available) return <Empty title="Retail data is ready to import" detail="Run the documented retail-data import and training commands to fill this workspace." />;
  const maxCountry = Math.max(...overview.countries.map((item) => item.gross_sales), 1);
  return <div className="dashboard-stack" id="overview">
    <div className="dashboard-title-row">
      <div><p className="eyebrow">RETAIL INTELLIGENCE / OVERVIEW</p><h1>Sales at a glance</h1>
        <p className="dashboard-subtitle">Historical international online retail transactions · {overview.start} to {overview.end}</p></div>
      <span className="source-pill">UCI real transactions · GBP</span>
    </div>
    <div className="kpi-grid">
      <div className="kpi-card"><span>Gross sales</span><strong>{gbp(overview.gross_sales)}</strong><small>Positive priced invoice lines</small></div>
      <div className="kpi-card"><span>Sales invoices</span><strong>{number(overview.sales_invoices)}</strong><small>Distinct non-cancelled invoices</small></div>
      <div className="kpi-card"><span>Units sold</span><strong>{number(overview.units)}</strong><small>Before returns or refunds</small></div>
      <div className="kpi-card"><span>Excluded lines</span><strong>{number(overview.excluded_lines)}</strong><small>Cancellations, zero-price or non-sale lines</small></div>
    </div>
    <div className="dashboard-grid-main">
      <section className="dashboard-card chart-card"><div className="card-head"><div><p className="eyebrow">PERFORMANCE</p><h2>Monthly gross sales</h2></div><span>GBP · historical</span></div>
        <div className="large-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={overview.months} margin={{ top: 15, right: 10, left: 5, bottom: 0 }}>
          <defs><linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6554ec" stopOpacity={0.28}/><stop offset="100%" stopColor="#6554ec" stopOpacity={0}/></linearGradient></defs>
          <CartesianGrid stroke="#edf0f5" vertical={false}/><XAxis dataKey="month" tick={{ fill: "#788393", fontSize: 11 }} minTickGap={18}/><YAxis tick={{ fill: "#788393", fontSize: 11 }} width={66} tickFormatter={(v: number) => `${Math.round(v/1000)}k`}/>
          <Tooltip formatter={(v) => gbp(Number(v))} contentStyle={{ borderRadius: 12, border: "1px solid #e5e8ef" }}/><Area type="monotone" dataKey="gross_sales" name="Gross sales" stroke="#6554ec" strokeWidth={3} fill="url(#salesFill)" isAnimationActive={false}/>
        </AreaChart></ResponsiveContainer></div>
        <p className="card-note">The December 2011 endpoint is partial. Gross sales exclude cancellation and non-sale lines; returns are not netted.</p>
      </section>
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">PRODUCT MIX</p><h2>Top products</h2></div><span>By gross sales</span></div>
        <div className="product-list">{overview.products.slice(0, 6).map((item, index) => <div className="product-row" key={`${item.name}-${index}`}>
          <span className="rank">{String(index + 1).padStart(2, "0")}</span><span className="product-name" title={item.name}>{item.name}</span><strong>{gbp(item.gross_sales)}</strong>
        </div>)}</div>
        <p className="card-note">Product names come from invoice descriptions, not a curated catalog.</p>
      </section>
    </div>
    <div className="dashboard-grid-lower">
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">GEOGRAPHY</p><h2>Sales by country</h2></div></div>
        <div className="country-list">{overview.countries.slice(0, 6).map((item) => <div className="country-row" key={item.name}><div><span>{item.name}</span><strong>{gbp(item.gross_sales)}</strong></div><div className="track"><span style={{ width: `${Math.max(2, item.gross_sales/maxCountry*100)}%` }}/></div></div>)}</div>
      </section>
      <section className="dashboard-card"><div className="card-head"><div><p className="eyebrow">DATA QUALITY</p><h2>What the numbers mean</h2></div></div>
        <div className="quality-grid"><div><strong>{number(overview.source_lines)}</strong><span>source lines</span></div><div><strong>{number(overview.sale_lines)}</strong><span>counted as sales</span></div></div>
        <p className="quality-copy">The source covers international orders from a UK-based retailer and records invoice lines in pounds sterling. A sale is a positive quantity and price on a non-cancelled invoice. These figures are gross transaction value, not profit or net revenue after returns.</p>
        {overview.source_sha256 && <p className="card-note">Audited import · SHA-256 {overview.source_sha256.slice(0, 12)}… · {number(overview.dropped_lines)} rejected rows</p>}
        <a className="source-link" href="https://archive.ics.uci.edu/dataset/352/online%2Bretail" target="_blank" rel="noreferrer">View dataset and license ↗</a>
      </section>
    </div>
    <section className="dashboard-card forecast-section" id="forecast"><div className="card-head"><div><p className="eyebrow">GERMANY / ONE MONTH AHEAD</p><h2>Retail volume outlook</h2></div><span>Eurostat · updated monthly</span></div>
      {!forecast ? <Empty title="Loading market forecast" detail="Reading the latest evaluated forecast…" /> : !forecast.available ? <Empty title="Market forecast is ready to build" detail="Run the documented market-data pipeline to import Eurostat and train the model." /> : <>
        <p className="forecast-intro">This forecasts Germany’s seasonally and calendar adjusted retail trade volume index (2021=100). Twenty-four validation months select the method; 24 later, untouched months measure it against the strongest transparent baseline.</p>
        <div className="forecast-detail market-forecast-detail"><div className="forecast-detail-head"><div><h3>Germany retail trade volume</h3><p>{forecast.target_period ? monthDate(forecast.target_period) : "Next month"} · index, 2021=100</p><span className={`confidence-badge ${forecast.confidence ?? "insufficient"}`}>{forecast.confidence ?? "unavailable"} evidence</span>{forecast.latest_observation_status?.includes("p") && <span className="provisional-badge">Latest Eurostat value is provisional</span>}</div><strong>{forecast.predicted_index?.toFixed(1)} <small>index</small>{forecast.prediction_lower != null && forecast.prediction_upper != null && <em>{forecast.prediction_lower.toFixed(1)}–{forecast.prediction_upper.toFixed(1)} empirical range</em>}</strong></div>
          <div className="backtest-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={forecast.backtest} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}><CartesianGrid stroke="#edf0f5" vertical={false}/><XAxis dataKey="period" tickFormatter={monthDate} tick={{ fill: "#788393", fontSize: 11 }} minTickGap={20}/><YAxis domain={["auto", "auto"]} tick={{ fill: "#788393", fontSize: 11 }} width={45}/><Tooltip labelFormatter={(v) => monthDate(String(v))}/><Legend/><Line name="Actual index" type="monotone" dataKey="actual" stroke="#6554ec" strokeWidth={2.5} dot={false} isAnimationActive={false}/><Line name="Out-of-sample forecast" type="monotone" dataKey="predicted" stroke="#46b7b5" strokeWidth={2.5} dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>
          <div className="model-stats"><div><span>Selected method</span><strong>{methodName(forecast.method)}</strong></div><div><span>ML validation MAE</span><strong>{forecast.ml_validation_mae == null ? "Unavailable" : `${forecast.ml_validation_mae.toFixed(2)} points`}</strong></div><div><span>Baseline validation MAE</span><strong>{forecast.baseline_validation_mae == null ? "Unavailable" : `${forecast.baseline_validation_mae.toFixed(2)} points`}</strong></div><div><span>Test MAE</span><strong>{forecast.test_mae == null ? "Unavailable" : `${forecast.test_mae.toFixed(2)} points`}</strong></div><div><span>Test WAPE</span><strong>{forecast.test_wape == null ? "Unavailable" : `${(forecast.test_wape * 100).toFixed(1)}%`}</strong></div><div><span>Mean bias</span><strong>{forecast.test_bias == null ? "Unavailable" : `${forecast.test_bias > 0 ? "+" : ""}${forecast.test_bias.toFixed(2)} points`}</strong></div><div><span>Baseline test MAE</span><strong>{forecast.baseline_test_mae == null ? "Unavailable" : `${forecast.baseline_test_mae.toFixed(2)} points`}</strong></div><div><span>Range coverage</span><strong>{forecast.interval_coverage == null ? "Unavailable" : `${Math.round(forecast.interval_coverage * 100)}%`}</strong></div></div>
          <p className="card-note">The range is calibrated on validation errors and checked on the later test window. Eurostat can revise provisional observations. This is a statistical outlook, not a guaranteed value or an individual retailer’s sales forecast.</p>
          <a className="source-link" href="https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table" target="_blank" rel="noreferrer">View Eurostat source and methodology ↗</a>
        </div>
      </>}
    </section>
  </div>;
}
