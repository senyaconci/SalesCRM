"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ContactCard, type ContactDTO } from "@/components/contacts/ContactCard";
import { ContactFormModal } from "@/components/contacts/ContactFormModal";

export function ContactsSection({
  contacts,
  projectId,
  side,
  canEdit,
}: {
  contacts: ContactDTO[];
  projectId: string;
  side: "BUYER" | "VENDOR";
  canEdit: boolean;
}) {
  const [addOpen, setAddOpen] = useState(false);
  const label = side === "BUYER" ? "Buyer" : "Vendor";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          {contacts.length} {label.toLowerCase()}-side contact
          {contacts.length === 1 ? "" : "s"}
        </p>
        {canEdit && (
          <Button size="sm" onClick={() => setAddOpen(true)}>
            + Add {label} Contact
          </Button>
        )}
      </div>

      {contacts.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white py-12 text-center text-sm text-slate-500">
          No {label.toLowerCase()}-side contacts yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {contacts.map((c) => (
            <ContactCard
              key={c.id}
              contact={c}
              projectId={projectId}
              side={side}
              canEdit={canEdit}
            />
          ))}
        </div>
      )}

      <ContactFormModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        projectId={projectId}
        side={side}
      />
    </div>
  );
}
