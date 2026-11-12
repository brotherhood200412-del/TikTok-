import { describe, expect, it } from 'vitest';
import { simulate } from '../server/game/validator.js';
import { allCases } from './helpers.js';

describe('Fallbibliothek', async () => {
  const cases = await allCases();

  it('enthält mindestens fünf Fälle in allen vier Schwierigkeitsgraden', () => {
    expect(cases.length).toBeGreaterThanOrEqual(5);
    const diffs = new Set(cases.map((c) => c.def?.difficulty));
    for (const d of ['einsteiger', 'fortgeschritten', 'experte', 'meisterdetektiv']) expect(diffs).toContain(d);
    expect(new Set(cases.map((c) => c.def?.genre)).size).toBeGreaterThanOrEqual(5);
  });

  for (const c of cases) {
    describe(c.def?.title ?? c.file, () => {
      it('besteht den Fallvalidator ohne Fehler', () => {
        expect(c.report.errors).toEqual([]);
        expect(c.report.ok).toBe(true);
      });
      it('alle Erkenntnisse, Beweise und Rätsel sind für ein perfektes Team erreichbar', () => {
        const def = c.def!;
        const sim = simulate(def, 0);
        expect(sim.insights.size).toBe(def.insights.length);
        for (const k of def.solution.keyInsights) expect(sim.insights.has(k)).toBe(true);
        expect(sim.puzzles.size).toBe(def.puzzles.length);
      });
      it('der Täter ist eine verdächtige Person und wird von Schlüssel-Erkenntnissen belastet', () => {
        const def = c.def!;
        const culprit = def.characters.find((x) => x.id === def.solution.culprit)!;
        expect(culprit.role).toBe('suspect');
        const blaming = def.insights.filter((i) => def.solution.keyInsights.includes(i.id) && i.characters.includes(culprit.id));
        expect(blaming.length).toBeGreaterThan(0);
      });
    });
  }
});
