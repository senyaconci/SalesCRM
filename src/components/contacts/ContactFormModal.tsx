"use client";

import { useState, useTransition } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea, EnumOptions } from "@/components/ui/Form";
import {
  createContactAction,
  updateContactAction,
  type ContactInput,
} from "@/app/actions/contacts";
import { RELEVANCES, relevanceLabel } from "@/lib/labels";
import type { ContactRelevance, ContactSide } from "@prisma/client";

export interface EditableContact {
  id: string;
  fullName: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  mobilePhone: string | null;
  linkedinUrl: string | null;
  relevance: string;
  notes: string | null;
}

export function ContactFormModal({
  open,
  onClose,
  projectId,
  side,
  contact,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  side: ContactSide;
  contact?: EditableContact;
}) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    fullName: contact?.fullName ?? "",
    title: contact?.title ?? "",
    email: contact?.email ?? "",
    phone: contact?.phone ?? "",
    mobilePhone: contact?.mobilePhone ?? "",
    linkedinUrl: contact?.linkedinUrl ?? "",
    relevance: contact?.relevance ?? "UNKNOWN",
    notes: contact?.notes ?? "",
  });

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = () => {
    setError(null);
    startTransition(async () => {
      try {
        const payload: Partial<ContactInput> = {
          fullName: form.fullName,
          title: form.title,
          email: form.email,
          phone: form.phone,
          mobilePhone: form.mobilePhone,
          linkedinUrl: form.linkedinUrl,
          relevance: form.relevance as ContactRelevance,
          notes: form.notes,
        };
        if (contact) {
          await updateContactAction(contact.id, payload);
        } else {
          await createContactAction({
            ...(payload as ContactInput),
            projectId,
            side,
          });
        }
        onClose();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to save contact");
      }
    });
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={
        contact
          ? "Edit Contact"
          : `Add ${side === "BUYER" ? "Buyer" : "Vendor"} Contact`
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={isPending || !form.fullName.trim()}>
            {isPending ? "Saving…" : "Save"}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <Field label="Full name" required>
            <Input value={form.fullName} onChange={set("fullName")} />
          </Field>
        </div>
        <div className="col-span-2">
          <Field label="Title">
            <Input value={form.title} onChange={set("title")} />
          </Field>
        </div>
        <Field label="Email">
          <Input type="email" value={form.email} onChange={set("email")} />
        </Field>
        <Field label="Relevance">
          <Select value={form.relevance} onChange={set("relevance")}>
            <EnumOptions values={RELEVANCES} labels={relevanceLabel} />
          </Select>
        </Field>
        <Field label="Phone">
          <Input value={form.phone} onChange={set("phone")} />
        </Field>
        <Field label="Mobile">
          <Input value={form.mobilePhone} onChange={set("mobilePhone")} />
        </Field>
        <div className="col-span-2">
          <Field label="LinkedIn URL">
            <Input value={form.linkedinUrl} onChange={set("linkedinUrl")} />
          </Field>
        </div>
        <div className="col-span-2">
          <Field label="Notes">
            <Textarea rows={2} value={form.notes} onChange={set("notes")} />
          </Field>
        </div>
      </div>
      {error && (
        <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </Modal>
  );
}
