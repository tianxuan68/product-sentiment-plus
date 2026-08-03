export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function request<T>(path: string, method: HttpMethod = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  if (!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`);
  return response.json() as Promise<T>;
}
