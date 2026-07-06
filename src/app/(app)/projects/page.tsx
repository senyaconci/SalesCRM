import { requireRole } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { buildProjectWhere, readParams } from "@/lib/project-query";
import { ProjectFilters } from "@/components/projects/ProjectFilters";
import { ProjectTable } from "@/components/projects/ProjectTable";
import { LinkButton } from "@/components/ui/Button";

export const dynamic = "force-dynamic";

export default async function ProjectsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  await requireRole(["ADMIN", "MANAGER"]);
  const sp = await searchParams;
  const where = buildProjectWhere(readParams(sp));

  const [projects, sdrs, vendors] = await Promise.all([
    prisma.project.findMany({
      where,
      include: {
        vendorCustomer: { select: { name: true } },
        ownerOrganization: { select: { name: true } },
        assignedSdr: { select: { name: true } },
      },
      orderBy: [{ priority: "desc" }, { lastActivityAt: "desc" }, { createdAt: "desc" }],
      take: 300,
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
  ]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">All Projects</h1>
          <p className="text-sm text-slate-500">
            {projects.length} project{projects.length === 1 ? "" : "s"} shown
          </p>
        </div>
        <LinkButton href="/projects/new">+ New Project</LinkButton>
      </div>
      <ProjectFilters sdrs={sdrs} vendors={vendors} />
      <ProjectTable projects={projects} />
    </div>
  );
}
