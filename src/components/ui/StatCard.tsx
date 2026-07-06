import Link from "next/link";

export function StatCard({
  label,
  value,
  href,
  tone = "slate",
}: {
  label: string;
  value: number | string;
  href?: string;
  tone?: "slate" | "blue" | "green" | "amber" | "red";
}) {
  const toneClass: Record<string, string> = {
    slate: "text-slate-900",
    blue: "text-blue-700",
    green: "text-green-700",
    amber: "text-amber-700",
    red: "text-red-700",
  };

  const inner = (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-slate-300">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-bold ${toneClass[tone]}`}>{value}</div>
    </div>
  );

  return href ? <Link href={href}>{inner}</Link> : inner;
}
