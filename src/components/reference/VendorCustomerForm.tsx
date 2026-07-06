"use client";

import { useRef } from "react";
import { useFormStatus } from "react-dom";
import { createVendorCustomerAction } from "@/app/actions/reference-data";
import { Field, Input, Textarea } from "@/components/ui/Form";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
    >
      {pending ? "Saving…" : "Add Vendor Customer"}
    </button>
  );
}

export function VendorCustomerForm() {
  const ref = useRef<HTMLFormElement>(null);
  return (
    <form
      ref={ref}
      action={async (fd) => {
        await createVendorCustomerAction(fd);
        ref.current?.reset();
      }}
      className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-slate-900">
        Add Vendor Customer
      </h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Name" required>
          <Input name="name" required placeholder="Cleaver-Brooks" />
        </Field>
        <Field label="Website">
          <Input name="website" placeholder="https://…" />
        </Field>
        <Field label="Target geography">
          <Input name="targetGeography" placeholder="Southeast US" />
        </Field>
        <Field label="Target project types">
          <Input name="targetProjectTypes" placeholder="Boilers, Steam" />
        </Field>
        <div className="md:col-span-2">
          <Field label="Description">
            <Textarea name="description" rows={2} />
          </Field>
        </div>
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
