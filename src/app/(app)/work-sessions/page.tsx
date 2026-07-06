import { requireUser } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { isAdminOrManager } from "@/lib/session";
import { formatDateTime, formatSeconds } from "@/lib/format";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";

export const dynamic = "force-dynamic";

export default async function WorkSessionsPage() {
  const user = await requireUser();
  const teamView = isAdminOrManager(user);

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);

  const sessions = await prisma.workSession.findMany({
    where: teamView ? {} : { userId: user.id },
    include: { user: { select: { id: true, name: true } } },
    orderBy: { startedAt: "desc" },
    take: 100,
  });

  // Today's per-user totals (work time, and touch counts).
  const todaysSessions = sessions.filter((s) => s.startedAt >= startOfToday);
  const totalsByUser = new Map<
    string,
    { name: string; seconds: number }
  >();
  for (const s of todaysSessions) {
    const cur = totalsByUser.get(s.user.id) ?? {
      name: s.user.name,
      seconds: 0,
    };
    const seconds =
      s.durationSeconds ??
      Math.round((Date.now() - s.startedAt.getTime()) / 1000);
    cur.seconds += seconds;
    totalsByUser.set(s.user.id, cur);
  }

  const activityCounts = await prisma.activity.groupBy({
    by: ["userId", "type"],
    where: {
      createdAt: { gte: startOfToday },
      userId: teamView ? undefined : user.id,
      type: { in: ["CALL", "EMAIL", "SMS"] },
    },
    _count: true,
  });

  const touchesByUser = new Map<string, { CALL: number; EMAIL: number; SMS: number }>();
  for (const row of activityCounts) {
    if (!row.userId) continue;
    const cur = touchesByUser.get(row.userId) ?? { CALL: 0, EMAIL: 0, SMS: 0 };
    cur[row.type as "CALL" | "EMAIL" | "SMS"] = row._count;
    touchesByUser.set(row.userId, cur);
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Work Sessions</h1>
        <p className="text-sm text-slate-500">
          {teamView
            ? "Team work time and outreach activity today."
            : "Your work sessions."}
        </p>
      </div>

      {teamView && (
        <Card>
          <CardHeader title="Today" subtitle="Work time & logged touches" />
          <CardBody className="p-0">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2">SDR</th>
                  <th className="px-4 py-2">Work time</th>
                  <th className="px-4 py-2">Calls</th>
                  <th className="px-4 py-2">Emails</th>
                  <th className="px-4 py-2">SMS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {[...totalsByUser.entries()].length === 0 && (
                  <tr>
                    <td className="px-4 py-3 text-slate-400" colSpan={5}>
                      No work sessions today.
                    </td>
                  </tr>
                )}
                {[...totalsByUser.entries()].map(([uid, t]) => {
                  const touches = touchesByUser.get(uid) ?? {
                    CALL: 0,
                    EMAIL: 0,
                    SMS: 0,
                  };
                  return (
                    <tr key={uid}>
                      <td className="px-4 py-2 font-medium text-slate-800">
                        {t.name}
                      </td>
                      <td className="px-4 py-2">{formatSeconds(t.seconds)}</td>
                      <td className="px-4 py-2">{touches.CALL}</td>
                      <td className="px-4 py-2">{touches.EMAIL}</td>
                      <td className="px-4 py-2">{touches.SMS}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="Recent sessions" />
        <CardBody className="p-0">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                {teamView && <th className="px-4 py-2">SDR</th>}
                <th className="px-4 py-2">Started</th>
                <th className="px-4 py-2">Ended</th>
                <th className="px-4 py-2">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sessions.length === 0 && (
                <tr>
                  <td
                    className="px-4 py-3 text-slate-400"
                    colSpan={teamView ? 4 : 3}
                  >
                    No work sessions yet.
                  </td>
                </tr>
              )}
              {sessions.map((s) => (
                <tr key={s.id}>
                  {teamView && (
                    <td className="px-4 py-2 font-medium text-slate-800">
                      {s.user.name}
                    </td>
                  )}
                  <td className="px-4 py-2 text-slate-600">
                    {formatDateTime(s.startedAt)}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {s.endedAt ? (
                      formatDateTime(s.endedAt)
                    ) : (
                      <span className="text-green-600">Active</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {s.durationSeconds
                      ? formatSeconds(s.durationSeconds)
                      : s.endedAt
                        ? "—"
                        : "in progress"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}
