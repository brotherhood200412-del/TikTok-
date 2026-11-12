import 'dotenv/config';
import { defineConfig } from 'prisma/config';
export default defineConfig({
  schema: 'prisma/schema.prisma',
  migrations: { path: 'prisma/migrations' },
  // Beim Bauen (prisma generate) wird keine echte Datenbank benötigt.
  datasource: { url: process.env.DATABASE_URL ?? 'postgresql://build:build@localhost:5432/build' },
});
