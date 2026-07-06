import { requireRole } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { OwnerOrganizationForm } from "@/components/reference/OwnerOrganizationForm";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { enumLabel } from "@/lib/labels";

export const dynamic = "force-dynamic";

export default async function OwnerOrganizationsPage() {
  await requireRole(["ADMIN", "MANAGER"]);
  const orgs = await prisma.ownerOrganization.findMany({
    orderBy: { name: "asc" },
    include: { _count: { select: { projects: true } } },
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Owner Organizations</h1>
        <p className="text-sm text-slate-500">
          Public organizations where projects are happening.
        </p>
      </div>

      <OwnerOrganizationForm />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {orgs.map((o) => (
          <Card key={o.id}>
            <CardBody>
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-semibold text-slate-900">{o.name}</h3>
                <span className="text-xs text-slate-400">
                  {o._count.projects} projects
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <Badge tone="slate">{enumLabel(o.type)}</Badge>
                {(o.city || o.state) && (
                  <span className="text-xs text-slate-500">
                    {[o.city, o.state].filter(Boolean).join(", ")}
                  </span>
                )}
              </div>
              {o.website && (
                <a
                  href={o.website}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block text-xs text-blue-600 hover:underline"
                >
                  {o.website}
                </a>
              )}
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
