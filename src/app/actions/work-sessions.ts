"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";

/** Returns the user's currently-open work session, if any. */
export async function getActiveWorkSession(userId: string) {
  return prisma.workSession.findFirst({
    where: { userId, endedAt: null },
    orderBy: { startedAt: "desc" },
  });
}

export async function startWorkSessionAction() {
  const user = await requireUser();
  const existing = await getActiveWorkSession(user.id);
  if (existing) return { ok: true, session: existing };

  const session = await prisma.workSession.create({
    data: { userId: user.id },
  });
  revalidatePath("/", "layout");
  return { ok: true, session };
}

export async function stopWorkSessionAction() {
  const user = await requireUser();
  const open = await getActiveWorkSession(user.id);
  if (!open) return { ok: true };

  const endedAt = new Date();
  const durationSeconds = Math.max(
    0,
    Math.round((endedAt.getTime() - open.startedAt.getTime()) / 1000)
  );

  await prisma.workSession.update({
    where: { id: open.id },
    data: { endedAt, durationSeconds },
  });
  revalidatePath("/", "layout");
  revalidatePath("/work-sessions");
  return { ok: true };
}
