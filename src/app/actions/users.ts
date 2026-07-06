"use server";

import { revalidatePath } from "next/cache";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { canManageUsers } from "@/lib/permissions";
import type { Role } from "@prisma/client";

export async function createUserAction(formData: FormData) {
  const user = await requireUser();
  if (!canManageUsers(user)) throw new Error("Not authorized");

  const name = (formData.get("name") as string)?.trim();
  const email = (formData.get("email") as string)?.trim().toLowerCase();
  const password = (formData.get("password") as string) ?? "";
  const role = (formData.get("role") as Role) ?? "SDR";

  if (!name || !email || password.length < 6) {
    throw new Error("Name, email, and a 6+ char password are required");
  }

  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) throw new Error("A user with that email already exists");

  await prisma.user.create({
    data: {
      name,
      email,
      role,
      passwordHash: await bcrypt.hash(password, 10),
    },
  });

  revalidatePath("/users");
  return { ok: true };
}

export async function setUserActiveAction(id: string, isActive: boolean) {
  const user = await requireUser();
  if (!canManageUsers(user)) throw new Error("Not authorized");
  await prisma.user.update({ where: { id }, data: { isActive } });
  revalidatePath("/users");
  return { ok: true };
}
