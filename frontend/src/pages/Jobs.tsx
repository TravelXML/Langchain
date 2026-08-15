import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { StatusBadge } from "../components/StatusBadge";

const STATUS_OPTIONS = ["queued", "rejected", "human_review", "duplicate"];

export function Jobs() {
  const [searchParams] = useSearchParams();
  const runId = searchParams.get("run_id") ?? undefined;

  const [status, setStatus] = useState("");
  const [company, setCompany] = useState("");
  const [minScore, setMinScore] = useState("");

  const filters = useMemo(
    () => ({
      status: status || undefined,
      company: company || undefined,
      run_id: runId,
      min_score: minScore ? Number(minScore) : undefined,
      limit: 100,
    }),
    [status, company, minScore, runId],
  );

  const jobs = useAsync(() => api.listJobs(filters), [filters]);

  return (
    <div>
      <div className="page-header">
        <h1>Jobs{runId ? ` — run ${runId.slice(0, 8)}` : ""}</h1>
      </div>

      <div className="filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          placeholder="Filter by company"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
        />
        <input
          placeholder="Min score"
          type="number"
          min={0}
          max={100}
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
        />
      </div>

      {jobs.error && <div className="error-banner">{jobs.error}</div>}

      <div className="card">
        {jobs.loading && <p className="muted">Loading…</p>}
        {jobs.data && jobs.data.length === 0 && (
          <p className="empty-state">No jobs match these filters.</p>
        )}
        {jobs.data && jobs.data.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Company</th>
                <th>Location</th>
                <th>Score</th>
                <th>Status</th>
                <th>Discovered</th>
              </tr>
            </thead>
            <tbody>
              {jobs.data.map((job) => (
                <tr key={job.id}>
                  <td>
                    <Link to={`/jobs/${job.id}`}>{job.title}</Link>
                  </td>
                  <td>{job.company}</td>
                  <td>{job.location ?? "—"}</td>
                  <td>{job.overall_score !== null ? Math.round(job.overall_score) : "—"}</td>
                  <td>
                    <StatusBadge status={job.status} />
                  </td>
                  <td>{new Date(job.discovered_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
