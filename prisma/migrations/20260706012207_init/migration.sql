-- CreateEnum
CREATE TYPE "Role" AS ENUM ('ADMIN', 'MANAGER', 'SDR');

-- CreateEnum
CREATE TYPE "OwnerOrgType" AS ENUM ('HOSPITAL', 'UNIVERSITY', 'COLLEGE', 'SCHOOL_DISTRICT', 'HIGH_SCHOOL', 'CITY', 'COUNTY', 'STATE_AGENCY', 'AIRPORT', 'WATER_DISTRICT', 'OTHER');

-- CreateEnum
CREATE TYPE "ProjectCategory" AS ENUM ('BOILERS', 'STEAM', 'THERMAL_PLANT', 'WATER', 'WASTEWATER', 'ELECTRICAL', 'HVAC', 'OTHER');

-- CreateEnum
CREATE TYPE "ProjectStage" AS ENUM ('IDENTIFIED', 'PROPOSED', 'PLANNING', 'FUNDED', 'DESIGN', 'PRE_RFP', 'RFP', 'CONSTRUCTION', 'CLOSED', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "ProjectStatus" AS ENUM ('NEW', 'ASSIGNED', 'OUTREACH_STARTED', 'CONTACTED', 'VALIDATING', 'VALIDATED_RELEVANT', 'VALIDATED_NOT_RELEVANT', 'INTRO_REQUESTED', 'INTRO_MADE', 'CUSTOMER_REVIEWING', 'FOLLOW_UP_LATER', 'CLOSED_WON', 'CLOSED_LOST', 'DEAD');

-- CreateEnum
CREATE TYPE "Priority" AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'URGENT');

-- CreateEnum
CREATE TYPE "ContactSide" AS ENUM ('BUYER', 'VENDOR', 'INTERNAL', 'OTHER');

-- CreateEnum
CREATE TYPE "ContactStatus" AS ENUM ('NOT_CONTACTED', 'CALL_ATTEMPTED', 'LEFT_VOICEMAIL', 'EMAIL_SENT', 'SMS_SENT', 'REPLIED', 'CONNECTED', 'WRONG_PERSON', 'REFERRED', 'INTERESTED', 'NOT_INTERESTED', 'DO_NOT_CONTACT', 'INVALID');

-- CreateEnum
CREATE TYPE "ContactRelevance" AS ENUM ('PRIMARY_DECISION_MAKER', 'INFLUENCER', 'PROCUREMENT', 'FACILITIES', 'ENGINEERING', 'ADMIN', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "ActivityType" AS ENUM ('CALL', 'EMAIL', 'SMS', 'NOTE', 'STATUS_CHANGE', 'ASSIGNMENT_CHANGE', 'FOLLOW_UP', 'SYSTEM');

-- CreateEnum
CREATE TYPE "ActivityDirection" AS ENUM ('OUTBOUND', 'INBOUND', 'INTERNAL');

-- CreateEnum
CREATE TYPE "ActivityOutcome" AS ENUM ('NO_ANSWER', 'LEFT_VOICEMAIL', 'CONNECTED', 'SENT', 'REPLIED', 'BOUNCED', 'WRONG_PERSON', 'REFERRED', 'INTERESTED', 'NOT_INTERESTED', 'OTHER');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT,
    "role" "Role" NOT NULL DEFAULT 'SDR',
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "VendorCustomer" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "website" TEXT,
    "description" TEXT,
    "targetGeography" TEXT,
    "targetProjectTypes" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "VendorCustomer_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "OwnerOrganization" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" "OwnerOrgType" NOT NULL DEFAULT 'OTHER',
    "website" TEXT,
    "state" TEXT,
    "city" TEXT,
    "address" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "OwnerOrganization_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Project" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "summary" TEXT,
    "category" "ProjectCategory" NOT NULL DEFAULT 'OTHER',
    "stage" "ProjectStage" NOT NULL DEFAULT 'UNKNOWN',
    "status" "ProjectStatus" NOT NULL DEFAULT 'NEW',
    "priority" "Priority" NOT NULL DEFAULT 'MEDIUM',
    "budgetAmount" DECIMAL(65,30),
    "budgetText" TEXT,
    "locationCity" TEXT,
    "locationState" TEXT,
    "sourceUrl" TEXT,
    "evidenceText" TEXT,
    "pdfUrl" TEXT,
    "pdfFileName" TEXT,
    "ownerOrganizationId" TEXT,
    "vendorCustomerId" TEXT,
    "assignedSdrId" TEXT,
    "projectOwnerId" TEXT,
    "nextFollowUpAt" TIMESTAMP(3),
    "lastActivityAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Project_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Contact" (
    "id" TEXT NOT NULL,
    "projectId" TEXT NOT NULL,
    "organizationId" TEXT,
    "vendorCustomerId" TEXT,
    "side" "ContactSide" NOT NULL DEFAULT 'BUYER',
    "firstName" TEXT,
    "lastName" TEXT,
    "fullName" TEXT NOT NULL,
    "title" TEXT,
    "email" TEXT,
    "phone" TEXT,
    "mobilePhone" TEXT,
    "linkedinUrl" TEXT,
    "source" TEXT,
    "status" "ContactStatus" NOT NULL DEFAULT 'NOT_CONTACTED',
    "relevance" "ContactRelevance" NOT NULL DEFAULT 'UNKNOWN',
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Contact_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Activity" (
    "id" TEXT NOT NULL,
    "projectId" TEXT NOT NULL,
    "contactId" TEXT,
    "userId" TEXT,
    "type" "ActivityType" NOT NULL,
    "direction" "ActivityDirection" NOT NULL DEFAULT 'OUTBOUND',
    "subject" TEXT,
    "body" TEXT,
    "outcome" "ActivityOutcome",
    "previousStatus" TEXT,
    "newStatus" TEXT,
    "recordingUrl" TEXT,
    "transcript" TEXT,
    "externalProvider" TEXT,
    "externalId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Activity_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Note" (
    "id" TEXT NOT NULL,
    "projectId" TEXT NOT NULL,
    "contactId" TEXT,
    "userId" TEXT,
    "body" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Note_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "WorkSession" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "endedAt" TIMESTAMP(3),
    "durationSeconds" INTEGER,
    "notes" TEXT,

    CONSTRAINT "WorkSession_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ProjectAssignmentHistory" (
    "id" TEXT NOT NULL,
    "projectId" TEXT NOT NULL,
    "assignedToId" TEXT,
    "assignedById" TEXT,
    "previousAssignedToId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ProjectAssignmentHistory_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "Project_status_idx" ON "Project"("status");

-- CreateIndex
CREATE INDEX "Project_stage_idx" ON "Project"("stage");

-- CreateIndex
CREATE INDEX "Project_assignedSdrId_idx" ON "Project"("assignedSdrId");

-- CreateIndex
CREATE INDEX "Project_vendorCustomerId_idx" ON "Project"("vendorCustomerId");

-- CreateIndex
CREATE INDEX "Project_ownerOrganizationId_idx" ON "Project"("ownerOrganizationId");

-- CreateIndex
CREATE INDEX "Contact_projectId_idx" ON "Contact"("projectId");

-- CreateIndex
CREATE INDEX "Contact_side_idx" ON "Contact"("side");

-- CreateIndex
CREATE INDEX "Activity_projectId_idx" ON "Activity"("projectId");

-- CreateIndex
CREATE INDEX "Activity_contactId_idx" ON "Activity"("contactId");

-- CreateIndex
CREATE INDEX "Activity_createdAt_idx" ON "Activity"("createdAt");

-- CreateIndex
CREATE INDEX "Note_projectId_idx" ON "Note"("projectId");

-- CreateIndex
CREATE INDEX "WorkSession_userId_idx" ON "WorkSession"("userId");

-- CreateIndex
CREATE INDEX "ProjectAssignmentHistory_projectId_idx" ON "ProjectAssignmentHistory"("projectId");

-- AddForeignKey
ALTER TABLE "Project" ADD CONSTRAINT "Project_ownerOrganizationId_fkey" FOREIGN KEY ("ownerOrganizationId") REFERENCES "OwnerOrganization"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Project" ADD CONSTRAINT "Project_vendorCustomerId_fkey" FOREIGN KEY ("vendorCustomerId") REFERENCES "VendorCustomer"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Project" ADD CONSTRAINT "Project_assignedSdrId_fkey" FOREIGN KEY ("assignedSdrId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Project" ADD CONSTRAINT "Project_projectOwnerId_fkey" FOREIGN KEY ("projectOwnerId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Contact" ADD CONSTRAINT "Contact_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Contact" ADD CONSTRAINT "Contact_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "OwnerOrganization"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Contact" ADD CONSTRAINT "Contact_vendorCustomerId_fkey" FOREIGN KEY ("vendorCustomerId") REFERENCES "VendorCustomer"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Activity" ADD CONSTRAINT "Activity_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Activity" ADD CONSTRAINT "Activity_contactId_fkey" FOREIGN KEY ("contactId") REFERENCES "Contact"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Activity" ADD CONSTRAINT "Activity_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Note" ADD CONSTRAINT "Note_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Note" ADD CONSTRAINT "Note_contactId_fkey" FOREIGN KEY ("contactId") REFERENCES "Contact"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Note" ADD CONSTRAINT "Note_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "WorkSession" ADD CONSTRAINT "WorkSession_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ProjectAssignmentHistory" ADD CONSTRAINT "ProjectAssignmentHistory_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ProjectAssignmentHistory" ADD CONSTRAINT "ProjectAssignmentHistory_assignedToId_fkey" FOREIGN KEY ("assignedToId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ProjectAssignmentHistory" ADD CONSTRAINT "ProjectAssignmentHistory_assignedById_fkey" FOREIGN KEY ("assignedById") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;
