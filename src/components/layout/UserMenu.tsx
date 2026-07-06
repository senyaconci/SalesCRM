import { signOutAction } from "@/app/actions/auth";
import { enumLabel } from "@/lib/labels";

export function UserMenu({
  name,
  role,
}: {
  name?: string | null;
  role: string;
}) {
  const initials = (name ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="flex items-center gap-3">
      <div className="hidden text-right sm:block">
        <div className="text-sm font-medium text-slate-800">{name}</div>
        <div className="text-xs text-slate-500">{enumLabel(role)}</div>
      </div>
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700">
        {initials}
      </div>
      <form action={signOutAction}>
        <button
          type="submit"
          className="rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Sign out
        </button>
      </form>
    </div>
  );
}
