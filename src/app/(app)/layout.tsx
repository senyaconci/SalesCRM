import { requireUser } from "@/lib/session";
import { getActiveWorkSession } from "@/app/actions/work-sessions";
import { Sidebar } from "@/components/layout/Sidebar";
import { UserMenu } from "@/components/layout/UserMenu";
import { WorkSessionControl } from "@/components/layout/WorkSessionControl";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireUser();
  const activeSession = await getActiveWorkSession(user.id);

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar role={user.role} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
          <div className="md:hidden text-sm font-semibold text-slate-900">
            CapEx Signal
          </div>
          <div className="flex flex-1 items-center justify-end gap-4">
            <WorkSessionControl
              activeSince={
                activeSession ? activeSession.startedAt.toISOString() : null
              }
            />
            <div className="h-6 w-px bg-slate-200" />
            <UserMenu name={user.name} role={user.role} />
          </div>
        </header>
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
