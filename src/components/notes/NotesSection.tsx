"use client";

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Form";
import { createNoteAction, deleteNoteAction } from "@/app/actions/notes";
import { formatDateTime } from "@/lib/format";

export interface NoteDTO {
  id: string;
  body: string;
  createdAt: string;
  userName: string | null;
  contactName: string | null;
}

export function NotesSection({
  notes,
  projectId,
  canEdit,
}: {
  notes: NoteDTO[];
  projectId: string;
  canEdit: boolean;
}) {
  const [body, setBody] = useState("");
  const [isPending, startTransition] = useTransition();

  const add = () => {
    if (!body.trim()) return;
    startTransition(async () => {
      await createNoteAction({ projectId, body });
      setBody("");
    });
  };

  return (
    <div className="space-y-4">
      {canEdit && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <Textarea
            rows={3}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Add a general project note…"
          />
          <div className="mt-2 flex justify-end">
            <Button size="sm" onClick={add} disabled={isPending || !body.trim()}>
              {isPending ? "Saving…" : "Add Note"}
            </Button>
          </div>
        </div>
      )}

      {notes.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white py-12 text-center text-sm text-slate-500">
          No notes yet.
        </div>
      ) : (
        <ul className="space-y-3">
          {notes.map((n) => (
            <li
              key={n.id}
              className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <p className="whitespace-pre-wrap text-sm text-slate-700">
                {n.body}
              </p>
              <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
                <span>{n.userName ?? "Unknown"}</span>
                <span>·</span>
                <span>{formatDateTime(n.createdAt)}</span>
                {n.contactName && (
                  <>
                    <span>·</span>
                    <span>re: {n.contactName}</span>
                  </>
                )}
                {canEdit && (
                  <button
                    onClick={() =>
                      startTransition(async () => {
                        await deleteNoteAction(n.id);
                      })
                    }
                    className="ml-auto hover:text-red-600"
                  >
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
