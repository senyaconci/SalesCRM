"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback } from "react";
import { Select, Input } from "@/components/ui/Form";
import {
  PROJECT_STATUSES,
  STAGES,
  CATEGORIES,
  PRIORITIES,
  projectStatusLabel,
  stageLabel,
  enumLabel,
  categoryLabel,
} from "@/lib/labels";

interface Option {
  id: string;
  name: string;
}

export function ProjectFilters({
  sdrs,
  vendors,
  showSdr = true,
}: {
  sdrs?: Option[];
  vendors?: Option[];
  showSdr?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const setParam = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) params.set(key, value);
      else params.delete(key);
      router.push(`${pathname}?${params.toString()}`);
    },
    [router, pathname, searchParams]
  );

  const val = (k: string) => searchParams.get(k) ?? "";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        defaultValue={val("q")}
        placeholder="Search title, org, vendor, state…"
        className="w-64"
        onKeyDown={(e) => {
          if (e.key === "Enter") setParam("q", e.currentTarget.value);
        }}
      />
      <Select
        value={val("status")}
        onChange={(e) => setParam("status", e.target.value)}
        className="w-auto"
      >
        <option value="">All statuses</option>
        {PROJECT_STATUSES.map((s) => (
          <option key={s} value={s}>
            {projectStatusLabel[s]}
          </option>
        ))}
      </Select>
      <Select
        value={val("stage")}
        onChange={(e) => setParam("stage", e.target.value)}
        className="w-auto"
      >
        <option value="">All stages</option>
        {STAGES.map((s) => (
          <option key={s} value={s}>
            {stageLabel[s]}
          </option>
        ))}
      </Select>
      <Select
        value={val("category")}
        onChange={(e) => setParam("category", e.target.value)}
        className="w-auto"
      >
        <option value="">All categories</option>
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>
            {categoryLabel(c)}
          </option>
        ))}
      </Select>
      <Select
        value={val("priority")}
        onChange={(e) => setParam("priority", e.target.value)}
        className="w-auto"
      >
        <option value="">All priorities</option>
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {enumLabel(p)}
          </option>
        ))}
      </Select>
      <Input
        defaultValue={val("state")}
        placeholder="State"
        className="w-20"
        onKeyDown={(e) => {
          if (e.key === "Enter") setParam("state", e.currentTarget.value);
        }}
      />
      {showSdr && sdrs && (
        <Select
          value={val("sdr")}
          onChange={(e) => setParam("sdr", e.target.value)}
          className="w-auto"
        >
          <option value="">All SDRs</option>
          {sdrs.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      )}
      {vendors && (
        <Select
          value={val("vendor")}
          onChange={(e) => setParam("vendor", e.target.value)}
          className="w-auto"
        >
          <option value="">All vendors</option>
          {vendors.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </Select>
      )}
      {searchParams.toString() && (
        <button
          onClick={() => router.push(pathname)}
          className="rounded-lg px-2.5 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100"
        >
          Clear
        </button>
      )}
    </div>
  );
}
