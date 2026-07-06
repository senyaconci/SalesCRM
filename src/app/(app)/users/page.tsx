import { requireRole } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { UserForm } from "@/components/users/UserForm";
import { UserActiveToggle } from "@/components/users/UserActiveToggle";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { enumLabel } from "@/lib/labels";

export const dynamic = "force-dynamic";

const roleTone: Record<string, "purple" | "blue" | "slate"> = {
  ADMIN: "purple",
  MANAGER: "blue",
  SDR: "slate",
};

export default async function UsersPage() {
  await requireRole(["ADMIN"]);
  const users = await prisma.user.findMany({
    orderBy: [{ role: "asc" }, { name: "asc" }],
    include: { _count: { select: { assignedProjects: true } } },
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Users</h1>
        <p className="text-sm text-slate-500">Manage team members and roles.</p>
      </div>

      <UserForm />

      <Card>
        <CardHeader title="Team" />
        <CardBody className="p-0">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Projects</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-2 font-medium text-slate-800">
                    {u.name}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{u.email}</td>
                  <td className="px-4 py-2">
                    <Badge tone={roleTone[u.role] ?? "slate"}>
                      {enumLabel(u.role)}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {u._count.assignedProjects}
                  </td>
                  <td className="px-4 py-2">
                    {u.isActive ? (
                      <span className="text-green-600">Active</span>
                    ) : (
                      <span className="text-slate-400">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <UserActiveToggle id={u.id} isActive={u.isActive} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}
