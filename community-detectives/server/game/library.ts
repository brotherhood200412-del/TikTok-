/**
 * Fallbibliothek: Zugriff auf importierte Fälle, Freischaltung nach Plan,
 * Exklusiv-Reservierungen und intelligente Fallzuweisung.
 */
import { caseSchema, type CaseDefinition, type Tier } from '../../shared/case/schema.js';
import { prisma } from '../db.js';

const TIER_RANK: Record<Tier, number> = { free: 0, creator: 1, premium: 2 };
const cache = new Map<string, { version: number; checksum: string; def: CaseDefinition }>();

export async function getCaseDefinition(id: string): Promise<CaseDefinition | null> {
  const row = await prisma.caseDefinition.findUnique({ where: { id } });
  if (!row) return null;
  const hit = cache.get(id);
  if (hit && hit.checksum === row.checksum) return hit.def;
  const def = caseSchema.parse(row.data);
  cache.set(id, { version: row.version, checksum: row.checksum, def });
  return def;
}

export interface LibraryEntry {
  id: string;
  title: string;
  tagline: string;
  genre: string;
  difficulty: string;
  tier: Tier;
  estimatedMinutes: number;
  accent: string;
  exclusive: boolean;
  eventTag: string | null;
  series: CaseDefinition['series'] | null;
  stats: { suspects: number; evidence: number; puzzles: number };
  playable: boolean;
  lockedReason: string | null;
  playedByMe: number;
  lastPlayedAt: string | null;
  globalPlays: number;
}

export async function listLibrary(streamer: { id: string; plan: Tier }): Promise<LibraryEntry[]> {
  const [rows, reservations, mine, global] = await Promise.all([
    prisma.caseDefinition.findMany({ where: { published: true }, orderBy: [{ difficulty: 'asc' }, { title: 'asc' }] }),
    prisma.caseReservation.findMany({ where: { streamerId: streamer.id } }),
    prisma.gameSession.groupBy({ by: ['caseId'], where: { streamerId: streamer.id }, _count: { _all: true }, _max: { createdAt: true } }),
    prisma.gameSession.groupBy({ by: ['caseId'], _count: { _all: true } }),
  ]);
  const reserved = new Set(reservations.map((r) => r.caseId));
  const mineMap = new Map(mine.map((m) => [m.caseId, m]));
  const globalMap = new Map(global.map((g) => [g.caseId, g._count._all]));
  const order = ['einsteiger', 'fortgeschritten', 'experte', 'meisterdetektiv'];
  return rows
    .map((r) => {
      const def = r.data as unknown as CaseDefinition;
      let lockedReason: string | null = null;
      if (TIER_RANK[r.tier] > TIER_RANK[streamer.plan]) lockedReason = `Benötigt den Plan „${r.tier === 'creator' ? 'Creator' : 'Premium'}“.`;
      if (r.exclusive && !reserved.has(r.id)) lockedReason = `Exklusivfall für das Event „${r.eventTag}“.`;
      const m = mineMap.get(r.id);
      return {
        id: r.id,
        title: r.title,
        tagline: def.tagline,
        genre: r.genre,
        difficulty: r.difficulty,
        tier: r.tier,
        estimatedMinutes: def.estimatedMinutes,
        accent: def.accent ?? '#b3262e',
        exclusive: r.exclusive,
        eventTag: r.eventTag,
        series: def.series ?? null,
        stats: { suspects: def.characters.filter((c) => c.role === 'suspect').length, evidence: def.evidence.length, puzzles: def.puzzles.length },
        playable: lockedReason === null,
        lockedReason,
        playedByMe: m?._count._all ?? 0,
        lastPlayedAt: m?._max.createdAt?.toISOString() ?? null,
        globalPlays: globalMap.get(r.id) ?? 0,
      };
    })
    .sort((a, b) => order.indexOf(a.difficulty) - order.indexOf(b.difficulty) || a.title.localeCompare(b.title));
}

/**
 * Fallzuweisung: bevorzugt spielbare, vom Streamer noch nicht gespielte Fälle
 * im gewünschten Schwierigkeitsgrad. Unter gleichwertigen Kandidaten werden
 * global seltener gespielte Fälle bevorzugt, damit nicht alle Communities
 * gleichzeitig denselben Fall erleben. Exklusivfälle werden nur zugewiesen,
 * wenn sie für den Streamer reserviert sind.
 */
export function pickCase(entries: LibraryEntry[], opts: { difficulty?: string; random?: () => number } = {}): LibraryEntry | null {
  const rnd = opts.random ?? Math.random;
  const playable = entries.filter((e) => e.playable);
  if (!playable.length) return null;
  const score = (e: LibraryEntry) =>
    (e.playedByMe === 0 ? 0 : 1000 + e.playedByMe * 100) + (opts.difficulty && e.difficulty !== opts.difficulty ? 500 : 0) + e.globalPlays * 3 + (e.exclusive ? -50 : 0);
  const ranked = playable.map((e) => ({ e, s: score(e) })).sort((a, b) => a.s - b.s);
  const best = ranked[0].s;
  const pool = ranked.filter((r) => r.s <= best + 6); // kleine Streuung unter fast gleichwertigen Kandidaten
  return pool[Math.floor(rnd() * pool.length)].e;
}

export function tierAllows(plan: Tier, tier: Tier) {
  return TIER_RANK[tier] <= TIER_RANK[plan];
}
