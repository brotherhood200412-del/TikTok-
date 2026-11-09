import { describe, expect, it } from 'vitest';
import { evaluate } from '../server/game/conditions.js';
import { computeAvailability, gameMs, normalizeAnswer, POINTS } from '../server/game/engine.js';
import { loadCase, makeEngine, viewer } from './helpers.js';

const def = await loadCase('der-perfekte-einbruch');

describe('Bedingungen', () => {
  const ctx = {
    insights: new Set(['a']),
    evidence: new Set<string>(),
    puzzles: new Set<string>(),
    events: new Set<string>(),
    topics: new Set(['x.y']),
    phaseIndex: 1,
    phaseOrder: ['p0', 'p1', 'p2'],
    minutes: 10,
    wrongAccusations: 0,
  };
  it('wertet all/any/not, Phasen und Minuten korrekt aus', () => {
    expect(evaluate({ all: [{ insight: 'a' }, { topic: 'x.y' }] }, ctx)).toBe(true);
    expect(evaluate({ any: [{ insight: 'b' }, { phase: 'p1' }] }, ctx)).toBe(true);
    expect(evaluate({ phase: 'p2' }, ctx)).toBe(false);
    expect(evaluate({ not: { insight: 'a' } }, ctx)).toBe(false);
    expect(evaluate({ minutes: 11 }, ctx)).toBe(false);
    expect(evaluate({ wrongAccusations: 1 }, ctx)).toBe(false);
    expect(evaluate(undefined, ctx)).toBe(true);
  });
});

describe('Spiel-Engine', () => {
  it('normalisiert Antworten (Groß-/Kleinschreibung, Umlaute, Satzzeichen)', () => {
    expect(normalizeAnswer(' K-14 ')).toBe('k14');
    expect(normalizeAnswer('Zwölf')).toBe('zwoelf');
    expect(normalizeAnswer('Jonas  Wendt!')).toBe('jonaswendt');
  });

  it('erlaubt keine Aktionen vor dem Start', () => {
    const { engine } = makeEngine(def);
    const r = engine.markItem('ev_gehweg', 'scherben', viewer());
    expect(r.ok).toBe(false);
    expect(r.code).toBe('not_started');
  });

  it('Hotspot: Treffer deckt Erkenntnis auf, vergibt Punkte genau einmal', () => {
    const { engine, state } = makeEngine(def);
    engine.start();
    const miss = engine.markItem('ev_gehweg', 'laterne', viewer());
    expect(miss.code).toBe('miss');
    const hit = engine.markItem('ev_gehweg', 'scherben', viewer('p1'));
    expect(hit.ok).toBe(true);
    expect(state.insights.in_von_innen).toBeDefined();
    expect(hit.awards).toEqual([{ participantId: 'p1', amount: POINTS.hotspot, reason: 'hotspot', ref: 'ev_gehweg:scherben' }]);
    const again = engine.markItem('ev_gehweg', 'scherben', viewer('p2'));
    expect(again.code).toBe('known');
    expect(again.awards).toEqual([]);
    // zweiter Hotspot mit derselben Erkenntnis bringt keine erneuten Punkte
    const second = engine.markItem('ev_kabinett', 'boden', viewer('p3'));
    expect(second.awards).toEqual([]);
  });

  it('gesperrte Beweise können nicht untersucht werden', () => {
    const { engine } = makeEngine(def);
    engine.start();
    const r = engine.markItem('ev_werkstatt', 'skalpell', viewer());
    expect(r.code).toBe('locked');
  });

  it('Verbindungen funktionieren in beide Richtungen und schalten Beweise frei', () => {
    const { engine, state } = makeEngine(def);
    engine.start();
    expect(engine.connect('ev_ausgang', 'wendt', viewer()).code).toBe('locked'); // Phase 2 noch nicht erreicht
    engine.setPhase('vernehmungen');
    const r = engine.connect('wendt', 'ev_ausgang', viewer());
    expect(r.ok).toBe(true);
    expect(state.insights.in_wendt_luegt).toBeDefined();
    expect(r.discoveries.some((d) => d.kind === 'evidence' && d.id === 'ev_versandliste')).toBe(true);
    expect(engine.connect('ev_alarm', 'ev_wachbuch', viewer()).code).toBe('miss');
  });

  it('Rätsel: falsche Antwort, Hinweise reduzieren Punkte, richtige Antwort löst', () => {
    const { engine, state } = makeEngine(def);
    engine.start();
    engine.setPhase('vernehmungen');
    engine.connect('wendt', 'ev_ausgang', viewer());
    expect(engine.solvePuzzle('p_kiste', 'K-13', viewer()).code).toBe('wrong');
    expect(engine.revealHint('p_kiste').ok).toBe(true);
    const r = engine.solvePuzzle('p_kiste', ' k14 ', viewer('p9'));
    expect(r.ok).toBe(true);
    expect(r.awards[0].amount).toBe(POINTS.puzzle - POINTS.puzzleHintPenalty);
    expect(state.insights.in_kiste14).toBeDefined();
    expect(state.puzzles.p_kiste.attempts).toBe(2);
  });

  it('Reihenfolge-Rätsel prüft die exakte Reihenfolge', () => {
    const { engine } = makeEngine(def);
    engine.start();
    engine.markItem('ev_alarm', 'a2108', viewer());
    engine.markItem('ev_wachbuch', 'w4', viewer());
    const wrong = ['o_rede', 'o_kontrolle', 'o_unscharf', 'o_klirren', 'o_scharf', 'o_entdeckt'];
    expect(engine.solvePuzzle('p_reihenfolge', wrong, viewer()).ok).toBe(false);
    const right = ['o_kontrolle', 'o_rede', 'o_unscharf', 'o_klirren', 'o_scharf', 'o_entdeckt'];
    expect(engine.solvePuzzle('p_reihenfolge', right, viewer()).ok).toBe(true);
  });

  it('Vernehmung: Antworten hängen vom Ermittlungsstand ab (reproduzierbar)', () => {
    const { engine } = makeEngine(def);
    engine.start();
    engine.startInterrogation('wendt');
    const first = engine.ask('wendt', 'abend', { kind: 'community' });
    expect(first.message).toContain('halb neun');
    engine.setPhase('vernehmungen');
    engine.connect('wendt', 'ev_ausgang', viewer());
    const second = engine.ask('wendt', 'abend', { kind: 'community' });
    expect(second.message).toContain('21:24');
    expect(engine.state.stress.wendt).toBe(60);
    // gleiche Eingaben → gleiche Antwort
    expect(engine.ask('wendt', 'abend', { kind: 'community' }).message).toBe(second.message);
  });

  it('Pause stoppt die Spielzeit; zeitgesteuerte Ereignisse feuern nach Spielminuten', () => {
    const { engine, state, clock } = makeEngine(def);
    engine.start(clock.get());
    clock.advance(10 * 60_000);
    engine.pause(clock.get());
    clock.advance(60 * 60_000); // Pause zählt nicht
    expect(gameMs(state, clock.get())).toBe(10 * 60_000);
    engine.resume(clock.get());
    engine.tick(clock.get());
    expect(state.events.ev_versicherung_meldet).toBeUndefined();
    clock.advance(5 * 60_000 + 1000);
    const r = engine.tick(clock.get());
    expect(state.events.ev_versicherung_meldet).toBeDefined();
    expect(r.discoveries.some((d) => d.id === 'ev_versicherung')).toBe(true);
  });

  it('ohne zeitgesteuerte Ereignisse bleibt das Ereignis manuell auslösbar', () => {
    const { engine, state, clock } = makeEngine(def, { timedEvents: false });
    engine.start(clock.get());
    clock.advance(30 * 60_000);
    engine.tick(clock.get());
    expect(state.events.ev_versicherung_meldet).toBeUndefined();
    expect(engine.fireEvent('ev_versicherung_meldet').ok).toBe(true);
  });

  it('falsche Anschuldigung löst Folgeereignis aus, richtige Anklage löst den Fall', () => {
    const { engine, state } = makeEngine(def);
    engine.start();
    engine.enterFinale();
    const wrong = engine.accuse('voss', undefined, 'test');
    expect((wrong.data as { correct: boolean }).correct).toBe(false);
    expect(state.status).toBe('active');
    expect(state.events.ev_nachbarin).toBeDefined();
    expect(state.insights.in_von_innen).toBeDefined();
    engine.enterFinale();
    const right = engine.accuse('wendt', 'pr_kiste', 'test');
    expect((right.data as { correct: boolean }).correct).toBe(true);
    expect(state.status).toBe('solved');
    expect(engine.reveal().ok).toBe(true);
    expect(state.status).toBe('revealed');
  });

  it('Verfügbarkeit: Personen und Beweise erscheinen über Bedingungen', () => {
    const { engine, state } = makeEngine(def);
    engine.start();
    let a = computeAvailability(def, state, engine.now());
    expect(a.evidence.has('ev_handbuch')).toBe(false);
    engine.ask('okafor', 'alarm', viewer());
    a = computeAvailability(def, state, engine.now());
    expect(a.evidence.has('ev_handbuch')).toBe(true);
    expect(state.announcedEvidence).toContain('ev_handbuch');
  });
});
