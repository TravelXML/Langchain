import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { StatusBadge } from "../components/StatusBadge";

export function Overview() {
  const analytics = useAsync(() => api.getAnalyticsSummary());
  const runs = useAsync(() => api.listRuns({ limit: 5 }));
  const humanActions = useAsync(() => api.listHumanActions());
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const startRun = useCallback(async () => {
    setStarting(true);
    setStartError(null);
    try {
      await api.startRun();
      runs.reload();
      humanActions.reload();
      analytics.reload();
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setStarting(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const a = analytics.data;

  return (
    <div>
      <div className="page-header">
        <h1>Overview</h1>
        <button className="btn btn-primary" onClick={startRun} disabled={starting}>
          {starting ? "Starting…" : "Start Discovery Run"}
        </button>
      </div>

      {startError && <div className="error-banner">{startError}</div>}
      {analytics.error && <div className="error-banner">{analytics.error}</div>}

      {a && (
        <div className="stat-grid">
          <StatTile label="Jobs discovered today" value={a.jobs_discovered_today} />
          <StatTile label="Queued for application" value={a.jobs_by_status["queued"] ?? 0} />
          <StatTile label="Rejected" value={a.jobs_by_status["rejected"] ?? 0} />
          <StatTile label="Applications today" value={a.applications_today} />
          <StatTile label="Applications this week" value={a.applications_this_week} />
          <StatTile label="Applications this month" value={a.applications_this_month} />
          <StatTile label="Human review pending" value={a.human_review_pending} />
        </div>
      )}

      <div className="grid-2">
        <div>
          <div className="section-title">Recent runs</div>
          <div className="card">
            {runs.loading && <p className="muted">Loading…</p>}
            {runs.data && runs.data.length === 0 && (
              <p className="empty-state">No discovery runs yet. Start one above.</p>
            )}
            {runs.data && runs.data.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Status</th>
                    <th>Queued</th>
                    <th>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.data.map((run) => (
                    <tr key={run.id}>
                      <td>
                        <Link to={`/jobs?run_id=${run.id}`}>{run.id.slice(0, 8)}</Link>
                      </td>
                      <td>
                        <StatusBadge status={run.status} />
                      </td>
                      <td>{run.metrics?.queued ?? "—"}</td>
                      <td>{new Date(run.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div>
          <div className="section-title">Human review queue</div>
          <div className="card">
            {humanActions.loading && <p className="muted">Loading…</p>}
            {humanActions.data && humanActions.data.length === 0 && (
              <p className="empty-state">Nothing waiting on you right now.</p>
            )}
            {humanActions.data && humanActions.data.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {humanActions.data.slice(0, 6).map((item) => (
                    <tr key={item.id}>
                      <td>{item.kind}</td>
                      <td>{item.reason.replace(/_/g, " ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {humanActions.data && humanActions.data.length > 0 && (
              <p style={{ marginTop: 10 }}>
                <Link to="/human-review">Go to Human Review →</Link>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-tile">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}
