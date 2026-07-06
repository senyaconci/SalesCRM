# CapEx Signal CRM

A project-based outreach CRM for **CapEx Signal**. The core object is a **public
capital project ticket** — each ticket is built around a CapEx Signal PDF/report
and is used by SDRs to call, email, SMS, validate, and update contacts related to
that project (boilers, steam plants, central utility plants, hospitals,
universities, school districts, municipalities, etc.).

This is **Phase 1** — the internal CRM foundation. Telecom/email integrations
(Twilio, Aircall, SendGrid, etc.) are intentionally not built yet, but the schema
carries future-ready fields (recording URL, transcript, external provider/id).

## Stack

- Next.js (App Router) + TypeScript
- PostgreSQL + Prisma ORM
- Tailwind CSS
- Auth.js / NextAuth v5 (email + password, role-based)

## Roles

- **Admin** — full access; manage users, vendors, orgs, projects, assignments.
- **Manager** — see/assign all projects, review activity, edit statuses.
- **SDR** — see only assigned projects, work the ticket, log activity, add notes,
  start/stop work sessions.

## Getting started

### 1. PostgreSQL

Ensure a PostgreSQL database is available and set `DATABASE_URL`. For local dev:

```bash
# Example (Ubuntu):
sudo apt-get install -y postgresql
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo -u postgres psql -c "CREATE DATABASE capexcrm;"
```

### 2. Environment

Copy `.env.example` to `.env` and adjust values:

```bash
cp .env.example .env
```

- `DATABASE_URL` — Postgres connection string
- `AUTH_SECRET` — any long random string (`openssl rand -base64 32`)
- `FILE_STORAGE_DIR` — where uploaded PDFs are stored in dev (default `./storage/uploads`)

### 3. Install, migrate, seed

```bash
npm install
npx prisma migrate dev
npm run db:seed
```

### 4. Run

```bash
npm run dev
# open http://localhost:3000
```

## Demo accounts

All seeded accounts use the password `password123`:

| Email                     | Role    |
| ------------------------- | ------- |
| admin@capexsignal.com     | Admin   |
| manager@capexsignal.com   | Manager |
| sdr1@capexsignal.com      | SDR     |
| sdr2@capexsignal.com      | SDR     |

## Key screens

- `/login` — email/password sign in (role-based redirect).
- `/dashboard` — admin/manager summary cards, filters, project table.
- `/my-projects` — SDR work queue, sorted by urgency / follow-up / freshness.
- `/projects/[id]` — the project ticket: PDF viewer + evidence on the left,
  status/assignment panel on the right, and tabs for Buyer Contacts, Vendor
  Contacts, Activities, Notes, and Project Data.
- `/projects/new` — create a project ticket (PDF upload + paste contacts as
  JSON/CSV).
- `/vendor-customers`, `/owner-organizations`, `/users`, `/work-sessions`.

## Status automation

Logging activity applies the workflow rules automatically:

- First call/email/SMS on a `NEW`/`ASSIGNED` project → `OUTREACH_STARTED`.
- Outcome `CONNECTED` → contact `CONNECTED`, project → `CONTACTED`.
- Outcome `INTERESTED` → contact `INTERESTED`, project → `VALIDATING` (or
  `VALIDATED_RELEVANT` if flagged in the log modal).
- Outcome `WRONG_PERSON` / `REFERRED` → contact status updated (referral prompts
  adding a new contact).
- Every status change is recorded as a `STATUS_CHANGE` activity; every assignment
  change writes `ProjectAssignmentHistory` + an `ASSIGNMENT_CHANGE` activity.

Status transitions never downgrade a project or override a terminal status
(`CLOSED_WON`, `CLOSED_LOST`, `DEAD`, `VALIDATED_NOT_RELEVANT`).

## Scripts

- `npm run dev` — dev server
- `npm run build` / `npm run start` — production build/serve
- `npm run typecheck` — TypeScript check
- `npm run db:seed` — seed demo data
- `npm run db:reset` — reset DB and re-run migrations

## Future integrations (schema-ready, not built)

Twilio / Aircall / OpenPhone / JustCall calling & SMS, Gmail / SendGrid /
Outlook / Close / HubSpot email, AI assistance (PDF summarization, call scripts,
transcript classification), and a vendor customer portal.
