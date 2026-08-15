import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import type { SettingsOut } from "../api/types";

const SECTIONS: { key: keyof SettingsOut; label: string; description: string }[] = [
  {
    key: "automation",
    label: "Automation",
    description:
      "Dry-run flag, approval mode, concurrency, per-day application limits, and the " +
      "scheduler (enabled/timezone/schedules/daily_summary_hour) — cron or interval " +
      "entries that trigger discovery runs automatically.",
  },
  {
    key: "scoring",
    label: "Scoring",
    description: "Matching engine weights and the score thresholds that drive queue/reject/review.",
  },
  {
    key: "search",
    label: "Search",
    description: "Enabled portals for discovery and per-run/per-portal job limits.",
  },
  {
    key: "portals",
    label: "Portals",
    description: "Portal adapter registry (e.g. Greenhouse board tokens).",
  },
  {
    key: "notifications",
    label: "Notifications",
    description:
      "Which channels fire on run/application completion, failure, human review, and the " +
      "daily summary. Console is on by default; webhook/email/desktop are opt-in.",
  },
];

export function Settings() {
  const settings = useAsync(() => api.getSettings());
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!settings.data) return;
    const next: Record<string, string> = {};
    for (const section of SECTIONS) {
      next[section.key] = JSON.stringify(settings.data[section.key], null, 2);
    }
    setDrafts(next);
  }, [settings.data]);

  const save = async (key: keyof SettingsOut) => {
    setErrors((e) => ({ ...e, [key]: "" }));
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(drafts[key]);
    } catch {
      setErrors((e) => ({ ...e, [key]: "Invalid JSON" }));
      return;
    }
    setSaving(key);
    try {
      await api.updateSettings({ [key]: parsed } as Partial<SettingsOut>);
      setSavedAt((s) => ({ ...s, [key]: Date.now() }));
    } catch (err) {
      setErrors((e) => ({ ...e, [key]: err instanceof ApiError ? err.message : String(err) }));
    } finally {
      setSaving(null);
    }
  };

  if (settings.loading) return <p className="muted">Loading…</p>;
  if (settings.error) return <div className="error-banner">{settings.error}</div>;

  return (
    <div>
      <div className="page-header">
        <h1>Settings</h1>
      </div>
      <p className="muted" style={{ marginTop: -12, marginBottom: 20 }}>
        Edits here rewrite <code>config/*.yaml</code> directly and take effect on the next
        request — no restart needed. Comments in the YAML files are not preserved once a section
        is saved through this page.
      </p>

      {SECTIONS.map((section) => (
        <div key={section.key} className="card" style={{ marginBottom: 16 }}>
          <div className="section-title" style={{ marginTop: 0 }}>
            {section.label}
          </div>
          <p className="muted" style={{ fontSize: 13, marginTop: -4 }}>
            {section.description}
          </p>
          <textarea
            className="json-editor"
            value={drafts[section.key] ?? ""}
            onChange={(e) => setDrafts((d) => ({ ...d, [section.key]: e.target.value }))}
            spellCheck={false}
          />
          {errors[section.key] && <div className="error-banner">{errors[section.key]}</div>}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
            <button
              className="btn btn-primary"
              disabled={saving === section.key}
              onClick={() => save(section.key)}
            >
              {saving === section.key ? "Saving…" : `Save ${section.label}`}
            </button>
            {savedAt[section.key] && Date.now() - savedAt[section.key] < 4000 && (
              <span className="muted" style={{ fontSize: 12 }}>
                Saved
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
