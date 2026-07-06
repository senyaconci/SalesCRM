import { requireRole } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { VendorCustomerForm } from "@/components/reference/VendorCustomerForm";
import { Card, CardBody } from "@/components/ui/Card";

export const dynamic = "force-dynamic";

export default async function VendorCustomersPage() {
  await requireRole(["ADMIN", "MANAGER"]);
  const vendors = await prisma.vendorCustomer.findMany({
    orderBy: { name: "asc" },
    include: { _count: { select: { projects: true } } },
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Vendor Customers</h1>
        <p className="text-sm text-slate-500">
          OEM / vendor customers using CapEx Signal.
        </p>
      </div>

      <VendorCustomerForm />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {vendors.map((v) => (
          <Card key={v.id}>
            <CardBody>
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">{v.name}</h3>
                <span className="text-xs text-slate-400">
                  {v._count.projects} projects
                </span>
              </div>
              {v.website && (
                <a
                  href={v.website}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-blue-600 hover:underline"
                >
                  {v.website}
                </a>
              )}
              {v.targetProjectTypes && (
                <p className="mt-2 text-xs text-slate-500">
                  Focus: {v.targetProjectTypes}
                </p>
              )}
              {v.targetGeography && (
                <p className="text-xs text-slate-500">
                  Geo: {v.targetGeography}
                </p>
              )}
              {v.description && (
                <p className="mt-2 text-sm text-slate-600">{v.description}</p>
              )}
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
