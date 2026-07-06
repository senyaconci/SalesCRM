"use client";

import { useTransition } from "react";
import { setUserActiveAction } from "@/app/actions/users";

export function UserActiveToggle({
  id,
  isActive,
}: {
  id: string;
  isActive: boolean;
}) {
  const [isPending, startTransition] = useTransition();
  return (
    <button
      disabled={isPending}
      onClick={() =>
        startTransition(async () => {
          await setUserActiveAction(id, !isActive);
        })
      }
      className={`rounded-lg px-2.5 py-1 text-xs font-medium disabled:opacity-50 ${
        isActive
          ? "text-red-600 hover:bg-red-50"
          : "text-green-600 hover:bg-green-50"
      }`}
    >
      {isActive ? "Deactivate" : "Reactivate"}
    </button>
  );
}
