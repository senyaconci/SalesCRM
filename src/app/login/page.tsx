"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { loginAction } from "./actions";
import { Field, Input } from "@/components/ui/Form";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
    >
      {pending ? "Signing in…" : "Sign in"}
    </button>
  );
}

export default function LoginPage() {
  const [error, formAction] = useActionState(loginAction, undefined);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-blue-600 text-lg font-bold text-white">
            CS
          </div>
          <h1 className="text-xl font-bold text-slate-900">CapEx Signal CRM</h1>
          <p className="mt-1 text-sm text-slate-500">
            Project-based outreach for public capital projects
          </p>
        </div>

        <form
          action={formAction}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <Field label="Email" required>
            <Input
              name="email"
              type="email"
              autoComplete="email"
              required
              placeholder="you@capexsignal.com"
            />
          </Field>
          <Field label="Password" required>
            <Input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              placeholder="••••••••"
            />
          </Field>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <SubmitButton />
        </form>

        <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-500">
          <p className="font-medium text-slate-600">Demo accounts (password123):</p>
          <ul className="mt-1 space-y-0.5">
            <li>admin@capexsignal.com — Admin</li>
            <li>manager@capexsignal.com — Manager</li>
            <li>sdr1@capexsignal.com — SDR</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
