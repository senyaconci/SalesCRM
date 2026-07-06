"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { canEditProject } from "@/lib/permissions";
import { recordContactStatusChange } from "@/lib/audit";
import type {
  ContactSide,
  ContactStatus,
  ContactRelevance,
} from "@prisma/client";

export interface ContactInput {
  projectId: string;
  side: ContactSide;
  firstName?: string;
  lastName?: string;
  fullName?: string;
  title?: string;
  email?: string;
  phone?: string;
  mobilePhone?: string;
  linkedinUrl?: string;
  source?: string;
  relevance?: ContactRelevance;
  status?: ContactStatus;
  notes?: string;
}

async function assertCanEditProject(projectId: string) {
  const user = await requireUser();
  const project = await prisma.project.findUnique({
    where: { id: projectId },
    select: { assignedSdrId: true, ownerOrganizationId: true, vendorCustomerId: true },
  });
  if (!project) throw new Error("Project not found");
  if (!canEditProject(user, project)) throw new Error("Not authorized");
  return { user, project };
}

function deriveFullName(input: {
  fullName?: string;
  firstName?: string;
  lastName?: string;
}): string {
  if (input.fullName?.trim()) return input.fullName.trim();
  const combined = [input.firstName, input.lastName]
    .filter(Boolean)
    .join(" ")
    .trim();
  return combined || "Unnamed Contact";
}

export async function createContactAction(input: ContactInput) {
  const { project } = await assertCanEditProject(input.projectId);

  await prisma.contact.create({
    data: {
      projectId: input.projectId,
      side: input.side,
      firstName: input.firstName || null,
      lastName: input.lastName || null,
      fullName: deriveFullName(input),
      title: input.title || null,
      email: input.email || null,
      phone: input.phone || null,
      mobilePhone: input.mobilePhone || null,
      linkedinUrl: input.linkedinUrl || null,
      source: input.source || null,
      relevance: input.relevance ?? "UNKNOWN",
      status: input.status ?? "NOT_CONTACTED",
      notes: input.notes || null,
      // Link to the appropriate org/vendor based on side.
      organizationId:
        input.side === "BUYER" ? project.ownerOrganizationId : null,
      vendorCustomerId:
        input.side === "VENDOR" ? project.vendorCustomerId : null,
    },
  });

  revalidatePath(`/projects/${input.projectId}`);
  return { ok: true };
}

export async function updateContactAction(
  id: string,
  input: Partial<ContactInput>
) {
  const user = await requireUser();
  const contact = await prisma.contact.findUnique({
    where: { id },
    select: { projectId: true, project: { select: { assignedSdrId: true } } },
  });
  if (!contact) throw new Error("Contact not found");
  if (!canEditProject(user, contact.project)) throw new Error("Not authorized");

  await prisma.contact.update({
    where: { id },
    data: {
      side: input.side,
      firstName: input.firstName,
      lastName: input.lastName,
      fullName:
        input.fullName || input.firstName || input.lastName
          ? deriveFullName(input)
          : undefined,
      title: input.title,
      email: input.email,
      phone: input.phone,
      mobilePhone: input.mobilePhone,
      linkedinUrl: input.linkedinUrl,
      source: input.source,
      relevance: input.relevance,
      notes: input.notes,
    },
  });

  revalidatePath(`/projects/${contact.projectId}`);
  return { ok: true };
}

export async function updateContactStatusAction(
  id: string,
  status: ContactStatus
) {
  const user = await requireUser();
  const contact = await prisma.contact.findUnique({
    where: { id },
    select: {
      projectId: true,
      status: true,
      project: { select: { assignedSdrId: true } },
    },
  });
  if (!contact) throw new Error("Contact not found");
  if (!canEditProject(user, contact.project)) throw new Error("Not authorized");

  if (contact.status !== status) {
    await prisma.$transaction(async (tx) => {
      await recordContactStatusChange(tx, {
        projectId: contact.projectId,
        contactId: id,
        userId: user.id,
        previousStatus: contact.status,
        newStatus: status,
      });
      await tx.contact.update({ where: { id }, data: { status } });
      await tx.project.update({
        where: { id: contact.projectId },
        data: { lastActivityAt: new Date() },
      });
    });
  }

  revalidatePath(`/projects/${contact.projectId}`);
  return { ok: true };
}

export async function deleteContactAction(id: string) {
  const user = await requireUser();
  const contact = await prisma.contact.findUnique({
    where: { id },
    select: { projectId: true, project: { select: { assignedSdrId: true } } },
  });
  if (!contact) throw new Error("Contact not found");
  if (!canEditProject(user, contact.project)) throw new Error("Not authorized");

  await prisma.contact.delete({ where: { id } });
  revalidatePath(`/projects/${contact.projectId}`);
  return { ok: true };
}
