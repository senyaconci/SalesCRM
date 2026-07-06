import type { Prisma, PrismaClient } from "@prisma/client";

type Db = PrismaClient | Prisma.TransactionClient;

/** Records a STATUS_CHANGE activity for a project status transition. */
export async function recordProjectStatusChange(
  db: Db,
  params: {
    projectId: string;
    userId: string;
    previousStatus: string;
    newStatus: string;
    note?: string;
  }
) {
  await db.activity.create({
    data: {
      projectId: params.projectId,
      userId: params.userId,
      type: "STATUS_CHANGE",
      direction: "INTERNAL",
      previousStatus: params.previousStatus,
      newStatus: params.newStatus,
      body:
        params.note ??
        `Project status changed from ${params.previousStatus} to ${params.newStatus}.`,
    },
  });
}

/** Records a STATUS_CHANGE activity tied to a contact. */
export async function recordContactStatusChange(
  db: Db,
  params: {
    projectId: string;
    contactId: string;
    userId: string;
    previousStatus: string;
    newStatus: string;
  }
) {
  await db.activity.create({
    data: {
      projectId: params.projectId,
      contactId: params.contactId,
      userId: params.userId,
      type: "STATUS_CHANGE",
      direction: "INTERNAL",
      previousStatus: params.previousStatus,
      newStatus: params.newStatus,
      body: `Contact status changed from ${params.previousStatus} to ${params.newStatus}.`,
    },
  });
}
