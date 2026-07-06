import { badgeToneClass, type BadgeTone } from "@/lib/labels";

export function Badge({
  children,
  tone = "gray",
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${badgeToneClass[tone]}`}
    >
      {children}
    </span>
  );
}
