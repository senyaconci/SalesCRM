"use client";

import { useState, useTransition } from "react";
import { uploadProjectPdfAction } from "@/app/actions/projects";

export function PdfViewer({
  pdfUrl,
  pdfFileName,
  projectId,
  canEdit,
}: {
  pdfUrl: string | null;
  pdfFileName: string | null;
  projectId: string;
  canEdit: boolean;
}) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const onUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    const fd = new FormData();
    fd.set("projectId", projectId);
    fd.set("pdf", file);
    startTransition(async () => {
      try {
        await uploadProjectPdfAction(fd);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      }
    });
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <h3 className="text-sm font-semibold text-slate-900">Project Report</h3>
        <div className="flex items-center gap-3">
          {pdfUrl && (
            <a
              href={pdfUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-medium text-blue-600 hover:underline"
            >
              Open in new tab ↗
            </a>
          )}
          {canEdit && (
            <label className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-700">
              {isPending ? "Uploading…" : pdfUrl ? "Replace" : "Upload PDF"}
              <input
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={onUpload}
                disabled={isPending}
              />
            </label>
          )}
        </div>
      </div>
      {error && (
        <p className="border-b border-red-100 bg-red-50 px-4 py-2 text-xs text-red-700">
          {error}
        </p>
      )}
      {pdfUrl ? (
        <object
          data={pdfUrl}
          type="application/pdf"
          className="h-[520px] w-full"
        >
          <div className="p-6 text-sm text-slate-500">
            Unable to display PDF inline.{" "}
            <a href={pdfUrl} className="text-blue-600 hover:underline">
              Download {pdfFileName ?? "file"}
            </a>
          </div>
        </object>
      ) : (
        <div className="flex h-64 items-center justify-center text-sm text-slate-400">
          No PDF uploaded
        </div>
      )}
    </div>
  );
}
