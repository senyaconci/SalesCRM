# Deploying CapEx Signal CRM online

The app is ready to deploy to **Vercel** with **Neon Postgres** and **Vercel
Blob** (all have free tiers). This gives you a public `https://…vercel.app` URL.

You'll do the clicks (deploying requires your own Vercel/GitHub accounts). It's a
one-time setup of ~10 minutes.

## Steps

### 1. Push the branch (or merge the PR)

The code is on branch `cursor/capex-signal-crm-mvp-f852`. You can deploy directly
from that branch, or merge the PR to `main` first.

### 2. Create the Vercel project

1. Go to <https://vercel.com/new> and import the `SalesCRM` GitHub repo.
2. When asked which branch, pick `main` (or the feature branch).
3. **Don't deploy yet** — add the database and env vars first (below), otherwise
   the first build fails because there's no `DATABASE_URL`.

### 3. Add a Postgres database (Neon)

In the Vercel project → **Storage** tab → **Create Database** → **Neon
(Postgres)**. Vercel automatically injects `DATABASE_URL` (and related vars) into
the project. That's all you need for the DB connection.

### 4. Add Blob storage (for PDF uploads)

In the same **Storage** tab → **Create** → **Blob**. This injects
`BLOB_READ_WRITE_TOKEN`, which makes PDF uploads go to Blob instead of local disk
(local disk is read-only on Vercel, so this is required for uploads to work).

### 5. Add the auth secret

Project → **Settings → Environment Variables** → add:

| Name          | Value                                   |
| ------------- | --------------------------------------- |
| `AUTH_SECRET` | output of `openssl rand -base64 32`     |

(`AUTH_URL` is not needed — the app trusts the host automatically.)

### 6. Deploy

Trigger a deploy (Vercel → **Deployments → Redeploy**, or push a commit). The
build command runs `prisma generate && prisma migrate deploy && next build`, so
your database schema is created automatically on first deploy.

### 7. Seed the demo data (one time)

The seed script is destructive (it wipes and repopulates), so it is **not** run
during deploys. Run it once against the production database from your machine:

```bash
# Copy the Neon connection string from Vercel → Storage → your DB → .env tab
export DATABASE_URL="postgresql://…neon…/…?sslmode=require"
npx prisma migrate deploy   # if you skipped auto-migrate
npm run db:seed
```

Now open your `https://<project>.vercel.app` URL and log in:

| Email                   | Role    | Password      |
| ----------------------- | ------- | ------------- |
| admin@capexsignal.com   | Admin   | `password123` |
| manager@capexsignal.com | Manager | `password123` |
| sdr1@capexsignal.com    | SDR     | `password123` |
| sdr2@capexsignal.com    | SDR     | `password123` |

> Change or delete these demo accounts before using real data — create your own
> admin from the **Users** page, then deactivate the demo ones.

## Notes

- **PDF uploads** require Blob storage (step 4). Without it, uploads will error in
  production. Everything else works without Blob.
- **Migrations**: `prisma migrate deploy` runs on every build and is idempotent —
  it only applies new migrations.
- **Other hosts**: any Node host works (Railway, Render, Fly.io, a VPS). Set
  `DATABASE_URL` + `AUTH_SECRET`, run `npm run db:deploy` and `npm run build`,
  then `npm run start`. For PDF uploads on ephemeral hosts, either set
  `BLOB_READ_WRITE_TOKEN` or point `FILE_STORAGE_DIR` at a persistent volume.
