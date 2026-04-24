export type QueryResponse = {
    id: number;
    question: string;
    generated_sql: string;
    explanation: string;
    status: string;
    columns: string[];
    rows: unknown[][];
    row_count: number;
    execution_time_ms: number;
    created_at: string;
};

export type HistoryItem = {
    id: number;
    question: string;
    generated_sql: string;
    explanation: string;
    status: string;
    row_count: number | null;
    execution_time_ms: number | null;
    created_at: string;
};

export type ExampleItem = {
    id: number;
    question: string;
};