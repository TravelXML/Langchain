import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { StatusBadge } from "../components/StatusBadge";
import type { ScoreBreakdown } from "../api/types";

const BREAKDOWN_LABELS: Record<keyof ScoreBreakdown, string> = {
  title: "Title match",
  skills: "Skills match",
  experience: "Experience",
  industry: "Industry",
  location: "Location",
  compensation: "Compensation",
};

export function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const job = useAsync(() => api.getJob(jobId!), [jobId]);

  if (job.loading) return <p className="muted">Loading…</p>;
  if (job.error) return <div className="error-banner">{job.error}</div>;
  if (!job.data) return null;

  const j = job.data;

  return (
    <div>
      <div className="page-header">
        <div>
          <Link to="/jobs">← Back to jobs</Link>
          <h1 style={{ marginTop: 6 }}>{j.title}</h1>
          <p className="muted" style={{ margin: "4px 0" }}>
            {j.company} · {j.location ?? "Location unknown"} · {j.work_mode ?? "—"}
          </p>
        </div>
        <StatusBadge status={j.status} />
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Match score: {j.overall_score !== null ? Math.round(j.overall_score) : "—"}
          </div>
          {j.breakdown &&
            (() => {
              const breakdown = j.breakdown;
              return (Object.keys(BREAKDOWN_LABELS) as (keyof ScoreBreakdown)[]).map((key) => (
                <div key={key} style={{ marginBottom: 10 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 13,
                      marginBottom: 4,
                    }}
                  >
                    <span>{BREAKDOWN_LABELS[key]}</span>
                    <span className="muted">{Math.round(breakdown[key])}</span>
                  </div>
                  <div className="score-bar-track">
                    <div
                      className="score-bar-fill"
                      style={{ width: `${Math.min(100, Math.max(0, breakdown[key]))}%` }}
                    />
                  </div>
                </div>
              ));
            })()}
          {!j.breakdown && <p className="muted">Not scored (duplicate or unscored job).</p>}

          {j.recommendation && (
            <p style={{ marginTop: 12 }}>
              <strong>Recommendation:</strong> {j.recommendation.replace(/_/g, " ")}
            </p>
          )}
          {j.reason && <p className="muted">{j.reason}</p>}
        </div>

        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Skills
          </div>
          <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Matched</p>
          <div className="chip-row" style={{ marginBottom: 14 }}>
            {j.matched_skills.length === 0 && <span className="muted">None</span>}
            {j.matched_skills.map((s) => (
              <span key={s} className="chip">
                {s}
              </span>
            ))}
          </div>
          <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Missing</p>
          <div className="chip-row">
            {j.missing_skills.length === 0 && <span className="muted">None</span>}
            {j.missing_skills.map((s) => (
              <span key={s} className="chip">
                {s}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="section-title">Description</div>
      <div className="card" style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.6 }}>
        {j.description}
      </div>

      <div className="section-title">Details</div>
      <div className="card">
        <table>
          <tbody>
            <tr>
              <td style={{ fontWeight: 600 }}>Source</td>
              <td>{j.source}</td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>URL</td>
              <td>
                <a href={j.url} target="_blank" rel="noreferrer">
                  {j.url}
                </a>
              </td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Salary</td>
              <td>
                {j.salary_min && j.salary_max
                  ? `${j.salary_min}–${j.salary_max} ${j.salary_currency ?? ""}`
                  : "—"}
              </td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Employment type</td>
              <td>{j.employment_type ?? "—"}</td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Industry</td>
              <td>{j.industry ?? "—"}</td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Discovered</td>
              <td>{new Date(j.discovered_at).toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
