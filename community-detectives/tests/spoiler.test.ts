import { describe, expect, it } from 'vitest';
import { buildGameView } from '../server/game/projection.js';
import { simulate } from '../server/game/validator.js';
import { computeAvailability, createInitialState, GameEngine } from '../server/game/engine.js';
import { allCases } from './helpers.js';

const FORBIDDEN_KEYS = ['hotspots', 'secret', 'accept', 'gmNotes', 'keyInsights', 'redHerrings', 'truthTimeline', 'correct', 'answer', 'reveals', 'unlock', 'when'];

function keysDeep(v: unknown, out = new Set<string>()) {
  if (Array.isArray(v)) v.forEach((x) => keysDeep(x, out));
  else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) (out.add(k), keysDeep(x, out));
  return out;
}

describe('Spoilerschutz der Zuschauer-Projektion', async () => {
  const cases = await allCases();
  for (const c of cases) {
    const def = c.def!;
    it(`${def.title}: auch bei vollständigem Ermittlungsstand keine Lösung vor der Auflösung`, () => {
      // Zustand eines Teams, das ALLES gefunden hat – aber noch nicht aufgelöst
      const state = createInitialState(def);
      const engine = new GameEngine(def, state);
      state.status = 'active';
      state.runningSince = engine.now();
      state.phaseIndex = def.phases.length - 1;
      const sim = simulate(def, 0);
      for (const i of sim.insights) state.insights[i] = { at: 0, via: 'streamer' };
      for (const p of sim.puzzles) state.puzzles[p] = { solvedAt: 0, hints: 0, attempts: 1 };
      const view = buildGameView(def, state, engine.now());
      const json = JSON.stringify(view);
      const keys = keysDeep(view);
      for (const k of FORBIDDEN_KEYS) expect(keys.has(k), `verbotener Schlüssel "${k}"`).toBe(false);
      expect(view.solution).toBeUndefined();
      expect(json).not.toContain(def.solution.summary.slice(0, 60));
      expect(json).not.toContain(def.solution.headline);
      expect(json).not.toContain(def.solution.method.slice(0, 60));
      for (const ch of def.characters) expect(json, `Geheimnis von ${ch.name}`).not.toContain(ch.secret.slice(0, 50));
      for (const n of def.gmNotes) expect(json).not.toContain(n.text.slice(0, 50));
    });

    it(`${def.title}: Startzustand zeigt keine gesperrten Beweise oder Rätsel`, () => {
      const state = createInitialState(def);
      const view = buildGameView(def, state, Date.now());
      const lockedEv = def.evidence.filter((e) => e.unlock).map((e) => e.id);
      for (const id of lockedEv) {
        const unlockedAtStart = state.announcedEvidence.includes(id);
        if (!unlockedAtStart) expect(view.evidence.some((e) => e.id === id)).toBe(false);
      }
      const avail = computeAvailability(def, state, Date.now());
      for (const p of def.puzzles.filter((p) => !avail.puzzles.has(p.id))) expect(view.puzzles.some((x) => x.id === p.id)).toBe(false);
      expect(view.evidence.length).toBe(avail.evidence.size);
    });

    it(`${def.title}: nach der Auflösung ist die Lösung sichtbar`, () => {
      const state = createInitialState(def);
      state.status = 'revealed';
      const view = buildGameView(def, state, Date.now());
      expect(view.solution?.culprit).toBe(def.solution.culprit);
    });
  }
});
