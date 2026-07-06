import type { SessionUser } from "@/lib/session";
import type { Prisma } from "@prisma/client";

/**
 * Central access-control rules for projects.
 *
 * - ADMIN: full access to everything.
 * - MANAGER: can see and edit all projects, assign, review activity.
 * - SDR: can only see and update projects assigned to them; cannot delete.
 */

export function projectVisibilityWhere(user: SessionUser): Prisma.ProjectWhereInput {
  if (user.role === "ADMIN" || user.role === "MANAGER") return {};
  return { assignedSdrId: user.id };
}

export function canViewProject(
  user: SessionUser,
  project: { assignedSdrId: string | null }
): boolean {
  if (user.role === "ADMIN" || user.role === "MANAGER") return true;
  return project.assignedSdrId === user.id;
}

export function canEditProject(
  user: SessionUser,
  project: { assignedSdrId: string | null }
): boolean {
  return canViewProject(user, project);
}

export function canDeleteProject(user: SessionUser): boolean {
  return user.role === "ADMIN" || user.role === "MANAGER";
}

export function canAssignProjects(user: SessionUser): boolean {
  return user.role === "ADMIN" || user.role === "MANAGER";
}

export function canManageUsers(user: SessionUser): boolean {
  return user.role === "ADMIN";
}

export function canCreateProjects(user: SessionUser): boolean {
  return user.role === "ADMIN" || user.role === "MANAGER";
}
