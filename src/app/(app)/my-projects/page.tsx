import { requireUser } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { buildProjectWhere, readParams } from "@/lib/project-query";
import { followUpState } from "@/lib/format";
import { ProjectFilters } from "@/components/projects/ProjectFilters";
import { ProjectTable, type ProjectRow } from "@/components/projects/ProjectTable";

export const dynamic = "force-dynamic";

/**
 * SDR work queue ordering:
 *   1. Urgent priority
 *   2. Follow-up due today / overdue
 *   3. New assigned projects
 *   4. Oldest last activity
 */
function workQueueScore(p: ProjectRow): number[] {
  const urgent = p.priority === "URGENT" ? 0 : 1;
  const fu = followUpState(p.nextFollowUpAt);
  const followUpDue = fu === "overdue" || fu === "today" ? 0 : 1;
  const isNew = p.status === "ASSIGNED" || p.status === "NEW" ? 0 : 1;
  const lastActivity = p.lastActivityAt
    ? new Date(p.lastActivityAt).getTime()
    : 0;
  return [urgent, followUpDue, isNew, lastActivity];
}

function compareScores(a: number[], b: number[]): number {
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

export default async function MyProjectsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const user = await requireUser();
  const sp = await searchParams;
  const where = {
    AND: [{ assignedSdrId: user.id }, buildProjectWhere(readParams(sp))],
  };

  const [projects, vendors] = await Promise.all([
    prisma.project.findMany({
      where,
      include: {
        vendorCustomer: { select: { name: true } },
        ownerOrganization: { select: { name: true } },
        assignedSdr: { select: { name: true } },
      },
    }),
    prisma.vendorCustomer.findMany({
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
  ]);

  const sorted = [...projects].sort((a, b) =>
    compareScores(workQueueScore(a), workQueueScore(b))
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900">My Projects</h1>
        <p className="text-sm text-slate-500">
          Your assigned project tickets, ordered by what needs attention first.
        </p>
      </div>
      <ProjectFilters vendors={vendors} showSdr={false} />
      <ProjectTable projects={sorted} showSdr={false} />
    </div>
  );
}
