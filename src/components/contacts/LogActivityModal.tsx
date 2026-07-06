"use client";

import { useState, useTransition } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Field, Select, Textarea, Input, EnumOptions } from "@/components/ui/Form";
import { logActivityAction } from "@/app/actions/activities";
import {
  CALL_OUTCOMES,
  CONTACT_STATUSES,
  contactStatusLabel,
  outcomeLabel,
} from "@/lib/labels";
import type {
  ActivityType,
  ActivityOutcome,
  ContactStatus,
} from "@prisma/client";

type Channel = "CALL" | "EMAIL" | "SMS";

const channelTitle: Record<Channel, string> = {
  CALL: "Log Call",
  EMAIL: "Log Email",
  SMS: "Log SMS",
};

const channelOutcomes: Record<Channel, string[]> = {
  CALL: CALL_OUTCOMES,
  EMAIL: ["SENT", "REPLIED", "BOUNCED", "INTERESTED", "NOT_INTERESTED", "OTHER"],
  SMS: ["SENT", "REPLIED", "INTERESTED", "NOT_INTERESTED", "OTHER"],
};

export function LogActivityModal({
  open,
  onClose,
  projectId,
  contactId,
  contactName,
  channel,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  contactId: string;
  contactName: string;
  channel: Channel;
}) {
  const [isPending, startTransition] = useTransition();
  const [outcome, setOutcome] = useState<string>(channelOutcomes[channel][0]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [relevantValidation, setRelevantValidation] = useState(false);
  const [contactStatusOverride, setContactStatusOverride] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    startTransition(async () => {
      try {
        await logActivityAction({
          projectId,
          contactId,
          type: channel as ActivityType,
          direction: "OUTBOUND",
          subject: channel === "EMAIL" ? subject || undefined : undefined,
          body: body || undefined,
          outcome: outcome as ActivityOutcome,
          relevantValidation,
          contactStatusOverride: contactStatusOverride
            ? (contactStatusOverride as ContactStatus)
            : null,
        });
        onClose();
        setBody("");
        setSubject("");
        setContactStatusOverride("");
        setRelevantValidation(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to log activity");
      }
    });
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${channelTitle[channel]} — ${contactName}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={isPending}>
            {isPending ? "Saving…" : "Save Activity"}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Outcome">
          <Select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            <EnumOptions values={channelOutcomes[channel]} labels={outcomeLabel} />
          </Select>
        </Field>

        {outcome === "INTERESTED" && (
          <label className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800">
            <input
              type="checkbox"
              checked={relevantValidation}
              onChange={(e) => setRelevantValidation(e.target.checked)}
            />
            Mark project as Validated — Relevant (otherwise Validating)
          </label>
        )}

        {channel === "EMAIL" && (
          <Field label="Subject">
            <Input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Email subject"
            />
          </Field>
        )}

        <Field label="Notes / summary">
          <Textarea
            rows={3}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="What happened on this touch?"
          />
        </Field>

        <Field label="Also set contact status (optional)">
          <Select
            value={contactStatusOverride}
            onChange={(e) => setContactStatusOverride(e.target.value)}
          >
            <option value="">Auto (based on outcome)</option>
            <EnumOptions values={CONTACT_STATUSES} labels={contactStatusLabel} />
          </Select>
        </Field>

        {outcome === "REFERRED" && (
          <p className="rounded-lg bg-purple-50 px-3 py-2 text-xs text-purple-700">
            Tip: this contact referred you to someone else — add the referred
            person as a new contact.
          </p>
        )}

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
