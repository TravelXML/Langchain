import type {
  AnalyticsSummary,
  ApplicationListItem,
  ApplicationResult,
  HumanActionOut,
  JobOut,
  RunListItem,
  RunResult,
  SettingsOut,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    let detail = body;
    try {
      detail = JSON.parse(body).detail ?? body;
    } catch {
      // response body wasn't JSON — surface it as-is.
    }
    throw new ApiError(response.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export interface JobFilters {
  status?: string;
  company?: string;
  source?: string;
  run_id?: string;
  min_score?: number;
  limit?: number;
  offset?: number;
}

function toQueryString(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params as Record<string, unknown>)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  listJobs: (filters: JobFilters = {}) => request<JobOut[]>(`/api/jobs${toQueryString(filters)}`),
  getJob: (jobId: string) => request<JobOut>(`/api/jobs/${jobId}`),

  listApplications: (filters: { status?: string; limit?: number; offset?: number } = {}) =>
    request<ApplicationListItem[]>(`/api/applications${toQueryString(filters)}`),
  getApplication: (applicationId: string) =>
    request<ApplicationResult>(`/api/applications/${applicationId}`),
  resumeApplication: (applicationId: string, payload: Record<string, unknown>) =>
    request<ApplicationResult>(`/api/applications/${applicationId}/resume`, {
      method: "POST",
      body: JSON.stringify({ payload }),
    }),

  listRuns: (filters: { limit?: number; offset?: number } = {}) =>
    request<RunListItem[]>(`/api/runs${toQueryString(filters)}`),
  getRun: (runId: string) => request<RunResult>(`/api/runs/${runId}`),
  startRun: () => request<RunResult>("/api/runs", { method: "POST" }),
  resumeRun: (runId: string, decisions: Record<string, string>) =>
    request<RunResult>(`/api/runs/${runId}/resume`, {
      method: "POST",
      body: JSON.stringify({ decisions }),
    }),

  listHumanActions: () => request<HumanActionOut[]>("/api/human-actions"),
  resolveHumanAction: (
    interventionId: string,
    body: { decisions?: Record<string, string>; payload?: Record<string, unknown> },
  ) =>
    request<RunResult | ApplicationResult>(`/api/human-actions/${interventionId}/resolve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getAnalyticsSummary: () => request<AnalyticsSummary>("/api/analytics/summary"),

  getSettings: () => request<SettingsOut>("/api/settings"),
  updateSettings: (body: Partial<SettingsOut>) =>
    request<SettingsOut>("/api/settings", { method: "PUT", body: JSON.stringify(body) }),
};
