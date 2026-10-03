export type Cell = string | number | boolean | null;
export type ClarificationTurn = { question: string; answer: string };
export type Metric = {
  id: string; name: string; description: string; calculation: string;
  source_tables: string[]; date_field: string; included_statuses: string[];
  excluded_statuses: string[]; currency: string | null; aliases: string[];
};
export type QueryPlan = {
  status: 'ready' | 'needs_clarification' | 'blocked'; sql: string | null;
  interpretation: string; metric: string | null; dimensions: string[];
  filters: string[]; date_range: string; assumptions: string[];
  source_tables: string[]; explanation: string; clarification_question: string | null;
};
export type ResultAnalysis = {
  answer: string; findings: string[]; trends: string[]; anomalies: string[];
  caveats: string[]; follow_up_questions: string[];
};
export type QueryResponse = {
  id: number | null; request_id: string; question: string; clarification: ClarificationTurn[];
  status: 'success' | 'needs_clarification' | 'blocked' | 'failed';
  plan: QueryPlan | null; metric_definition: Metric | null; generated_sql: string;
  columns: string[]; rows: Cell[][]; row_count: number; possibly_truncated: boolean;
  analysis: ResultAnalysis | null; warnings: string[];
  timings: { generation_ms: number; execution_ms: number; analysis_ms: number; total_ms: number };
  error: { code: string; message: string } | null; created_at: string;
};
export type HistoryItem = { id: number; question: string; status: string; row_count: number | null; created_at: string };
export type ExampleItem = { id: number; question: string };
export type Health = { status: 'ok' | 'degraded'; provider: string };
export type Metadata = { name: string; synthetic: boolean; currency: string; date_start: string | null; date_end: string | null; order_count: number; max_rows: number; metrics: Metric[] };
