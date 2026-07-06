"use client";

import { useTransition } from "react";
import { Select, EnumOptions } from "@/components/ui/Form";
import {
  ProjectStatusBadge,
  StageBadge,
  PriorityBadge,
} from "@/components/ui/StatusBadges";
import { updateProjectAction, assignProjectAction } from "@/app/actions/projects";
import {
  PROJECT_STATUSES,
  PRIORITIES,
  projectStatusLabel,
} from "@/lib/labels";
import { formatCurrency } from "@/lib/format";
import type { ProjectStatus, Priority } from "@prisma/client";

interface Option {
  id: string;
  name: string;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </span>
      <div className="text-right text-sm text-slate-700">{children}</div>
    </div>
  );
}

export function ProjectSidePanel({
  project,
  sdrs,
  canEdit,
  canAssign,
}: {
  project: {
    id: string;
    status: string;
    stage: string;
    priority: string;
    budgetAmount: string | null;
    budgetText: string | null;
    locationCity: string | null;
    locationState: string | null;
    nextFollowUpAt: string | null;
    assignedSdrId: string | null;
    assignedSdrName: string | null;
    vendorName: string | null;
    ownerName: string | null;
  };
  sdrs: Option[];
  canEdit: boolean;
  canAssign: boolean;
}) {
  const [isPending, startTransition] = useTransition();

  const update = (data: Parameters<typeof updateProjectAction>[0]) =>
    startTransition(async () => {
      await updateProjectAction(data);
    });

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-2 text-sm font-semibold text-slate-900">Project</h3>

      <div className="divide-y divide-slate-100">
        <Row label="Status">
          {canEdit ? (
            <Select
              className="w-44"
              disabled={isPending}
              value={project.status}
              onChange={(e) =>
                update({ id: project.id, status: e.target.value as ProjectStatus })
              }
            >
              <EnumOptions
                values={PROJECT_STATUSES}
                labels={projectStatusLabel}
              />
            </Select>
          ) : (
            <ProjectStatusBadge status={project.status} />
          )}
        </Row>

        <Row label="Stage">
          <StageBadge stage={project.stage} />
        </Row>

        <Row label="Priority">
          {canEdit ? (
            <Select
              className="w-32"
              disabled={isPending}
              value={project.priority}
              onChange={(e) =>
                update({ id: project.id, priority: e.target.value as Priority })
              }
            >
              <EnumOptions values={PRIORITIES} />
            </Select>
          ) : (
            <PriorityBadge priority={project.priority} />
          )}
        </Row>

        <Row label="Assigned SDR">
          {canAssign ? (
            <Select
              className="w-44"
              disabled={isPending}
              value={project.assignedSdrId ?? ""}
              onChange={(e) =>
                startTransition(async () => {
                  await assignProjectAction({
                    projectId: project.id,
                    sdrId: e.target.value || null,
                  });
                })
              }
            >
              <option value="">Unassigned</option>
              {sdrs.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          ) : (
            <span>{project.assignedSdrName ?? "Unassigned"}</span>
          )}
        </Row>

        <Row label="Vendor">{project.vendorName ?? "—"}</Row>
        <Row label="Owner Org">{project.ownerName ?? "—"}</Row>
        <Row label="Budget">
          {formatCurrency(
            project.budgetAmount ? Number(project.budgetAmount) : null,
            project.budgetText
          )}
        </Row>
        <Row label="Location">
          {[project.locationCity, project.locationState]
            .filter(Boolean)
            .join(", ") || "—"}
        </Row>
        <Row label="Follow-up">
          {canEdit ? (
            <input
              type="date"
              disabled={isPending}
              defaultValue={project.nextFollowUpAt?.slice(0, 10) ?? ""}
              onChange={(e) =>
                update({
                  id: project.id,
                  nextFollowUpAt: e.target.value || null,
                })
              }
              className="rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-700 focus:border-blue-500 focus:outline-none"
            />
          ) : (
            <span>{project.nextFollowUpAt?.slice(0, 10) ?? "—"}</span>
          )}
        </Row>
      </div>
    </div>
  );
}
