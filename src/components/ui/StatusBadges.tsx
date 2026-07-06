import { Badge } from "@/components/ui/Badge";
import {
  contactStatusLabel,
  contactStatusTone,
  priorityTone,
  projectStatusLabel,
  projectStatusTone,
  stageLabel,
  enumLabel,
} from "@/lib/labels";

export function ProjectStatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={projectStatusTone[status] ?? "gray"}>
      {projectStatusLabel[status] ?? enumLabel(status)}
    </Badge>
  );
}

export function ContactStatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={contactStatusTone[status] ?? "gray"}>
      {contactStatusLabel[status] ?? enumLabel(status)}
    </Badge>
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  return <Badge tone={priorityTone[priority] ?? "gray"}>{enumLabel(priority)}</Badge>;
}

export function StageBadge({ stage }: { stage: string }) {
  return <Badge tone="slate">{stageLabel[stage] ?? enumLabel(stage)}</Badge>;
}
