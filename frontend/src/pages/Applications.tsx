import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { StatusBadge } from "../components/StatusBadge";

const STATUS_OPTIONS = ["waiting_human", "dry_run_ready", "submitted_mock", "rejected_by_human"];

export function Applications() {
  const [status, setStatus] = useState("");
  const filters = useMemo(() => ({ status: status || undefined, limit: 100 }), [status]);
  const applications = useAsync(() => api.listApplications(filters), [filters]);

  return (
    <div>
      <div className="page-header">
        <h1>Applications</h1>
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
      </div>

      {applications.error && <div className="error-banner">{applications.error}</div>}

      <div className="card">
        {applications.loading && <p className="muted">Loading…</p>}
        {applications.data && applications.data.length === 0 && (
          <p className="empty-state">No applications yet.</p>
        )}
        {applications.data && applications.data.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Company</th>
                <th>Status</th>
                <th>Submitted</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {applications.data.map((appItem) => (
                <tr key={appItem.id}>
                  <td>
                    {appItem.job_id ? (
                      <Link to={`/jobs/${appItem.job_id}`}>{appItem.job_title}</Link>
                    ) : (
                      appItem.job_title
                    )}
                  </td>
                  <td>{appItem.company}</td>
                  <td>
                    <StatusBadge status={appItem.status} />
                    {appItem.interrupt_reason && (
                      <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                        {appItem.interrupt_reason.replace(/_/g, " ")}
                      </div>
                    )}
                  </td>
                  <td>
                    {appItem.submitted_at
                      ? new Date(appItem.submitted_at).toLocaleString()
                      : "—"}
                  </td>
                  <td>{new Date(appItem.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
