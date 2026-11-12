import { prisma } from '../db.js';
import { loadAllCases } from './caseLoader.js';

/**
 * Importiert alle Fälle aus content/cases in die Datenbank.
 * Nur Fälle, die den Validator bestehen, werden veröffentlicht.
 */
export async function importCases(dir?: string) {
  const loaded = await loadAllCases(dir);
  const results: { id: string; ok: boolean; title: string; errors: string[] }[] = [];
  for (const c of loaded) {
    if (!c.def) {
      results.push({ id: c.file, ok: false, title: c.file, errors: c.report.errors });
      continue;
    }
    const d = c.def;
    const data = {
      version: d.version,
      title: d.title,
      genre: d.genre,
      difficulty: d.difficulty,
      tier: d.tier,
      published: d.published && c.report.ok,
      exclusive: !!d.exclusive,
      eventTag: d.exclusive?.eventTag ?? null,
      data: d as object,
      checksum: c.checksum,
      validation: c.report as object,
    };
    await prisma.caseDefinition.upsert({ where: { id: d.id }, create: { id: d.id, ...data }, update: { ...data, importedAt: new Date() } });
    results.push({ id: d.id, ok: c.report.ok, title: d.title, errors: c.report.errors });
  }
  return results;
}
