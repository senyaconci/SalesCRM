import Link from "next/link";
import {
  ProjectStatusBadge,
  StageBadge,
  PriorityBadge,
} from "@/components/ui/StatusBadges";
import { formatCurrency, formatDate, relativeTime, followUpState } from "@/lib/format";

export interface ProjectRow {
  id: string;
  title: string;
  priority: string;
  status: string;
  stage: string;
  locationState: string | null;
  budgetText: string | null;
  budgetAmount: { toString(): string } | null;
  nextFollowUpAt: Date | null;
  lastActivityAt: Date | null;
  vendorCustomer: { name: string } | null;
  ownerOrganization: { name: string } | null;
  assignedSdr: { name: string } | null;
}

const followUpClass: Record<string, string> = {
  overdue: "text-red-600 font-medium",
  today: "text-amber-600 font-medium",
  upcoming: "text-slate-600",
  none: "text-slate-400",
};

export function ProjectTable({
  projects,
  showSdr = true,
}: {
  projects: ProjectRow[];
  showSdr?: boolean;
}) {
  if (projects.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center text-sm text-slate-500">
        No projects match the current filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Project</th>
            <th className="px-4 py-3">Vendor</th>
            <th className="px-4 py-3">Owner Org</th>
            <th className="px-4 py-3">State</th>
            <th className="px-4 py-3">Budget</th>
            <th className="px-4 py-3">Stage</th>
            <th className="px-4 py-3">Status</th>
            {showSdr && <th className="px-4 py-3">SDR</th>}
            <th className="px-4 py-3">Last Activity</th>
            <th className="px-4 py-3">Follow-up</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {projects.map((p) => (
            <tr key={p.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link
                  href={`/projects/${p.id}`}
                  className="font-medium text-blue-700 hover:underline"
                >
                  {p.title}
                </Link>
                <div className="mt-1">
                  <PriorityBadge priority={p.priority} />
                </div>
              </td>
              <td className="px-4 py-3 text-slate-600">
                {p.vendorCustomer?.name ?? "—"}
              </td>
              <td className="px-4 py-3 text-slate-600">
                {p.ownerOrganization?.name ?? "—"}
              </td>
              <td className="px-4 py-3 text-slate-600">
                {p.locationState ?? "—"}
              </td>
              <td className="px-4 py-3 text-slate-600">
                {formatCurrency(p.budgetAmount, p.budgetText)}
              </td>
              <td className="px-4 py-3">
                <StageBadge stage={p.stage} />
              </td>
              <td className="px-4 py-3">
                <ProjectStatusBadge status={p.status} />
              </td>
              {showSdr && (
                <td className="px-4 py-3 text-slate-600">
                  {p.assignedSdr?.name ?? (
                    <span className="text-slate-400">Unassigned</span>
                  )}
                </td>
              )}
              <td className="px-4 py-3 text-slate-500">
                {relativeTime(p.lastActivityAt)}
              </td>
              <td
                className={`px-4 py-3 ${followUpClass[followUpState(p.nextFollowUpAt)]}`}
              >
                {p.nextFollowUpAt ? formatDate(p.nextFollowUpAt) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
