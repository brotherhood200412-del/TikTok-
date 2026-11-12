import { execSync } from 'node:child_process';
import pg from 'pg';

/** Bereitet die Testdatenbank vor: Migrationen anwenden, Tabellen leeren. */
export default async function setup() {
  const url = process.env.TEST_DATABASE_URL ?? 'postgresql://detectives:detectives@localhost:5432/community_detectives_test';
  execSync('npx prisma migrate deploy', { env: { ...process.env, DATABASE_URL: url }, stdio: 'pipe' });
  const client = new pg.Client({ connectionString: url });
  await client.connect();
  const { rows } = await client.query<{ tablename: string }>(`SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> '_prisma_migrations'`);
  if (rows.length) await client.query(`TRUNCATE ${rows.map((r) => `"${r.tablename}"`).join(', ')} CASCADE`);
  await client.end();
}
