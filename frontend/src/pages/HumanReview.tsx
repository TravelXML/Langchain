import { useState } from "react";
import { api, ApiError } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import type { HumanActionOut } from "../api/types";

export function HumanReview() {
  const actions = useAsync(() => api.listHumanActions());

  return (
    <div>
      <div className="page-header">
        <h1>Human Review</h1>
      </div>

      {actions.error && <div className="error-banner">{actions.error}</div>}

      {actions.loading && <p className="muted">Loading…</p>}
      {actions.data && actions.data.length === 0 && (
        <div className="card">
          <p className="empty-state">Nothing waiting on you right now.</p>
        </div>
      )}

      {actions.data?.map((action) => (
        <div key={action.id} className="card" style={{ marginBottom: 16 }}>
          <ActionResolver action={action} onResolved={actions.reload} />
        </div>
      ))}
    </div>
  );
}

function ActionResolver({
  action,
  onResolved,
}: {
  action: HumanActionOut;
  onResolved: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (body: { decisions?: Record<string, string>; payload?: Record<string, unknown> }) => {
    setSubmitting(true);
    setError(null);
    try {
      await api.resolveHumanAction(action.id, body);
      onResolved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const header = (
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
      <div>
        <span className="badge badge-neutral">{action.kind}</span>{" "}
        <strong>{action.reason.replace(/_/g, " ")}</strong>
        <div className="muted" style={{ fontSize: 12 }}>
          ref: {action.ref_id.slice(0, 8)} · {new Date(action.created_at).toLocaleString()}
        </div>
      </div>
    </div>
  );

  return (
    <div>
      {header}
      {error && <div className="error-banner">{error}</div>}

      {action.kind === "run" && action.reason === "HUMAN_REVIEW_REQUIRED" && (
        <RunReviewForm action={action} submitting={submitting} onSubmit={submit} />
      )}
      {action.kind === "application" && action.reason === "UNKNOWN_REQUIRED_FIELD" && (
        <UnknownFieldForm action={action} submitting={submitting} onSubmit={submit} />
      )}
      {action.kind === "application" && action.reason === "MANUAL_APPROVAL_REQUIRED" && (
        <ApprovalForm action={action} submitting={submitting} onSubmit={submit} />
      )}
      {action.kind === "application" && action.reason === "OTP_REQUIRED" && (
        <OtpForm submitting={submitting} onSubmit={submit} />
      )}
      {action.kind === "application" && action.reason === "CAPTCHA_REQUIRED" && (
        <CaptchaForm submitting={submitting} onSubmit={submit} />
      )}
      {![
        "HUMAN_REVIEW_REQUIRED",
        "UNKNOWN_REQUIRED_FIELD",
        "MANUAL_APPROVAL_REQUIRED",
        "OTP_REQUIRED",
        "CAPTCHA_REQUIRED",
      ].includes(action.reason) && (
        <pre style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>
          {JSON.stringify(action.payload, null, 2)}
        </pre>
      )}
    </div>
  );
}

interface ReviewJob {
  job_id: string;
  title: string;
  company: string;
  score: number;
  note: string;
}

function RunReviewForm({
  action,
  submitting,
  onSubmit,
}: {
  action: HumanActionOut;
  submitting: boolean;
  onSubmit: (body: { decisions: Record<string, string> }) => void;
}) {
  const jobs = (action.payload.jobs as ReviewJob[]) ?? [];
  const [decisions, setDecisions] = useState<Record<string, string>>({});

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>Job</th>
            <th>Company</th>
            <th>Score</th>
            <th>Note</th>
            <th>Decision</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.job_id}>
              <td>{job.title}</td>
              <td>{job.company}</td>
              <td>{Math.round(job.score)}</td>
              <td className="muted" style={{ fontSize: 12 }}>
                {job.note}
              </td>
              <td>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    className={`btn ${decisions[job.job_id] === "queue" ? "btn-primary" : ""}`}
                    onClick={() => setDecisions((d) => ({ ...d, [job.job_id]: "queue" }))}
                  >
                    Queue
                  </button>
                  <button
                    className={`btn ${decisions[job.job_id] === "reject" ? "btn-primary" : ""}`}
                    onClick={() => setDecisions((d) => ({ ...d, [job.job_id]: "reject" }))}
                  >
                    Reject
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        className="btn btn-primary"
        style={{ marginTop: 12 }}
        disabled={submitting || Object.keys(decisions).length !== jobs.length}
        onClick={() => onSubmit({ decisions })}
      >
        {submitting ? "Submitting…" : "Submit decisions"}
      </button>
    </div>
  );
}

function UnknownFieldForm({
  action,
  submitting,
  onSubmit,
}: {
  action: HumanActionOut;
  submitting: boolean;
  onSubmit: (body: { payload: Record<string, unknown> }) => void;
}) {
  const fields = (action.payload.fields as { field: string; reason: string }[]) ?? [];
  const [values, setValues] = useState<Record<string, string>>({});

  return (
    <div>
      {fields.map((f) => (
        <div key={f.field} style={{ marginBottom: 10 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            {f.field}
          </label>
          <input
            style={{ width: "100%", maxWidth: 360 }}
            value={values[f.field] ?? ""}
            onChange={(e) => setValues((v) => ({ ...v, [f.field]: e.target.value }))}
            placeholder={f.reason}
          />
        </div>
      ))}
      <button
        className="btn btn-primary"
        disabled={submitting || fields.some((f) => !values[f.field])}
        onClick={() => onSubmit({ payload: values })}
      >
        {submitting ? "Submitting…" : "Submit values"}
      </button>
    </div>
  );
}

function ApprovalForm({
  action,
  submitting,
  onSubmit,
}: {
  action: HumanActionOut;
  submitting: boolean;
  onSubmit: (body: { payload: Record<string, unknown> }) => void;
}) {
  const mappings =
    (action.payload.field_mappings as {
      field: string;
      candidate_value: string | null;
      requires_human: boolean;
    }[]) ?? [];

  return (
    <div>
      <p>
        <strong>{String(action.payload.title ?? "")}</strong> at{" "}
        {String(action.payload.company ?? "")}
      </p>
      {mappings.length > 0 && (
        <table style={{ marginBottom: 12 }}>
          <thead>
            <tr>
              <th>Field</th>
              <th>Value to submit</th>
            </tr>
          </thead>
          <tbody>
            {mappings.map((m) => (
              <tr key={m.field}>
                <td>{m.field}</td>
                <td>{m.candidate_value ?? <span className="muted">(empty)</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="btn btn-primary"
          disabled={submitting}
          onClick={() => onSubmit({ payload: { approved: "true" } })}
        >
          Approve & submit
        </button>
        <button
          className="btn"
          disabled={submitting}
          onClick={() => onSubmit({ payload: { approved: "false" } })}
        >
          Reject
        </button>
      </div>
    </div>
  );
}

function OtpForm({
  submitting,
  onSubmit,
}: {
  submitting: boolean;
  onSubmit: (body: { payload: Record<string, unknown> }) => void;
}) {
  const [code, setCode] = useState("");
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <input placeholder="OTP code" value={code} onChange={(e) => setCode(e.target.value)} />
      <button
        className="btn btn-primary"
        disabled={submitting || !code}
        onClick={() => onSubmit({ payload: { otp_code: code } })}
      >
        {submitting ? "Submitting…" : "Submit OTP"}
      </button>
    </div>
  );
}

function CaptchaForm({
  submitting,
  onSubmit,
}: {
  submitting: boolean;
  onSubmit: (body: { payload: Record<string, unknown> }) => void;
}) {
  return (
    <div>
      <p className="muted">Solve the CAPTCHA in the browser session, then confirm here.</p>
      <button
        className="btn btn-primary"
        disabled={submitting}
        onClick={() => onSubmit({ payload: { solved: "true" } })}
      >
        {submitting ? "Submitting…" : "I solved it"}
      </button>
    </div>
  );
}
