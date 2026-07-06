"use client";

import { useState } from "react";

export interface TabDef {
  key: string;
  label: string;
  count?: number;
  content: React.ReactNode;
}

export function ProjectTabs({ tabs }: { tabs: TabDef[] }) {
  const [active, setActive] = useState(tabs[0]?.key);

  return (
    <div>
      <div className="flex flex-wrap gap-1 border-b border-slate-200">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              active === t.key
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.label}
            {typeof t.count === "number" && (
              <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="pt-5">
        {tabs.map((t) => (
          <div key={t.key} className={active === t.key ? "block" : "hidden"}>
            {t.content}
          </div>
        ))}
      </div>
    </div>
  );
}
