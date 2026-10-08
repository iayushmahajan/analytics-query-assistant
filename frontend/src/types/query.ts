export type Cell = string | number | boolean | null;
export type ClarificationTurn = { question: string; answer: string };
export type Metric = {
  id: string;
  name: string;
  description: string;
  calculation: string;
  source_tables: string[];
  date_field: string;
  included_statuses: string[];
  excluded_statuses: string[];
  currency: string | null;
  aliases: string[];
};
export type QueryPlan = {
  status: "ready" | "needs_clarification" | "blocked";
  sql: string | null;
  interpretation: string;
  metric: string | null;
  dimensions: string[];
  filters: string[];
  date_range: string;
  assumptions: string[];
  source_tables: string[];
  explanation: string;
  clarification_question: string | null;
};
export type ResultAnalysis = {
  answer: string;
  findings: string[];
  trends: string[];
  anomalies: string[];
  caveats: string[];
  follow_up_questions: string[];
};
export type QueryResponse = {
  id: number | null;
  request_id: string;
  question: string;
  dataset: "eurostat";
  clarification: ClarificationTurn[];
  status: "success" | "needs_clarification" | "blocked" | "failed";
  plan: QueryPlan | null;
  metric_definition: Metric | null;
  generated_sql: string;
  columns: string[];
  rows: Cell[][];
  row_count: number;
  possibly_truncated: boolean;
  analysis: ResultAnalysis | null;
  warnings: string[];
  timings: {
    generation_ms: number;
    execution_ms: number;
    analysis_ms: number;
    total_ms: number;
  };
  error: { code: string; message: string } | null;
  created_at: string;
};
export type HistoryItem = {
  id: number;
  question: string;
  dataset: "eurostat";
  status: string;
  row_count: number | null;
  created_at: string;
};
export type ExampleItem = { id: number; question: string };
export type Health = { status: "ok" | "degraded"; provider: string };
export type RetailOverview = {
  available: boolean;
  source: string;
  unit: string;
  source_updated_at: string | null;
  source_sha256: string | null;
  earliest_period: string | null;
  latest_period: string | null;
  observation_count: number;
  missing_cells: number;
  geography_count: number;
  category_count: number;
  provisional_count: number;
  germany_value: number | null;
  germany_monthly_change: number | null;
  germany_yearly_change: number | null;
  germany_volatility: number | null;
  germany_provisional: boolean;
  eu_value: number | null;
  eu_yearly_change: number | null;
  germany_rank: number | null;
  ranked_country_count: number;
  history: { period: string; germany: number | null; eu: number | null }[];
  categories: {
    code: string; name: string; period: string; value: number;
    monthly_change: number | null; yearly_change: number | null;
    volatility: number | null; provisional: boolean;
  }[];
  countries: {
    rank: number; code: string; name: string; period: string;
    value: number; yearly_change: number; provisional: boolean;
  }[];
  anomalies: {
    geography: string; category: string; period: string; value: number;
    monthly_change: number; score: number; direction: "increase" | "decrease";
    provisional: boolean;
  }[];
};
