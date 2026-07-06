"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { canCreateProjects } from "@/lib/permissions";
import type { OwnerOrgType } from "@prisma/client";

function s(fd: FormData, key: string): string | null {
  const v = fd.get(key);
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t.length ? t : null;
}

// --- Vendor customers -------------------------------------------------------

export async function createVendorCustomerAction(formData: FormData) {
  const user = await requireUser();
  if (!canCreateProjects(user)) throw new Error("Not authorized");
  const name = s(formData, "name");
  if (!name) throw new Error("Name is required");

  await prisma.vendorCustomer.create({
    data: {
      name,
      website: s(formData, "website"),
      description: s(formData, "description"),
      targetGeography: s(formData, "targetGeography"),
      targetProjectTypes: s(formData, "targetProjectTypes"),
      notes: s(formData, "notes"),
    },
  });
  revalidatePath("/vendor-customers");
  return { ok: true };
}

export async function updateVendorCustomerAction(id: string, formData: FormData) {
  const user = await requireUser();
  if (!canCreateProjects(user)) throw new Error("Not authorized");
  await prisma.vendorCustomer.update({
    where: { id },
    data: {
      name: s(formData, "name") ?? undefined,
      website: s(formData, "website"),
      description: s(formData, "description"),
      targetGeography: s(formData, "targetGeography"),
      targetProjectTypes: s(formData, "targetProjectTypes"),
      notes: s(formData, "notes"),
    },
  });
  revalidatePath("/vendor-customers");
  return { ok: true };
}

// --- Owner organizations ----------------------------------------------------

export async function createOwnerOrganizationAction(formData: FormData) {
  const user = await requireUser();
  if (!canCreateProjects(user)) throw new Error("Not authorized");
  const name = s(formData, "name");
  if (!name) throw new Error("Name is required");

  await prisma.ownerOrganization.create({
    data: {
      name,
      type: (s(formData, "type") as OwnerOrgType) ?? "OTHER",
      website: s(formData, "website"),
      state: s(formData, "state"),
      city: s(formData, "city"),
      address: s(formData, "address"),
      notes: s(formData, "notes"),
    },
  });
  revalidatePath("/owner-organizations");
  return { ok: true };
}

export async function updateOwnerOrganizationAction(
  id: string,
  formData: FormData
) {
  const user = await requireUser();
  if (!canCreateProjects(user)) throw new Error("Not authorized");
  await prisma.ownerOrganization.update({
    where: { id },
    data: {
      name: s(formData, "name") ?? undefined,
      type: (s(formData, "type") as OwnerOrgType) ?? undefined,
      website: s(formData, "website"),
      state: s(formData, "state"),
      city: s(formData, "city"),
      address: s(formData, "address"),
      notes: s(formData, "notes"),
    },
  });
  revalidatePath("/owner-organizations");
  return { ok: true };
}
