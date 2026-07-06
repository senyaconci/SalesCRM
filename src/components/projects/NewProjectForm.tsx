"use client";

import { useFormStatus } from "react-dom";
import { createProjectAction } from "@/app/actions/projects";
import { Field, Input, Textarea, Select, EnumOptions } from "@/components/ui/Form";
import {
  CATEGORIES,
  STAGES,
  PRIORITIES,
  categoryLabel,
  stageLabel,
} from "@/lib/labels";

interface Option {
  id: string;
  name: string;
}

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
    >
      {pending ? "Creating…" : "Create Project"}
    </button>
  );
}

export function NewProjectForm({
  vendors,
  organizations,
  sdrs,
}: {
  vendors: Option[];
  organizations: Option[];
  sdrs: Option[];
}) {
  return (
    <form action={createProjectAction} className="space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-slate-900">
          Project details
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <Field label="Project title" required>
              <Input name="title" required placeholder="Central Steam Plant Boiler Replacement" />
            </Field>
          </div>
          <Field label="Vendor customer">
            <Select name="vendorCustomerId">
              <option value="">— Select vendor —</option>
              {vendors.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Owner organization">
            <Select name="ownerOrganizationId">
              <option value="">— Select organization —</option>
              {organizations.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Category">
            <Select name="category" defaultValue="BOILERS">
              <EnumOptions
                values={CATEGORIES}
                labels={Object.fromEntries(CATEGORIES.map((c) => [c, categoryLabel(c)]))}
              />
            </Select>
          </Field>
          <Field label="Stage">
            <Select name="stage" defaultValue="IDENTIFIED">
              <EnumOptions values={STAGES} labels={stageLabel} />
            </Select>
          </Field>
          <Field label="Priority">
            <Select name="priority" defaultValue="MEDIUM">
              <EnumOptions values={PRIORITIES} />
            </Select>
          </Field>
          <Field label="Assign SDR">
            <Select name="assignedSdrId">
              <option value="">— Unassigned —</option>
              {sdrs.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Budget amount (USD)">
            <Input name="budgetAmount" type="number" step="1" placeholder="8500000" />
          </Field>
          <Field label="Budget text (display)">
            <Input name="budgetText" placeholder="$8.5M" />
          </Field>
          <Field label="City">
            <Input name="locationCity" placeholder="Athens" />
          </Field>
          <Field label="State">
            <Input name="locationState" placeholder="GA" />
          </Field>
          <div className="md:col-span-2">
            <Field label="Summary">
              <Textarea name="summary" rows={3} placeholder="Short project summary for SDRs." />
            </Field>
          </div>
          <div className="md:col-span-2">
            <Field label="Evidence text" hint="Why is this project relevant? Source snippet, budget language, etc.">
              <Textarea name="evidenceText" rows={3} />
            </Field>
          </div>
          <Field label="Source URL">
            <Input name="sourceUrl" type="url" placeholder="https://…" />
          </Field>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-1 text-sm font-semibold text-slate-900">
          Project report (PDF)
        </h2>
        <p className="mb-3 text-xs text-slate-500">
          Upload the CapEx Signal report. Stored locally in dev; ready to move to
          object storage later.
        </p>
        <input
          type="file"
          name="pdf"
          accept="application/pdf"
          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
        />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-1 text-sm font-semibold text-slate-900">Contacts</h2>
        <p className="mb-3 text-xs text-slate-500">
          Paste as JSON array (fields: fullName, title, email, phone, mobilePhone)
          or CSV lines: <code>name, title, email, phone, mobile</code>.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Buyer-side contacts">
            <Textarea
              name="buyerContacts"
              rows={5}
              placeholder={'Pat Johnson, Director of Facilities, pat@uga.edu, 404-555-1000'}
            />
          </Field>
          <Field label="Vendor-side contacts">
            <Textarea
              name="vendorContacts"
              rows={5}
              placeholder={'Alex Carter, Regional Sales Manager, alex@vendor.com, 470-555-3000'}
            />
          </Field>
        </div>
      </section>

      <div className="flex justify-end">
        <SubmitButton />
      </div>
    </form>
  );
}
