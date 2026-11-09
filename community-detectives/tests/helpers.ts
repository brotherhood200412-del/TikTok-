import path from 'node:path';
import { loadAllCases, loadCaseFile } from '../server/game/caseLoader.js';
import type { CaseDefinition } from '../shared/case/schema.js';
import { GameEngine, createInitialState } from '../server/game/engine.js';

export async function loadCase(id: string): Promise<CaseDefinition> {
  const c = await loadCaseFile(path.resolve(import.meta.dirname, `../content/cases/${id}.yaml`));
  if (!c.def) throw new Error(c.report.errors.join('\n'));
  return c.def;
}
export const allCases = () => loadAllCases();

/** Engine mit kontrollierbarer Uhr. */
export function makeEngine(def: CaseDefinition, opts = { timedEvents: true }) {
  const state = createInitialState(def);
  const engine = new GameEngine(def, state, opts);
  let now = 1_000_000;
  engine.now = () => now;
  const clock = { advance: (ms: number) => (now += ms), get: () => now };
  return { engine, state, clock };
}
export const viewer = (id = 'p1', name = 'Tester') => ({ kind: 'viewer' as const, participantId: id, name });
