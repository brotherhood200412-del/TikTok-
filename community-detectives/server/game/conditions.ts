import type { Condition } from '../../shared/case/schema.js';

export interface ConditionContext {
  insights: ReadonlySet<string>;
  evidence: ReadonlySet<string>;
  puzzles: ReadonlySet<string>;
  events: ReadonlySet<string>;
  topics: ReadonlySet<string>;
  phaseIndex: number;
  phaseOrder: readonly string[];
  minutes: number;
  wrongAccusations: number;
}

export function evaluate(cond: Condition | undefined, ctx: ConditionContext): boolean {
  if (!cond) return true;
  if ('all' in cond) return cond.all.every((c) => evaluate(c, ctx));
  if ('any' in cond) return cond.any.some((c) => evaluate(c, ctx));
  if ('not' in cond) return !evaluate(cond.not, ctx);
  if ('insight' in cond) return ctx.insights.has(cond.insight);
  if ('evidence' in cond) return ctx.evidence.has(cond.evidence);
  if ('puzzle' in cond) return ctx.puzzles.has(cond.puzzle);
  if ('event' in cond) return ctx.events.has(cond.event);
  if ('topic' in cond) return ctx.topics.has(cond.topic);
  if ('phase' in cond) {
    const idx = ctx.phaseOrder.indexOf(cond.phase);
    return idx >= 0 && ctx.phaseIndex >= idx;
  }
  if ('minutes' in cond) return ctx.minutes >= cond.minutes;
  if ('wrongAccusations' in cond) return ctx.wrongAccusations >= cond.wrongAccusations;
  return false;
}

/** Sammelt alle IDs, auf die eine Bedingung verweist (für den Validator). */
export function collectRefs(cond: Condition | undefined, out: { kind: string; id: string }[] = []) {
  if (!cond) return out;
  if ('all' in cond) cond.all.forEach((c) => collectRefs(c, out));
  else if ('any' in cond) cond.any.forEach((c) => collectRefs(c, out));
  else if ('not' in cond) collectRefs(cond.not, out);
  else {
    for (const kind of ['insight', 'evidence', 'puzzle', 'event', 'phase', 'topic'] as const) {
      if (kind in cond) out.push({ kind, id: (cond as Record<string, string>)[kind] });
    }
  }
  return out;
}

/** Menschlich lesbare Beschreibung (nur für Streamer/Spielleitung). */
export function describe(cond: Condition | undefined, names: (kind: string, id: string) => string): string {
  if (!cond) return 'von Beginn an verfügbar';
  if ('all' in cond) return cond.all.map((c) => describe(c, names)).join(' UND ');
  if ('any' in cond) return '(' + cond.any.map((c) => describe(c, names)).join(' ODER ') + ')';
  if ('not' in cond) return 'NICHT ' + describe(cond.not, names);
  if ('insight' in cond) return `Erkenntnis „${names('insight', cond.insight)}“`;
  if ('evidence' in cond) return `Beweis „${names('evidence', cond.evidence)}“ verfügbar`;
  if ('puzzle' in cond) return `Rätsel „${names('puzzle', cond.puzzle)}“ gelöst`;
  if ('event' in cond) return `Ereignis „${names('event', cond.event)}“`;
  if ('topic' in cond) return `Frage „${names('topic', cond.topic)}“ gestellt`;
  if ('phase' in cond) return `Phase „${names('phase', cond.phase)}“`;
  if ('minutes' in cond) return `nach ${cond.minutes} Minuten`;
  if ('wrongAccusations' in cond) return `nach ${cond.wrongAccusations} falschen Anschuldigung(en)`;
  return '?';
}
