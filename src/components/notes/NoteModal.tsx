"use client";

import { useState, useTransition } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Field, Textarea } from "@/components/ui/Form";
import { createNoteAction } from "@/app/actions/notes";

export function NoteModal({
  open,
  onClose,
  projectId,
  contactId,
  contactName,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  contactId?: string;
  contactName?: string;
}) {
  const [isPending, startTransition] = useTransition();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    startTransition(async () => {
      try {
        await createNoteAction({ projectId, contactId: contactId ?? null, body });
        setBody("");
        onClose();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to add note");
      }
    });
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={contactName ? `Note — ${contactName}` : "Add Note"}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={isPending || !body.trim()}>
            {isPending ? "Saving…" : "Save Note"}
          </Button>
        </>
      }
    >
      <Field label="Note">
        <Textarea
          rows={4}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Add context, next steps, research…"
          autoFocus
        />
      </Field>
      {error && (
        <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </Modal>
  );
}
