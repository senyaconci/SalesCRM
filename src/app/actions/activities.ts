"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { canEditProject } from "@/lib/permissions";
import { computeActivityEffects, advanceProjectStatus } from "@/lib/workflow";
import {
  recordContactStatusChange,
  recordProjectStatusChange,
} from "@/lib/audit";
import type {
  ActivityType,
  ActivityDirection,
  ActivityOutcome,
  ContactStatus,
} from "@prisma/client";

export interface LogActivityInput {
  projectId: string;
  contactId?: string | null;
  type: ActivityType;
  direction?: ActivityDirection;
  subject?: string;
  body?: string;
  outcome?: ActivityOutcome | null;
  /** When outcome is INTERESTED, request VALIDATED_RELEVANT vs VALIDATING. */
  relevantValidation?: boolean;
  /** Explicit contact status override chosen in the modal. */
  contactStatusOverride?: ContactStatus | null;
  recordingUrl?: string | null;
  transcript?: string | null;
}

/**
 * Creates an activity and applies the status-automation rules described in the
 * product spec (first-activity → OUTREACH_STARTED, outcome-driven contact and
 * project status advancement, etc.). All work happens in one transaction.
 */
export async function logActivityAction(input: LogActivityInput) {
  const user = await requireUser();

  const project = await prisma.project.findUnique({
    where: { id: input.projectId },
    select: { id: true, status: true, assignedSdrId: true },
  });
  if (!project) throw new Error("Project not found");
  if (!canEditProject(user, project)) throw new Error("Not authorized");

  const effects = computeActivityEffects({
    type: input.type,
    outcome: input.outcome ?? undefined,
    relevantValidation: input.relevantValidation,
  });

  const contactStatus: ContactStatus | null =
    input.contactStatusOverride ?? (effects.contactStatus as ContactStatus | null);

  await prisma.$transaction(async (tx) => {
    await tx.activity.create({
      data: {
        projectId: input.projectId,
        contactId: input.contactId ?? null,
        userId: user.id,
        type: input.type,
        direction: input.direction ?? "OUTBOUND",
        subject: input.subject,
        body: input.body,
        outcome: input.outcome ?? null,
        recordingUrl: input.recordingUrl ?? null,
        transcript: input.transcript ?? null,
      },
    });

    let currentStatus = project.status as string;

    // Rule 1: first outreach moves NEW/ASSIGNED to OUTREACH_STARTED.
    const isOutreach =
      input.type === "CALL" || input.type === "EMAIL" || input.type === "SMS";
    if (isOutreach && (currentStatus === "NEW" || currentStatus === "ASSIGNED")) {
      const next = "OUTREACH_STARTED";
      await recordProjectStatusChange(tx, {
        projectId: input.projectId,
        userId: user.id,
        previousStatus: currentStatus,
        newStatus: next,
      });
      currentStatus = next;
    }

    // Outcome-driven project advancement.
    if (effects.projectStatusTarget) {
      const advanced = advanceProjectStatus(
        currentStatus,
        effects.projectStatusTarget
      );
      if (advanced !== currentStatus) {
        await recordProjectStatusChange(tx, {
          projectId: input.projectId,
          userId: user.id,
          previousStatus: currentStatus,
          newStatus: advanced,
        });
        currentStatus = advanced;
      }
    }

    await tx.project.update({
      where: { id: input.projectId },
      data: {
        status: currentStatus as never,
        lastActivityAt: new Date(),
      },
    });

    // Contact status update (if this activity targets a contact).
    if (input.contactId && contactStatus) {
      const contact = await tx.contact.findUnique({
        where: { id: input.contactId },
        select: { status: true },
      });
      if (contact && contact.status !== contactStatus) {
        await recordContactStatusChange(tx, {
          projectId: input.projectId,
          contactId: input.contactId,
          userId: user.id,
          previousStatus: contact.status,
          newStatus: contactStatus,
        });
        await tx.contact.update({
          where: { id: input.contactId },
          data: { status: contactStatus },
        });
      }
    }
  });

  revalidatePath(`/projects/${input.projectId}`);
  return { ok: true, promptAddReferredContact: effects.promptAddReferredContact };
}
