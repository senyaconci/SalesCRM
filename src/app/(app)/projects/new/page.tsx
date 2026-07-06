import { requireRole } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { NewProjectForm } from "@/components/projects/NewProjectForm";

export const dynamic = "force-dynamic";

export default async function NewProjectPage() {
  await requireRole(["ADMIN", "MANAGER"]);

  const [vendors, organizations, sdrs] = await Promise.all([
    prisma.vendorCustomer.findMany({
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.ownerOrganization.findMany({
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.user.findMany({
      where: { role: "SDR", isActive: true },
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
  ]);

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900">New Project Ticket</h1>
        <p className="text-sm text-slate-500">
          Create a public capital project ticket for SDR outreach.
        </p>
      </div>
      <NewProjectForm
        vendors={vendors}
        organizations={organizations}
        sdrs={sdrs}
      />
    </div>
  );
}
