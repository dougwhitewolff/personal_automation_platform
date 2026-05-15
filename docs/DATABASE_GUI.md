# Viewing the database in a GUI

The automation platform uses **one PostgreSQL database** (`DATABASE_URL`) for tenants, captures, reviews, outbox emails, and CRM email mappings.

## Prisma Studio (recommended)

```bash
cd /path/to/personal_automation_platform_v2
npx prisma studio
```

Default URL: [http://localhost:5555](http://localhost:5555)

Use another port if it conflicts with another app:

```bash
npx prisma studio --port 5556
```

## Local Postgres with Docker

From the repo root:

```bash
docker compose up -d
```

Set `DATABASE_URL` in `.env` to match [docker-compose.yml](../docker-compose.yml) (default port **5434**, database `personal_automation`), then:

```bash
npx prisma migrate deploy
npm run prisma:seed
```

## Other tools

**pgAdmin**, **DBeaver**, **TablePlus**, **Azure Data Studio** — connect with the same `DATABASE_URL` connection string.

## Migrating from older setups

- If you previously used **MongoDB** (`DATABASE_URL` as a `mongodb://` URL), switch `.env` to a Postgres `DATABASE_URL` and run `prisma migrate deploy`.
- If you used a **separate outbox URL** (`DATABASE_URL_OUTBOX`), merge data into the single Postgres database and use only `DATABASE_URL`.
