"use client";

import { useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import { createUserAction } from "@/app/actions/users";
import { Field, Input, Select } from "@/components/ui/Form";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
    >
      {pending ? "Creating…" : "Create User"}
    </button>
  );
}

export function UserForm() {
  const ref = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <form
      ref={ref}
      action={async (fd) => {
        setError(null);
        try {
          await createUserAction(fd);
          ref.current?.reset();
        } catch (e) {
          setError(e instanceof Error ? e.message : "Failed to create user");
        }
      }}
      className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-slate-900">Create User</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Field label="Name" required>
          <Input name="name" required />
        </Field>
        <Field label="Email" required>
          <Input name="email" type="email" required />
        </Field>
        <Field label="Password" required hint="Min 6 characters">
          <Input name="password" type="password" required minLength={6} />
        </Field>
        <Field label="Role">
          <Select name="role" defaultValue="SDR">
            <option value="SDR">SDR</option>
            <option value="MANAGER">Manager</option>
            <option value="ADMIN">Admin</option>
          </Select>
        </Field>
      </div>
      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <SubmitButton />
      </div>
    </form>
  );
}
