"use client";

import { useEffect, useState, useTransition } from "react";
import {
  startWorkSessionAction,
  stopWorkSessionAction,
} from "@/app/actions/work-sessions";

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

export function WorkSessionControl({
  activeSince,
}: {
  activeSince: string | null;
}) {
  const [isPending, startTransition] = useTransition();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!activeSince) return;
    const start = new Date(activeSince).getTime();
    const tick = () =>
      setElapsed(Math.max(0, Math.round((Date.now() - start) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [activeSince]);

  const active = !!activeSince;

  return (
    <div className="flex items-center gap-2">
      {active && (
        <span className="hidden font-mono text-sm tabular-nums text-slate-600 sm:inline">
          {formatDuration(elapsed)}
        </span>
      )}
      <button
        disabled={isPending}
        onClick={() =>
          startTransition(async () => {
            if (active) {
              await stopWorkSessionAction();
            } else {
              await startWorkSessionAction();
            }
          })
        }
        className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-60 ${
          active
            ? "bg-red-50 text-red-700 hover:bg-red-100"
            : "bg-green-600 text-white hover:bg-green-700"
        }`}
      >
        <span
          className={`h-2 w-2 rounded-full ${
            active ? "animate-pulse bg-red-500" : "bg-white"
          }`}
        />
        {active ? "Stop Work" : "Start Work"}
      </button>
    </div>
  );
}
