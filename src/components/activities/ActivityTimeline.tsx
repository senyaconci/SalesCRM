import { Badge } from "@/components/ui/Badge";
import { activityTypeLabel, outcomeLabel, enumLabel } from "@/lib/labels";
import { formatDateTime } from "@/lib/format";

export interface ActivityDTO {
  id: string;
  type: string;
  direction: string;
  subject: string | null;
  body: string | null;
  outcome: string | null;
  previousStatus: string | null;
  newStatus: string | null;
  recordingUrl: string | null;
  transcript: string | null;
  createdAt: string;
  userName: string | null;
  contactName: string | null;
}

const typeTone: Record<string, "blue" | "green" | "purple" | "amber" | "slate" | "gray"> = {
  CALL: "green",
  EMAIL: "blue",
  SMS: "blue",
  NOTE: "amber",
  STATUS_CHANGE: "purple",
  ASSIGNMENT_CHANGE: "purple",
  FOLLOW_UP: "amber",
  SYSTEM: "gray",
};

export function ActivityTimeline({ activities }: { activities: ActivityDTO[] }) {
  if (activities.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white py-12 text-center text-sm text-slate-500">
        No activity logged yet.
      </div>
    );
  }

  return (
    <ol className="space-y-3">
      {activities.map((a) => (
        <li
          key={a.id}
          className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={typeTone[a.type] ?? "gray"}>
              {activityTypeLabel[a.type] ?? enumLabel(a.type)}
            </Badge>
            {a.outcome && <Badge tone="slate">{outcomeLabel[a.outcome]}</Badge>}
            {a.contactName && (
              <span className="text-sm font-medium text-slate-700">
                {a.contactName}
              </span>
            )}
            <span className="ml-auto text-xs text-slate-400">
              {formatDateTime(a.createdAt)}
            </span>
          </div>

          {a.type === "STATUS_CHANGE" && a.previousStatus && a.newStatus && (
            <p className="mt-2 text-sm text-slate-600">
              {enumLabel(a.previousStatus)} → {enumLabel(a.newStatus)}
            </p>
          )}

          {a.subject && (
            <p className="mt-2 text-sm font-medium text-slate-800">
              {a.subject}
            </p>
          )}
          {a.body && <p className="mt-1 text-sm text-slate-600">{a.body}</p>}

          {a.recordingUrl && (
            <a
              href={a.recordingUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-xs text-blue-600 hover:underline"
            >
              ▶ Recording
            </a>
          )}
          {a.transcript && (
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-slate-500">
                Transcript
              </summary>
              <p className="mt-1 whitespace-pre-wrap rounded-lg bg-slate-50 p-2 text-xs text-slate-600">
                {a.transcript}
              </p>
            </details>
          )}

          <p className="mt-2 text-xs text-slate-400">
            by {a.userName ?? "System"}
          </p>
        </li>
      ))}
    </ol>
  );
}
