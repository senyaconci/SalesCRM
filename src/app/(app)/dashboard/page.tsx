import { requireRole } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { buildProjectWhere, readParams } from "@/lib/project-query";
import { ProjectFilters } from "@/components/projects/ProjectFilters";
import { ProjectTable } from "@/components/projects/ProjectTable";
import { StatCard } from "@/components/ui/StatCard";
import { LinkButton } from "@/components/ui/Button";

export const dynamic = "force-dynamic";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  await requireRole(["ADMIN", "MANAGER"]);
  const sp = await searchParams;
  const filters = readParams(sp);
  const where = buildProjectWhere(filters);

  const [projects, sdrs, vendors, counts] = await Promise.all([
    prisma.project.findMany({
      where,
      include: {
        vendorCustomer: { select: { name: true } },
        ownerOrganization: { select: { name: true } },
        assignedSdr: { select: { name: true } },
      },
      orderBy: [{ priority: "desc" }, { lastActivityAt: "desc" }],
      take: 200,
    }),
    prisma.user.findMany({
      where: { role: "SDR", isActive: true },
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.vendorCustomer.findMany({
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.project.groupBy({ by: ["status"], _count: true }),
  ]);

  const countByStatus = Object.fromEntries(
    counts.map((c) => [c.status, c._count])
  ) as Record<string, number>;
  const total = counts.reduce((sum, c) => sum + c._count, 0);
  const closedDead =
    (countByStatus.CLOSED_WON ?? 0) +
    (countByStatus.CLOSED_LOST ?? 0) +
    (countByStatus.DEAD ?? 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">
            All public capital project tickets across the team.
          </p>
        </div>
        <LinkButton href="/projects/new">+ New Project</LinkButton>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <StatCard label="Total" value={total} href="/projects" />
        <StatCard
          label="New"
          value={countByStatus.NEW ?? 0}
          tone="slate"
          href="/projects?status=NEW"
        />
        <StatCard
          label="Assigned"
          value={countByStatus.ASSIGNED ?? 0}
          tone="blue"
          href="/projects?status=ASSIGNED"
        />
        <StatCard
          label="Outreach"
          value={countByStatus.OUTREACH_STARTED ?? 0}
          tone="blue"
          href="/projects?status=OUTREACH_STARTED"
        />
        <StatCard
          label="Validated"
          value={countByStatus.VALIDATED_RELEVANT ?? 0}
          tone="green"
          href="/projects?status=VALIDATED_RELEVANT"
        />
        <StatCard
          label="Follow-up"
          value={countByStatus.FOLLOW_UP_LATER ?? 0}
          tone="amber"
          href="/projects?status=FOLLOW_UP_LATER"
        />
        <StatCard label="Closed / Dead" value={closedDead} tone="red" />
      </div>

      <ProjectFilters sdrs={sdrs} vendors={vendors} />
      <ProjectTable projects={projects} />
    </div>
  );
}
