const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  queued: "success",
  dry_run_ready: "success",
  submitted_mock: "success",
  completed: "success",
  resolved: "success",
  human_review: "warning",
  waiting_human: "warning",
  pending: "warning",
  rejected: "danger",
  rejected_by_human: "danger",
  duplicate: "neutral",
};

export function StatusBadge({ status }: { status: string }) {
  const variant = STATUS_VARIANT[status] ?? "neutral";
  return <span className={`badge badge-${variant}`}>{status.replace(/_/g, " ")}</span>;
}
