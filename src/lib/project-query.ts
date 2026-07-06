import type { Prisma } from "@prisma/client";

export interface ProjectFilterParams {
  q?: string;
  status?: string;
  stage?: string;
  category?: string;
  priority?: string;
  state?: string;
  sdr?: string;
  vendor?: string;
}

/** Reads a single string value from a Next.js searchParams object. */
export function readParams(
  sp: Record<string, string | string[] | undefined>
): ProjectFilterParams {
  const one = (k: string) => {
    const v = sp[k];
    return Array.isArray(v) ? v[0] : v;
  };
  return {
    q: one("q"),
    status: one("status"),
    stage: one("stage"),
    category: one("category"),
    priority: one("priority"),
    state: one("state"),
    sdr: one("sdr"),
    vendor: one("vendor"),
  };
}

/** Builds a Prisma where clause from filter params (combine with visibility). */
export function buildProjectWhere(
  params: ProjectFilterParams
): Prisma.ProjectWhereInput {
  const and: Prisma.ProjectWhereInput[] = [];

  if (params.q) {
    const q = params.q;
    and.push({
      OR: [
        { title: { contains: q, mode: "insensitive" } },
        { locationState: { contains: q, mode: "insensitive" } },
        { locationCity: { contains: q, mode: "insensitive" } },
        { ownerOrganization: { name: { contains: q, mode: "insensitive" } } },
        { vendorCustomer: { name: { contains: q, mode: "insensitive" } } },
      ],
    });
  }
  if (params.status) and.push({ status: params.status as never });
  if (params.stage) and.push({ stage: params.stage as never });
  if (params.category) and.push({ category: params.category as never });
  if (params.priority) and.push({ priority: params.priority as never });
  if (params.state)
    and.push({ locationState: { equals: params.state, mode: "insensitive" } });
  if (params.sdr) and.push({ assignedSdrId: params.sdr });
  if (params.vendor) and.push({ vendorCustomerId: params.vendor });

  return and.length ? { AND: and } : {};
}
