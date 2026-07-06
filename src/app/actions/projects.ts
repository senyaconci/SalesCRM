"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import {
  canCreateProjects,
  canEditProject,
  canAssignProjects,
} from "@/lib/permissions";
import { recordProjectStatusChange } from "@/lib/audit";
import { fileStorage } from "@/lib/storage";
import type {
  ProjectCategory,
  ProjectStage,
  ProjectStatus,
  Priority,
  ContactSide,
} from "@prisma/client";

function str(fd: FormData, key: string): string | null {
  const v = fd.get(key);
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t.length ? t : null;
}

function parseContactsBlob(blob: string | null, side: ContactSide) {
  if (!blob) return [];
  const trimmed = blob.trim();
  if (!trimmed) return [];

  type RawContact = {
    fullName?: string;
    name?: string;
    firstName?: string;
    lastName?: string;
    title?: string;
    email?: string;
    phone?: string;
    mobilePhone?: string;
    linkedinUrl?: string;
  };

  let rows: RawContact[] = [];
  try {
    if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
      const parsed = JSON.parse(trimmed);
      rows = Array.isArray(parsed) ? parsed : [parsed];
    } else {
      // CSV: name,title,email,phone[,mobile]
      rows = trimmed
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [name, title, email, phone, mobilePhone] = line
            .split(",")
            .map((c) => c.trim());
          return { fullName: name, title, email, phone, mobilePhone };
        });
    }
  } catch {
    return [];
  }

  return rows
    .map((r) => {
      const fullName =
        r.fullName ||
        r.name ||
        [r.firstName, r.lastName].filter(Boolean).join(" ");
      if (!fullName) return null;
      return {
        side,
        fullName,
        firstName: r.firstName ?? null,
        lastName: r.lastName ?? null,
        title: r.title ?? null,
        email: r.email ?? null,
        phone: r.phone ?? null,
        mobilePhone: r.mobilePhone ?? null,
        linkedinUrl: r.linkedinUrl ?? null,
        source: "Import",
      };
    })
    .filter((r): r is NonNullable<typeof r> => r !== null);
}

export async function createProjectAction(formData: FormData) {
  const user = await requireUser();
  if (!canCreateProjects(user)) throw new Error("Not authorized");

  const title = str(formData, "title");
  if (!title) throw new Error("Title is required");

  const budgetRaw = str(formData, "budgetAmount");
  const assignedSdrId = str(formData, "assignedSdrId");

  let pdfUrl: string | null = null;
  let pdfFileName: string | null = null;
  const pdf = formData.get("pdf");
  if (pdf instanceof File && pdf.size > 0) {
    const stored = await fileStorage.save(pdf, "projects");
    pdfUrl = stored.url;
    pdfFileName = stored.fileName;
  }

  const buyerContacts = parseContactsBlob(str(formData, "buyerContacts"), "BUYER");
  const vendorContacts = parseContactsBlob(
    str(formData, "vendorContacts"),
    "VENDOR"
  );

  const ownerOrganizationId = str(formData, "ownerOrganizationId");
  const vendorCustomerId = str(formData, "vendorCustomerId");

  const project = await prisma.project.create({
    data: {
      title,
      summary: str(formData, "summary"),
      description: str(formData, "description"),
      evidenceText: str(formData, "evidenceText"),
      sourceUrl: str(formData, "sourceUrl"),
      category: (str(formData, "category") as ProjectCategory) ?? "OTHER",
      stage: (str(formData, "stage") as ProjectStage) ?? "UNKNOWN",
      priority: (str(formData, "priority") as Priority) ?? "MEDIUM",
      status: assignedSdrId ? "ASSIGNED" : "NEW",
      budgetAmount: budgetRaw ? new Prisma.Decimal(budgetRaw) : null,
      budgetText: str(formData, "budgetText"),
      locationCity: str(formData, "locationCity"),
      locationState: str(formData, "locationState"),
      ownerOrganizationId,
      vendorCustomerId,
      assignedSdrId,
      projectOwnerId: user.id,
      pdfUrl,
      pdfFileName,
      contacts: {
        create: [...buyerContacts, ...vendorContacts].map((c) => ({
          ...c,
          organizationId: c.side === "BUYER" ? ownerOrganizationId : null,
          vendorCustomerId: c.side === "VENDOR" ? vendorCustomerId : null,
        })),
      },
    },
  });

  if (assignedSdrId) {
    await prisma.projectAssignmentHistory.create({
      data: {
        projectId: project.id,
        assignedToId: assignedSdrId,
        assignedById: user.id,
      },
    });
  }

  redirect(`/projects/${project.id}`);
}

export interface UpdateProjectInput {
  id: string;
  title?: string;
  summary?: string;
  description?: string;
  evidenceText?: string;
  sourceUrl?: string;
  category?: ProjectCategory;
  stage?: ProjectStage;
  status?: ProjectStatus;
  priority?: Priority;
  budgetAmount?: string | null;
  budgetText?: string | null;
  locationCity?: string | null;
  locationState?: string | null;
  ownerOrganizationId?: string | null;
  vendorCustomerId?: string | null;
  nextFollowUpAt?: string | null;
}

export async function updateProjectAction(input: UpdateProjectInput) {
  const user = await requireUser();
  const existing = await prisma.project.findUnique({
    where: { id: input.id },
    select: { assignedSdrId: true, status: true },
  });
  if (!existing) throw new Error("Project not found");
  if (!canEditProject(user, existing)) throw new Error("Not authorized");

  const statusChanged =
    input.status !== undefined && input.status !== existing.status;

  await prisma.$transaction(async (tx) => {
    await tx.project.update({
      where: { id: input.id },
      data: {
        title: input.title,
        summary: input.summary,
        description: input.description,
        evidenceText: input.evidenceText,
        sourceUrl: input.sourceUrl,
        category: input.category,
        stage: input.stage,
        status: input.status,
        priority: input.priority,
        budgetAmount:
          input.budgetAmount === undefined
            ? undefined
            : input.budgetAmount
              ? new Prisma.Decimal(input.budgetAmount)
              : null,
        budgetText: input.budgetText,
        locationCity: input.locationCity,
        locationState: input.locationState,
        ownerOrganizationId: input.ownerOrganizationId,
        vendorCustomerId: input.vendorCustomerId,
        nextFollowUpAt:
          input.nextFollowUpAt === undefined
            ? undefined
            : input.nextFollowUpAt
              ? new Date(input.nextFollowUpAt)
              : null,
      },
    });

    if (statusChanged) {
      await recordProjectStatusChange(tx, {
        projectId: input.id,
        userId: user.id,
        previousStatus: existing.status,
        newStatus: input.status as string,
        note: `Status manually changed to ${input.status}.`,
      });
    }
  });

  revalidatePath(`/projects/${input.id}`);
  return { ok: true };
}

export async function assignProjectAction(input: {
  projectId: string;
  sdrId: string | null;
}) {
  const user = await requireUser();
  if (!canAssignProjects(user)) throw new Error("Not authorized");

  const project = await prisma.project.findUnique({
    where: { id: input.projectId },
    select: { assignedSdrId: true, status: true },
  });
  if (!project) throw new Error("Project not found");

  if (project.assignedSdrId === input.sdrId) return { ok: true };

  await prisma.$transaction(async (tx) => {
    await tx.project.update({
      where: { id: input.projectId },
      data: {
        assignedSdrId: input.sdrId,
        status:
          input.sdrId && project.status === "NEW" ? "ASSIGNED" : undefined,
      },
    });

    await tx.projectAssignmentHistory.create({
      data: {
        projectId: input.projectId,
        assignedToId: input.sdrId,
        assignedById: user.id,
        previousAssignedToId: project.assignedSdrId,
      },
    });

    await tx.activity.create({
      data: {
        projectId: input.projectId,
        userId: user.id,
        type: "ASSIGNMENT_CHANGE",
        direction: "INTERNAL",
        body: input.sdrId
          ? "Project assignment changed."
          : "Project unassigned.",
      },
    });
  });

  revalidatePath(`/projects/${input.projectId}`);
  revalidatePath("/dashboard");
  revalidatePath("/my-projects");
  return { ok: true };
}

export async function uploadProjectPdfAction(formData: FormData) {
  const user = await requireUser();
  const projectId = str(formData, "projectId");
  if (!projectId) throw new Error("projectId required");

  const project = await prisma.project.findUnique({
    where: { id: projectId },
    select: { assignedSdrId: true },
  });
  if (!project) throw new Error("Project not found");
  if (!canEditProject(user, project)) throw new Error("Not authorized");

  const pdf = formData.get("pdf");
  if (!(pdf instanceof File) || pdf.size === 0) throw new Error("No file");

  const stored = await fileStorage.save(pdf, "projects");
  await prisma.project.update({
    where: { id: projectId },
    data: { pdfUrl: stored.url, pdfFileName: stored.fileName },
  });

  revalidatePath(`/projects/${projectId}`);
  return { ok: true };
}
