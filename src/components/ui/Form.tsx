import React from "react";
import { enumLabel } from "@/lib/labels";

const fieldBase =
  "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

export function Field({
  label,
  children,
  hint,
  required,
}: {
  label?: string;
  children: React.ReactNode;
  hint?: string;
  required?: boolean;
}) {
  return (
    <label className="block space-y-1">
      {label && (
        <span className="text-xs font-medium text-slate-700">
          {label}
          {required && <span className="text-red-500"> *</span>}
        </span>
      )}
      {children}
      {hint && <span className="block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { className = "", ...rest } = props;
  return <input className={`${fieldBase} ${className}`} {...rest} />;
}

export function Textarea(
  props: React.TextareaHTMLAttributes<HTMLTextAreaElement>
) {
  const { className = "", ...rest } = props;
  return <textarea className={`${fieldBase} ${className}`} {...rest} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  const { className = "", children, ...rest } = props;
  return (
    <select className={`${fieldBase} ${className}`} {...rest}>
      {children}
    </select>
  );
}

/**
 * Renders <option> elements from an enum value list, using a label map or the
 * default title-casing when no map is supplied.
 */
export function EnumOptions({
  values,
  labels,
  includeBlank,
  blankLabel = "—",
}: {
  values: string[];
  labels?: Record<string, string>;
  includeBlank?: boolean;
  blankLabel?: string;
}) {
  return (
    <>
      {includeBlank && <option value="">{blankLabel}</option>}
      {values.map((v) => (
        <option key={v} value={v}>
          {labels?.[v] ?? enumLabel(v)}
        </option>
      ))}
    </>
  );
}
