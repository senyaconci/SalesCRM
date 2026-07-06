"use client";

import { useState, useTransition } from "react";
import { ContactStatusBadge } from "@/components/ui/StatusBadges";
import { Badge } from "@/components/ui/Badge";
import { LogActivityModal } from "@/components/contacts/LogActivityModal";
import { NoteModal } from "@/components/notes/NoteModal";
import {
  ContactFormModal,
  type EditableContact,
} from "@/components/contacts/ContactFormModal";
import {
  updateContactStatusAction,
  deleteContactAction,
} from "@/app/actions/contacts";
import {
  CONTACT_STATUSES,
  contactStatusLabel,
  relevanceLabel,
} from "@/lib/labels";
import type { ContactStatus } from "@prisma/client";

export interface ContactDTO {
  id: string;
  fullName: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  mobilePhone: string | null;
  linkedinUrl: string | null;
  status: string;
  relevance: string;
  notes: string | null;
  orgName: string | null;
}

type Channel = "CALL" | "EMAIL" | "SMS";

function ActionButton({
  label,
  onClick,
  disabled,
  tone = "slate",
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: "slate" | "blue" | "green";
}) {
  const toneClass = {
    slate: "border-slate-300 text-slate-700 hover:bg-slate-50",
    blue: "border-blue-300 text-blue-700 hover:bg-blue-50",
    green: "border-green-300 text-green-700 hover:bg-green-50",
  }[tone];
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${toneClass}`}
    >
      {label}
    </button>
  );
}

export function ContactCard({
  contact,
  projectId,
  side,
  canEdit,
}: {
  contact: ContactDTO;
  projectId: string;
  side: "BUYER" | "VENDOR";
  canEdit: boolean;
}) {
  const [logChannel, setLogChannel] = useState<Channel | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  const openChannel = (channel: Channel, href: string | null) => {
    if (href && typeof window !== "undefined") {
      window.location.href = href;
    }
    setLogChannel(channel);
  };

  const editable: EditableContact = {
    id: contact.id,
    fullName: contact.fullName,
    title: contact.title,
    email: contact.email,
    phone: contact.phone,
    mobilePhone: contact.mobilePhone,
    linkedinUrl: contact.linkedinUrl,
    relevance: contact.relevance,
    notes: contact.notes,
  };

  const phoneForCall = contact.phone || contact.mobilePhone;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="truncate font-semibold text-slate-900">
              {contact.fullName}
            </h4>
            <ContactStatusBadge status={contact.status} />
          </div>
          {contact.title && (
            <p className="text-sm text-slate-600">{contact.title}</p>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Badge tone="slate">{relevanceLabel[contact.relevance]}</Badge>
            {contact.orgName && (
              <span className="text-xs text-slate-400">{contact.orgName}</span>
            )}
          </div>
        </div>
      </div>

      <dl className="mt-3 space-y-1 text-sm">
        {contact.email && (
          <div className="flex gap-2">
            <dt className="w-14 shrink-0 text-slate-400">Email</dt>
            <dd className="truncate text-slate-700">{contact.email}</dd>
          </div>
        )}
        {contact.phone && (
          <div className="flex gap-2">
            <dt className="w-14 shrink-0 text-slate-400">Phone</dt>
            <dd className="text-slate-700">{contact.phone}</dd>
          </div>
        )}
        {contact.mobilePhone && (
          <div className="flex gap-2">
            <dt className="w-14 shrink-0 text-slate-400">Mobile</dt>
            <dd className="text-slate-700">{contact.mobilePhone}</dd>
          </div>
        )}
        {contact.linkedinUrl && (
          <div className="flex gap-2">
            <dt className="w-14 shrink-0 text-slate-400">LinkedIn</dt>
            <dd className="truncate">
              <a
                href={contact.linkedinUrl}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 hover:underline"
              >
                Profile
              </a>
            </dd>
          </div>
        )}
      </dl>

      {contact.notes && (
        <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          {contact.notes}
        </p>
      )}

      {canEdit && (
        <>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <ActionButton
              label="Call"
              tone="green"
              disabled={!phoneForCall}
              onClick={() =>
                openChannel("CALL", phoneForCall ? `tel:${phoneForCall}` : null)
              }
            />
            <ActionButton
              label="Email"
              tone="blue"
              disabled={!contact.email}
              onClick={() =>
                openChannel(
                  "EMAIL",
                  contact.email ? `mailto:${contact.email}` : null
                )
              }
            />
            <ActionButton
              label="SMS"
              disabled={!phoneForCall}
              onClick={() =>
                openChannel("SMS", phoneForCall ? `sms:${phoneForCall}` : null)
              }
            />
            <ActionButton label="Note" onClick={() => setNoteOpen(true)} />
            <ActionButton label="Edit" onClick={() => setEditOpen(true)} />
          </div>

          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-slate-400">Status</span>
            <select
              disabled={isPending}
              value={contact.status}
              onChange={(e) =>
                startTransition(async () => {
                  await updateContactStatusAction(
                    contact.id,
                    e.target.value as ContactStatus
                  );
                })
              }
              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 focus:border-blue-500 focus:outline-none"
            >
              {CONTACT_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {contactStatusLabel[s]}
                </option>
              ))}
            </select>
            <button
              onClick={() => {
                if (confirm(`Delete contact ${contact.fullName}?`)) {
                  startTransition(async () => {
                    await deleteContactAction(contact.id);
                  });
                }
              }}
              className="ml-auto text-xs text-slate-400 hover:text-red-600"
            >
              Delete
            </button>
          </div>
        </>
      )}

      {logChannel && (
        <LogActivityModal
          open={!!logChannel}
          onClose={() => setLogChannel(null)}
          projectId={projectId}
          contactId={contact.id}
          contactName={contact.fullName}
          channel={logChannel}
        />
      )}
      <NoteModal
        open={noteOpen}
        onClose={() => setNoteOpen(false)}
        projectId={projectId}
        contactId={contact.id}
        contactName={contact.fullName}
      />
      <ContactFormModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        projectId={projectId}
        side={side}
        contact={editable}
      />
    </div>
  );
}
