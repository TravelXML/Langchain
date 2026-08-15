import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";

const COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2"];
const SCORE_BUCKET_ORDER = ["0-59", "60-74", "75-79", "80-89", "90-100"];

function toChartData(counts: Record<string, number>): { name: string; value: number }[] {
  return Object.entries(counts).map(([name, value]) => ({ name: name.replace(/_/g, " "), value }));
}

export function Analytics() {
  const analytics = useAsync(() => api.getAnalyticsSummary());

  if (analytics.loading) return <p className="muted">Loading…</p>;
  if (analytics.error) return <div className="error-banner">{analytics.error}</div>;
  if (!analytics.data) return null;

  const a = analytics.data;
  const scoreBuckets = SCORE_BUCKET_ORDER.map((bucket) => ({
    name: bucket,
    value: a.jobs_by_score_bucket[bucket] ?? 0,
  }));

  return (
    <div>
      <div className="page-header">
        <h1>Analytics</h1>
      </div>
      <p className="muted" style={{ marginTop: -12, marginBottom: 20 }}>
        Response rate, interview rate, and time-to-response aren't shown here — this system has
        no mechanism to observe real employer responses (no inbound email/webhook monitoring), so
        those numbers would be fabricated rather than measured.
      </p>

      <div className="grid-2">
        <ChartCard title="Jobs by status">
          <PieChart width={320} height={240}>
            <Pie
              data={toChartData(a.jobs_by_status)}
              dataKey="value"
              nameKey="name"
              outerRadius={80}
              label
            >
              {toChartData(a.jobs_by_status).map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Legend />
            <Tooltip />
          </PieChart>
        </ChartCard>

        <ChartCard title="Jobs by score bucket">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={scoreBuckets}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" fontSize={12} />
              <YAxis allowDecimals={false} fontSize={12} />
              <Tooltip />
              <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Applications by status">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={toChartData(a.applications_by_status)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} fontSize={12} />
              <YAxis type="category" dataKey="name" width={110} fontSize={12} />
              <Tooltip />
              <Bar dataKey="value" fill="#16a34a" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Applications by source">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={toChartData(a.applications_by_source)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" fontSize={12} />
              <YAxis allowDecimals={false} fontSize={12} />
              <Tooltip />
              <Bar dataKey="value" fill="#d97706" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Top matched skills
          </div>
          <SkillList entries={a.top_matched_skills} empty="No matched skills yet." />
        </div>
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Top missing skills
          </div>
          <SkillList entries={a.top_missing_skills} empty="No missing skills recorded." />
        </div>
      </div>

      <div className="section-title">Companies applied to</div>
      <div className="card">
        {a.companies_applied_to.length === 0 && <p className="empty-state">None yet.</p>}
        <div className="chip-row">
          {a.companies_applied_to.map((c) => (
            <span key={c} className="chip">
              {c}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <div className="section-title" style={{ marginTop: 0 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function SkillList({ entries, empty }: { entries: [string, number][]; empty: string }) {
  if (entries.length === 0) return <p className="empty-state">{empty}</p>;
  return (
    <div className="chip-row">
      {entries.map(([skill, count]) => (
        <span key={skill} className="chip">
          {skill} ({count})
        </span>
      ))}
    </div>
  );
}
