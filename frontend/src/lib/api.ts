import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 150_000,
  headers: { 'Content-Type': 'application/json' },
});

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { error?: { message?: unknown }; detail?: unknown } | undefined;
    if (typeof data?.error?.message === 'string') return data.error.message;
    if (typeof data?.detail === 'string') return data.detail;
    if (error.code === 'ECONNABORTED') return 'The request timed out. Please try a narrower question.';
  }
  return 'Unable to complete the request. Check the connection and try again.';
}
