import { useState } from "react";
import {
  Area, AreaChart, CartesianGrid, Legend, Line,
  LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { ProductForecast, RetailOverview } from "../types/query";

const gbp = (value: number) => new Intl.NumberFormat("en-GB", {
  style: "currency", currency: "GBP", maximumFractionDigits: 0,
}).format(value);
const number = (value: number) => new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 }).format(value);
const shortDate = (value: string) => new Date(`${value}T00:00:00Z`).toLocaleDateString("en-GB", {
  month: "short", day: "numeric", timeZone: "UTC",
});

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="dashboard-empty"><strong>{title}</strong><p>{detail}</p></div>;
}

export function RetailDashboard({ overview, forecasts, failed }: {
  overview: RetailOverview | null;
  forecasts: ProductForecast[];
  failed: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const focus = forecasts.find((item) => item.stock_code === selected) ?? forecasts[0];
  if (failed) return <Empty title="Retail dashboard unavailable" detail="The database could not load the retail overview. Check the backend and retry." />;
  if (!overview) return <Empty title="Loading retail workspace" detail="Preparing sales and forecast summaries…" />;
  if (!overview.available) return <Empty title="Retail data is ready to import" detail="Run the documented retail-data import and training commands to fill this workspace." />;
  const maxCountry = Math.max(...overview.countries.map((item) => item.gross_sales), 1);
  return <div className="dashboard-stack" id="overview">
    <div className="dashboard-title-row">
      <div><p className="eyebrow">RETAIL INTELLIGENCE / OVERVIEW</p><h1>Sales at a glance</h1>
        <p className="dashboard-subtitle">Historical UK online retail transactions · {overview.start} to {overview.end}</p></div>
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
        <p className="quality-copy">The source records invoice lines in pounds sterling. A sale is a positive quantity and price on a non-cancelled invoice. These figures are gross transaction value, not profit or net revenue after returns.</p>
        {overview.source_sha256 && <p className="card-note">Audited import · SHA-256 {overview.source_sha256.slice(0, 12)}… · {number(overview.dropped_lines)} rejected rows</p>}
        <a className="source-link" href="https://archive.ics.uci.edu/dataset/352/online%2Bretail" target="_blank" rel="noreferrer">View dataset and license ↗</a>
      </section>
    </div>
    <section className="dashboard-card forecast-section" id="forecast"><div className="card-head"><div><p className="eyebrow">DEMAND / ONE WEEK AHEAD</p><h2>Forecast lab</h2></div><span>Historical backtest · 2011</span></div>
      {forecasts.length === 0 ? <Empty title="Forecasts have not been trained" detail="Run the retail training command after importing the dataset." /> : <>
        <p className="forecast-intro">Eight validation weeks select gradient boosting only when it beats the four-week average by at least 5%. Eight later, untouched weeks then measure the selected method. Weak evidence is labelled instead of hidden.</p>
        <div className="forecast-layout"><div className="forecast-products" role="group" aria-label="Forecast products">{forecasts.map((item) => <button type="button" aria-pressed={focus?.stock_code === item.stock_code} key={item.stock_code} onClick={() => setSelected(item.stock_code)}>
          <span><strong>{item.description}</strong><small>SKU {item.stock_code}</small></span><b>{number(item.predicted_units)} units</b>
        </button>)}</div>
          {focus && <div className="forecast-detail"><div className="forecast-detail-head"><div><h3>{focus.description}</h3><p>Week of {shortDate(focus.forecast_week)} · one-week historical forecast</p><span className={`confidence-badge ${focus.confidence ?? "insufficient"}`}>{focus.confidence ?? "legacy evaluation"} evidence</span></div><strong>{number(focus.predicted_units)} <small>units</small>{focus.prediction_lower != null && focus.prediction_upper != null && <em>{number(focus.prediction_lower)}–{number(focus.prediction_upper)} empirical range</em>}</strong></div>
            <div className="backtest-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={focus.backtest} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}><CartesianGrid stroke="#edf0f5" vertical={false}/><XAxis dataKey="week" tickFormatter={shortDate} tick={{ fill: "#788393", fontSize: 11 }}/><YAxis tick={{ fill: "#788393", fontSize: 11 }} width={45}/><Tooltip labelFormatter={(v) => shortDate(String(v))}/><Legend/><Line name="Actual units" type="monotone" dataKey="actual" stroke="#6554ec" strokeWidth={2.5} dot={false} isAnimationActive={false}/><Line name="Selected forecast" type="monotone" dataKey="predicted" stroke="#46b7b5" strokeWidth={2.5} dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>
            <div className="model-stats"><div><span>Selected method</span><strong>{focus.method === "gradient_boosting" ? "Gradient boosting" : "4-week average"}</strong></div><div><span>Test MAE</span><strong>{focus.test_mae == null ? "Not evaluated" : `${number(focus.test_mae)} units`}</strong></div><div><span>Test WAPE</span><strong>{focus.test_wape == null ? "Unavailable" : `${Math.round(focus.test_wape * 100)}%`}</strong></div><div><span>Mean bias</span><strong>{focus.test_bias == null ? "Unavailable" : `${focus.test_bias > 0 ? "+" : ""}${number(focus.test_bias)} units`}</strong></div><div><span>Baseline test MAE</span><strong>{focus.baseline_test_mae == null ? "Unavailable" : `${number(focus.baseline_test_mae)} units`}</strong></div><div><span>Range coverage</span><strong>{focus.interval_coverage == null ? "Unavailable" : `${Math.round(focus.interval_coverage * 100)}%`}</strong></div></div>
            <p className="card-note">The range uses validation errors and coverage is checked on the later test window. It is an empirical uncertainty band, not a guarantee. No inventory or stock-out data exists; this is demand, not a restock recommendation.</p>
          </div>}
        </div>
      </>}
    </section>
  </div>;
}
