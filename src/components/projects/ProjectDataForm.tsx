"use client";

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea, Select, EnumOptions } from "@/components/ui/Form";
import { updateProjectAction } from "@/app/actions/projects";
import {
  CATEGORIES,
  STAGES,
  PRIORITIES,
  PROJECT_STATUSES,
  categoryLabel,
  stageLabel,
  projectStatusLabel,
} from "@/lib/labels";
import type {
  ProjectCategory,
  ProjectStage,
  ProjectStatus,
  Priority,
} from "@prisma/client";

interface Option {
  id: string;
  name: string;
}

export interface ProjectDataDTO {
  id: string;
  title: string;
  summary: string | null;
  description: string | null;
  evidenceText: string | null;
  sourceUrl: string | null;
  category: string;
  stage: string;
  status: string;
  priority: string;
  budgetAmount: string | null;
  budgetText: string | null;
  ownerOrganizationId: string | null;
  vendorCustomerId: string | null;
  nextFollowUpAt: string | null;
}

export function ProjectDataForm({
  project,
  vendors,
  organizations,
  canEdit,
}: {
  project: ProjectDataDTO;
  vendors: Option[];
  organizations: Option[];
  canEdit: boolean;
}) {
  const [isPending, startTransition] = useTransition();
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({
    title: project.title,
    summary: project.summary ?? "",
    description: project.description ?? "",
    evidenceText: project.evidenceText ?? "",
    sourceUrl: project.sourceUrl ?? "",
    category: project.category,
    stage: project.stage,
    status: project.status,
    priority: project.priority,
    budgetAmount: project.budgetAmount ?? "",
    budgetText: project.budgetText ?? "",
    ownerOrganizationId: project.ownerOrganizationId ?? "",
    vendorCustomerId: project.vendorCustomerId ?? "",
    nextFollowUpAt: project.nextFollowUpAt?.slice(0, 10) ?? "",
  });

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
    setSaved(false);
  };

  const save = () => {
    startTransition(async () => {
      await updateProjectAction({
        id: project.id,
        title: form.title,
        summary: form.summary,
        description: form.description,
        evidenceText: form.evidenceText,
        sourceUrl: form.sourceUrl,
        category: form.category as ProjectCategory,
        stage: form.stage as ProjectStage,
        status: form.status as ProjectStatus,
        priority: form.priority as Priority,
        budgetAmount: form.budgetAmount || null,
        budgetText: form.budgetText || null,
        ownerOrganizationId: form.ownerOrganizationId || null,
        vendorCustomerId: form.vendorCustomerId || null,
        nextFollowUpAt: form.nextFollowUpAt || null,
      });
      setSaved(true);
    });
  };

  const disabled = !canEdit;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <Field label="Title">
            <Input value={form.title} onChange={set("title")} disabled={disabled} />
          </Field>
        </div>
        <Field label="Status">
          <Select value={form.status} onChange={set("status")} disabled={disabled}>
            <EnumOptions values={PROJECT_STATUSES} labels={projectStatusLabel} />
          </Select>
        </Field>
        <Field label="Priority">
          <Select value={form.priority} onChange={set("priority")} disabled={disabled}>
            <EnumOptions values={PRIORITIES} />
          </Select>
        </Field>
        <Field label="Category">
          <Select value={form.category} onChange={set("category")} disabled={disabled}>
            <EnumOptions
              values={CATEGORIES}
              labels={Object.fromEntries(CATEGORIES.map((c) => [c, categoryLabel(c)]))}
            />
          </Select>
        </Field>
        <Field label="Stage">
          <Select value={form.stage} onChange={set("stage")} disabled={disabled}>
            <EnumOptions values={STAGES} labels={stageLabel} />
          </Select>
        </Field>
        <Field label="Vendor customer">
          <Select
            value={form.vendorCustomerId}
            onChange={set("vendorCustomerId")}
            disabled={disabled}
          >
            <option value="">— None —</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Owner organization">
          <Select
            value={form.ownerOrganizationId}
            onChange={set("ownerOrganizationId")}
            disabled={disabled}
          >
            <option value="">— None —</option>
            {organizations.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Budget amount (USD)">
          <Input
            type="number"
            value={form.budgetAmount}
            onChange={set("budgetAmount")}
            disabled={disabled}
          />
        </Field>
        <Field label="Budget text">
          <Input
            value={form.budgetText}
            onChange={set("budgetText")}
            disabled={disabled}
          />
        </Field>
        <Field label="Next follow-up">
          <Input
            type="date"
            value={form.nextFollowUpAt}
            onChange={set("nextFollowUpAt")}
            disabled={disabled}
          />
        </Field>
        <Field label="Source URL">
          <Input
            value={form.sourceUrl}
            onChange={set("sourceUrl")}
            disabled={disabled}
          />
        </Field>
        <div className="md:col-span-2">
          <Field label="Summary">
            <Textarea
              rows={3}
              value={form.summary}
              onChange={set("summary")}
              disabled={disabled}
            />
          </Field>
        </div>
        <div className="md:col-span-2">
          <Field label="Description">
            <Textarea
              rows={3}
              value={form.description}
              onChange={set("description")}
              disabled={disabled}
            />
          </Field>
        </div>
        <div className="md:col-span-2">
          <Field label="Evidence text">
            <Textarea
              rows={3}
              value={form.evidenceText}
              onChange={set("evidenceText")}
              disabled={disabled}
            />
          </Field>
        </div>
      </div>

      {canEdit && (
        <div className="mt-4 flex items-center justify-end gap-3">
          {saved && <span className="text-sm text-green-600">Saved</span>}
          <Button onClick={save} disabled={isPending}>
            {isPending ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      )}
    </div>
  );
}
