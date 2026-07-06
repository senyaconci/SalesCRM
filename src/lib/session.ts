import { redirect } from "next/navigation";
import { auth } from "@/auth";

export interface SessionUser {
  id: string;
  name?: string | null;
  email?: string | null;
  role: string;
}

export async function getCurrentUser(): Promise<SessionUser | null> {
  const session = await auth();
  if (!session?.user?.id) return null;
  return {
    id: session.user.id,
    name: session.user.name,
    email: session.user.email,
    role: session.user.role,
  };
}

/** Returns the current user or redirects to /login. */
export async function requireUser(): Promise<SessionUser> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return user;
}

/** Requires that the current user has one of the given roles. */
export async function requireRole(roles: string[]): Promise<SessionUser> {
  const user = await requireUser();
  if (!roles.includes(user.role)) redirect("/dashboard");
  return user;
}

export const isAdmin = (u: { role: string }) => u.role === "ADMIN";
export const isManager = (u: { role: string }) => u.role === "MANAGER";
export const isSdr = (u: { role: string }) => u.role === "SDR";
export const isAdminOrManager = (u: { role: string }) =>
  u.role === "ADMIN" || u.role === "MANAGER";
