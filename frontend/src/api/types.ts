// Mirrors the Pydantic response models under app/api/routes/*.py.
// Kept as plain interfaces, not generated — the API surface is small and
// stable enough that a codegen step wouldn't earn its keep here.

export interface JobOut {
  id: string;
  run_id: string | null;
  source: string;
  url: string;
  title: string;
  company: string;
  location: string | null;
  work_mode: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  description: string;
  industry: string | null;
  employment_type: string | null;
  posted_at: string | null;
  discovered_at: string;
  status: string;
  overall_score: number | null;
  breakdown: ScoreBreakdown | null;
  matched_skills: string[];
  missing_skills: string[];
  recommendation: string | null;
  reason: string | null;
}

export interface ScoreBreakdown {
  title: number;
  skills: number;
  experience: number;
  industry: number;
  location: number;
  compensation: number;
}

export interface ApplicationListItem {
  id: string;
  job_id: string | null;
  job_title: string;
  company: string;
  status: string;
  interrupt_reason: string | null;
  submitted_at: string | null;
  created_at: string;
}

export interface ApplicationResult {
  application_id: string;
  status: "completed" | "waiting_human";
  application_status: string | null;
  interrupt: Record<string, unknown> | null;
  warnings: string[];
  errors: Record<string, unknown>[];
}

export interface JobSummary {
  job_id: string;
  title: string;
  company: string;
  score: number;
  recommendation: string;
  reason: string;
}

export interface RunResult {
  run_id: string;
  status: "completed" | "waiting_human";
  metrics: Record<string, number> | null;
  queued: JobSummary[];
  rejected: JobSummary[];
  duplicates: string[];
  warnings: string[];
  errors: Record<string, unknown>[];
  interrupt: Record<string, unknown> | null;
}

export interface RunListItem {
  id: string;
  status: string;
  enabled_portals: string[];
  metrics: Record<string, number> | null;
  warnings: string[];
  errors: Record<string, unknown>[];
  completed_at: string | null;
  created_at: string;
}

export interface HumanActionOut {
  id: string;
  kind: "run" | "application";
  ref_id: string;
  reason: string;
  payload: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface AnalyticsSummary {
  jobs_discovered_today: number;
  jobs_by_status: Record<string, number>;
  jobs_by_recommendation: Record<string, number>;
  jobs_by_score_bucket: Record<string, number>;
  applications_today: number;
  applications_this_week: number;
  applications_this_month: number;
  applications_by_status: Record<string, number>;
  applications_by_source: Record<string, number>;
  top_matched_skills: [string, number][];
  top_missing_skills: [string, number][];
  companies_applied_to: string[];
  human_review_pending: number;
}

// automation/scoring/search/portals/notifications sections are free-form
// YAML — typed loosely and edited as raw JSON in the Settings page rather
// than with a bespoke form per section.
export interface SettingsOut {
  automation: Record<string, unknown>;
  scoring: Record<string, unknown>;
  search: Record<string, unknown>;
  portals: Record<string, unknown>;
  notifications: Record<string, unknown>;
}
