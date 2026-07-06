"use client";

import { useRef } from "react";
import { useFormStatus } from "react-dom";
import { createOwnerOrganizationAction } from "@/app/actions/reference-data";
import { Field, Input, Textarea, Select, EnumOptions } from "@/components/ui/Form";
import { OWNER_ORG_TYPES } from "@/lib/labels";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
    >
      {pending ? "Saving…" : "Add Owner Organization"}
    </button>
  );
}

export function OwnerOrganizationForm() {
  const ref = useRef<HTMLFormElement>(null);
  return (
    <form
      ref={ref}
      action={async (fd) => {
        await createOwnerOrganizationAction(fd);
        ref.current?.reset();
      }}
      className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-slate-900">
        Add Owner Organization
      </h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Name" required>
          <Input name="name" required placeholder="University of Georgia" />
        </Field>
        <Field label="Type">
          <Select name="type" defaultValue="UNIVERSITY">
            <EnumOptions values={OWNER_ORG_TYPES} />
          </Select>
        </Field>
        <Field label="Website">
          <Input name="website" placeholder="https://…" />
        </Field>
        <Field label="City">
          <Input name="city" />
        </Field>
        <Field label="State">
          <Input name="state" placeholder="GA" />
        </Field>
        <Field label="Address">
          <Input name="address" />
        </Field>
        <div className="md:col-span-2">
          <Field label="Notes">
            <Textarea name="notes" rows={2} />
          </Field>
        </div>
      </div>
      <div className="flex justify-end">
        <SubmitButton />
      </div>
    </form>
  );
}
