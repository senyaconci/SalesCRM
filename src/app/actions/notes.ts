"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { canEditProject } from "@/lib/permissions";

async function assertCanEdit(projectId: string) {
  const user = await requireUser();
  const project = await prisma.project.findUnique({
    where: { id: projectId },
    select: { assignedSdrId: true },
  });
  if (!project) throw new Error("Project not found");
  if (!canEditProject(user, project)) throw new Error("Not authorized");
  return user;
}

export async function createNoteAction(input: {
  projectId: string;
  contactId?: string | null;
  body: string;
}) {
  const user = await assertCanEdit(input.projectId);
  const body = input.body.trim();
  if (!body) throw new Error("Note cannot be empty");

  await prisma.$transaction(async (tx) => {
    await tx.note.create({
      data: {
        projectId: input.projectId,
        contactId: input.contactId ?? null,
        userId: user.id,
        body,
      },
    });
    // Mirror the note into the activity timeline so it appears chronologically.
    await tx.activity.create({
      data: {
        projectId: input.projectId,
        contactId: input.contactId ?? null,
        userId: user.id,
        type: "NOTE",
        direction: "INTERNAL",
        body,
      },
    });
    await tx.project.update({
      where: { id: input.projectId },
      data: { lastActivityAt: new Date() },
    });
  });

  revalidatePath(`/projects/${input.projectId}`);
  return { ok: true };
}

export async function updateNoteAction(input: { id: string; body: string }) {
  const user = await requireUser();
  const note = await prisma.note.findUnique({
    where: { id: input.id },
    select: { projectId: true, project: { select: { assignedSdrId: true } } },
  });
  if (!note) throw new Error("Note not found");
  if (!canEditProject(user, note.project)) throw new Error("Not authorized");

  await prisma.note.update({
    where: { id: input.id },
    data: { body: input.body.trim() },
  });
  revalidatePath(`/projects/${note.projectId}`);
  return { ok: true };
}

export async function deleteNoteAction(id: string) {
  const user = await requireUser();
  const note = await prisma.note.findUnique({
    where: { id },
    select: { projectId: true, project: { select: { assignedSdrId: true } } },
  });
  if (!note) throw new Error("Note not found");
  if (!canEditProject(user, note.project)) throw new Error("Not authorized");

  await prisma.note.delete({ where: { id } });
  revalidatePath(`/projects/${note.projectId}`);
  return { ok: true };
}
