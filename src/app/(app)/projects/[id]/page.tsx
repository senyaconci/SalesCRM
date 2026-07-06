import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { canViewProject, canEditProject, canAssignProjects } from "@/lib/permissions";
import { PdfViewer } from "@/components/projects/PdfViewer";
import { ProjectSidePanel } from "@/components/projects/ProjectSidePanel";
import { ProjectTabs, type TabDef } from "@/components/projects/ProjectTabs";
import { ContactsSection } from "@/components/contacts/ContactsSection";
import { ActivityTimeline } from "@/components/activities/ActivityTimeline";
import { NotesSection } from "@/components/notes/NotesSection";
import { ProjectDataForm } from "@/components/projects/ProjectDataForm";
import {
  ProjectStatusBadge,
  StageBadge,
  PriorityBadge,
} from "@/components/ui/StatusBadges";
import { categoryLabel } from "@/lib/labels";

export const dynamic = "force-dynamic";

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await requireUser();

  const project = await prisma.project.findUnique({
    where: { id },
    include: {
      vendorCustomer: true,
      ownerOrganization: true,
      assignedSdr: { select: { id: true, name: true } },
      contacts: { orderBy: { createdAt: "asc" } },
      notes: {
        orderBy: { createdAt: "desc" },
        include: {
          user: { select: { name: true } },
          contact: { select: { fullName: true } },
        },
      },
      activities: {
        orderBy: { createdAt: "desc" },
        include: {
          user: { select: { name: true } },
          contact: { select: { fullName: true } },
        },
      },
    },
  });

  if (!project) notFound();
  if (!canViewProject(user, project)) notFound();

  const canEdit = canEditProject(user, project);
  const canAssign = canAssignProjects(user);

  const [sdrs, vendors, organizations] = await Promise.all([
    prisma.user.findMany({
      where: { role: "SDR", isActive: true },
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.vendorCustomer.findMany({
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.ownerOrganization.findMany({
      select: { id: true, name: true },
      orderBy: { name: "asc" },
    }),
  ]);

  const buyerContacts = project.contacts
    .filter((c) => c.side === "BUYER")
    .map((c) => ({
      id: c.id,
      fullName: c.fullName,
      title: c.title,
      email: c.email,
      phone: c.phone,
      mobilePhone: c.mobilePhone,
      linkedinUrl: c.linkedinUrl,
      status: c.status,
      relevance: c.relevance,
      notes: c.notes,
      orgName: project.ownerOrganization?.name ?? null,
    }));

  const vendorContacts = project.contacts
    .filter((c) => c.side === "VENDOR")
    .map((c) => ({
      id: c.id,
      fullName: c.fullName,
      title: c.title,
      email: c.email,
      phone: c.phone,
      mobilePhone: c.mobilePhone,
      linkedinUrl: c.linkedinUrl,
      status: c.status,
      relevance: c.relevance,
      notes: c.notes,
      orgName: project.vendorCustomer?.name ?? null,
    }));

  const activities = project.activities.map((a) => ({
    id: a.id,
    type: a.type,
    direction: a.direction,
    subject: a.subject,
    body: a.body,
    outcome: a.outcome,
    previousStatus: a.previousStatus,
    newStatus: a.newStatus,
    recordingUrl: a.recordingUrl,
    transcript: a.transcript,
    createdAt: a.createdAt.toISOString(),
    userName: a.user?.name ?? null,
    contactName: a.contact?.fullName ?? null,
  }));

  const notes = project.notes.map((n) => ({
    id: n.id,
    body: n.body,
    createdAt: n.createdAt.toISOString(),
    userName: n.user?.name ?? null,
    contactName: n.contact?.fullName ?? null,
  }));

  const tabs: TabDef[] = [
    {
      key: "buyer",
      label: "Buyer Contacts",
      count: buyerContacts.length,
      content: (
        <ContactsSection
          contacts={buyerContacts}
          projectId={project.id}
          side="BUYER"
          canEdit={canEdit}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor Contacts",
      count: vendorContacts.length,
      content: (
        <ContactsSection
          contacts={vendorContacts}
          projectId={project.id}
          side="VENDOR"
          canEdit={canEdit}
        />
      ),
    },
    {
      key: "activities",
      label: "Activities",
      count: activities.length,
      content: <ActivityTimeline activities={activities} />,
    },
    {
      key: "notes",
      label: "Notes",
      count: notes.length,
      content: (
        <NotesSection notes={notes} projectId={project.id} canEdit={canEdit} />
      ),
    },
    {
      key: "data",
      label: "Project Data",
      content: (
        <ProjectDataForm
          project={{
            id: project.id,
            title: project.title,
            summary: project.summary,
            description: project.description,
            evidenceText: project.evidenceText,
            sourceUrl: project.sourceUrl,
            category: project.category,
            stage: project.stage,
            status: project.status,
            priority: project.priority,
            budgetAmount: project.budgetAmount?.toString() ?? null,
            budgetText: project.budgetText,
            ownerOrganizationId: project.ownerOrganizationId,
            vendorCustomerId: project.vendorCustomerId,
            nextFollowUpAt: project.nextFollowUpAt?.toISOString() ?? null,
          }}
          vendors={vendors}
          organizations={organizations}
          canEdit={canEdit}
        />
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <div>
        <Link
          href={user.role === "SDR" ? "/my-projects" : "/projects"}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          ← Back to projects
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold text-slate-900">{project.title}</h1>
          <ProjectStatusBadge status={project.status} />
          <PriorityBadge priority={project.priority} />
          <StageBadge stage={project.stage} />
          <span className="text-sm text-slate-500">
            {categoryLabel(project.category)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Left: PDF + evidence */}
        <div className="space-y-4 lg:col-span-2">
          <PdfViewer
            pdfUrl={project.pdfUrl}
            pdfFileName={project.pdfFileName}
            projectId={project.id}
            canEdit={canEdit}
          />
          {(project.summary || project.evidenceText || project.sourceUrl) && (
            <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              {project.summary && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Summary
                  </h3>
                  <p className="mt-1 text-sm text-slate-600">
                    {project.summary}
                  </p>
                </div>
              )}
              {project.evidenceText && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Why this is relevant
                  </h3>
                  <p className="mt-1 text-sm text-slate-600">
                    {project.evidenceText}
                  </p>
                </div>
              )}
              {project.sourceUrl && (
                <a
                  href={project.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block text-sm text-blue-600 hover:underline"
                >
                  View source ↗
                </a>
              )}
            </div>
          )}
        </div>

        {/* Right: meta panel */}
        <div className="lg:col-span-1">
          <ProjectSidePanel
            project={{
              id: project.id,
              status: project.status,
              stage: project.stage,
              priority: project.priority,
              budgetAmount: project.budgetAmount?.toString() ?? null,
              budgetText: project.budgetText,
              locationCity: project.locationCity,
              locationState: project.locationState,
              nextFollowUpAt: project.nextFollowUpAt?.toISOString() ?? null,
              assignedSdrId: project.assignedSdrId,
              assignedSdrName: project.assignedSdr?.name ?? null,
              vendorName: project.vendorCustomer?.name ?? null,
              ownerName: project.ownerOrganization?.name ?? null,
            }}
            sdrs={sdrs}
            canEdit={canEdit}
            canAssign={canAssign}
          />
        </div>
      </div>

      <ProjectTabs tabs={tabs} />
    </div>
  );
}
