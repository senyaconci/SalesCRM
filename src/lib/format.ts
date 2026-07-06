export function formatCurrency(
  amount: { toString(): string } | number | null | undefined,
  fallback?: string | null
): string {
  if (amount === null || amount === undefined) return fallback || "—";
  const n = typeof amount === "number" ? amount : Number(amount.toString());
  if (Number.isNaN(n)) return fallback || "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

export function formatDate(date: Date | string | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(date: Date | string | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function relativeTime(date: Date | string | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  const diff = Date.now() - d.getTime();
  const mins = Math.round(diff / 60000);
  if (Math.abs(mins) < 60) return mins <= 0 ? "just now" : `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (Math.abs(hours) < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (Math.abs(days) < 30) return `${days}d ago`;
  return formatDate(d);
}

export type FollowUpState = "none" | "overdue" | "today" | "upcoming";

export function followUpState(
  date: Date | string | null | undefined
): FollowUpState {
  if (!date) return "none";
  const d = typeof date === "string" ? new Date(date) : date;
  const now = new Date();
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  );
  const endOfToday = new Date(startOfToday);
  endOfToday.setDate(endOfToday.getDate() + 1);

  if (d < startOfToday) return "overdue";
  if (d < endOfToday) return "today";
  return "upcoming";
}

export function formatSeconds(seconds: number | null | undefined): string {
  if (!seconds) return "0m";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
