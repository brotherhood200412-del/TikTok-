/**
 * Fallvalidator – Qualitätssicherung für jeden Fall vor der Veröffentlichung.
 *
 * 1. Schema-Prüfung (zod)
 * 2. Referenzprüfung (alle IDs existieren, Antworten passen zu Eingaben …)
 * 3. Simulation eines "perfekten Ermittlerteams": Ausgehend vom Startzustand
 *    werden alle erreichbaren Aktionen ausgeführt, bis nichts Neues mehr
 *    passiert. So werden unerreichbare Hinweise, unlösbare Rätsel und
 *    Sackgassen erkannt.
 * 4. Fairness: Die Lösungskette muss ohne falsche Anschuldigung erreichbar
 *    sein, falsche Fährten müssen auflösbar sein, der Täter muss durch
 *    Beweise belastet werden.
 */
import { caseSchema, type CaseDefinition, type Condition } from '../../shared/case/schema.js';
import { collectRefs } from './conditions.js';
import { GameEngine, createInitialState, itemIds, computeAvailability } from './engine.js';

export interface ValidationReport {
  ok: boolean;
  errors: string[];
  warnings: string[];
  stats: {
    suspects: number;
    characters: number;
    evidence: number;
    insights: number;
    puzzles: number;
    statements: number;
    connections: number;
    events: number;
    redHerrings: number;
    reachableInsights: number;
  };
}

const GUIDE: Record<string, { suspects: [number, number]; evidence: [number, number]; puzzles: [number, number] }> = {
  einsteiger: { suspects: [3, 6], evidence: [8, 22], puzzles: [2, 5] },
  fortgeschritten: { suspects: [4, 8], evidence: [12, 30], puzzles: [3, 7] },
  experte: { suspects: [5, 9], evidence: [16, 36], puzzles: [4, 9] },
  meisterdetektiv: { suspects: [6, 10], evidence: [20, 40], puzzles: [5, 10] },
};

export function parseCase(raw: unknown): { def?: CaseDefinition; errors: string[] } {
  const parsed = caseSchema.safeParse(raw);
  if (!parsed.success) {
    return { errors: parsed.error.issues.map((i) => `Schema: ${i.path.join('.')} – ${i.message}`) };
  }
  return { def: parsed.data, errors: [] };
}

export function validateCase(raw: unknown): ValidationReport & { def?: CaseDefinition } {
  const { def, errors: schemaErrors } = parseCase(raw);
  const emptyStats = { suspects: 0, characters: 0, evidence: 0, insights: 0, puzzles: 0, statements: 0, connections: 0, events: 0, redHerrings: 0, reachableInsights: 0 };
  if (!def) return { ok: false, errors: schemaErrors, warnings: [], stats: emptyStats };

  const errors: string[] = [];
  const warnings: string[] = [];
  const err = (m: string) => errors.push(m);
  const warn = (m: string) => warnings.push(m);

  /* ---------- Eindeutige IDs ---------- */
  const globalIds = new Map<string, string>();
  const reg = (kind: string, id: string) => {
    if (globalIds.has(id)) err(`Doppelte ID "${id}" (${globalIds.get(id)} und ${kind})`);
    else globalIds.set(id, kind);
  };
  def.phases.forEach((p) => reg('Phase', p.id));
  def.characters.forEach((c) => reg('Person', c.id));
  def.insights.forEach((i) => reg('Erkenntnis', i.id));
  def.evidence.forEach((e) => reg('Beweis', e.id));
  def.puzzles.forEach((p) => reg('Rätsel', p.id));
  def.events.forEach((e) => reg('Ereignis', e.id));
  def.connections.forEach((c) => reg('Verbindung', c.id));

  const chars = new Map(def.characters.map((c) => [c.id, c]));
  const insights = new Map(def.insights.map((i) => [i.id, i]));
  const evidence = new Map(def.evidence.map((e) => [e.id, e]));
  const puzzles = new Map(def.puzzles.map((p) => [p.id, p]));
  const events = new Map(def.events.map((e) => [e.id, e]));
  const phases = new Set(def.phases.map((p) => p.id));
  const topics = new Set<string>();
  for (const it of def.interrogations) {
    const seen = new Set<string>();
    for (const t of it.topics) {
      if (seen.has(t.id)) err(`Vernehmung ${it.character}: doppeltes Thema "${t.id}"`);
      seen.add(t.id);
      topics.add(`${it.character}.${t.id}`);
    }
  }

  const needInsight = (id: string, where: string) => !insights.has(id) && err(`${where}: unbekannte Erkenntnis "${id}"`);
  const checkCond = (c: Condition | undefined, where: string) => {
    for (const r of collectRefs(c)) {
      const ok =
        (r.kind === 'insight' && insights.has(r.id)) ||
        (r.kind === 'evidence' && evidence.has(r.id)) ||
        (r.kind === 'puzzle' && puzzles.has(r.id)) ||
        (r.kind === 'event' && events.has(r.id)) ||
        (r.kind === 'phase' && phases.has(r.id)) ||
        (r.kind === 'topic' && topics.has(r.id));
      if (!ok) err(`${where}: Bedingung verweist auf unbekannte ${r.kind} "${r.id}"`);
    }
    if (c && JSON.stringify(c).includes('"not"')) warn(`${where}: verwendet "not" – Element kann wieder verschwinden (Sackgassengefahr).`);
  };

  /* ---------- Referenzen ---------- */
  const insightSources = new Map<string, string[]>();
  const addSource = (ins: string, src: string) => insightSources.set(ins, [...(insightSources.get(ins) ?? []), src]);

  for (const c of def.characters) {
    checkCond(c.unlock, `Person ${c.id}`);
    if (c.role === 'suspect') {
      if (!c.alibi) warn(`Verdächtige(r) ${c.name}: kein Alibi angegeben.`);
      if (!c.motive) warn(`Verdächtige(r) ${c.name}: kein mögliches Motiv angegeben.`);
      if (!def.interrogations.some((i) => i.character === c.id)) warn(`Verdächtige(r) ${c.name}: keine Vernehmung definiert.`);
    }
  }
  for (const i of def.insights) for (const c of i.characters) if (!chars.has(c)) err(`Erkenntnis ${i.id}: unbekannte Person "${c}"`);

  for (const e of def.evidence) {
    checkCond(e.unlock, `Beweis ${e.id}`);
    const items = itemIds(e.content);
    const seen = new Set<string>();
    for (const it of items) {
      if (seen.has(it)) err(`Beweis ${e.id}: doppelte Element-ID "${it}"`);
      seen.add(it);
    }
    if (e.content.kind === 'map') {
      const places = new Set(e.content.places.map((p) => p.id));
      for (const r of e.content.routes) if (!places.has(r.from) || !places.has(r.to)) err(`Karte ${e.id}: Route ${r.id} verweist auf unbekannten Ort.`);
    }
    if (e.content.kind === 'table') {
      for (const r of e.content.rows) if (r.cells.length !== e.content.columns.length) err(`Tabelle ${e.id}: Zeile ${r.id} hat ${r.cells.length} statt ${e.content.columns.length} Zellen.`);
    }
    const hsSeen = new Set<string>();
    for (const h of e.hotspots) {
      if (hsSeen.has(h.item)) err(`Beweis ${e.id}: Element "${h.item}" hat mehrere Hotspots – nur der erste würde greifen.`);
      hsSeen.add(h.item);
      if (!items.includes(h.item)) err(`Beweis ${e.id}: Hotspot verweist auf unbekanntes Element "${h.item}"`);
      needInsight(h.insight, `Beweis ${e.id}`);
      addSource(h.insight, `Hotspot ${e.id}:${h.item}`);
    }
  }
  for (const c of def.connections) {
    for (const end of [c.a, c.b]) {
      if (!evidence.has(end) && !insights.has(end) && !chars.has(end)) err(`Verbindung ${c.id}: unbekanntes Element "${end}"`);
    }
    needInsight(c.insight, `Verbindung ${c.id}`);
    addSource(c.insight, `Verbindung ${c.id}`);
  }
  for (const it of def.interrogations) {
    if (!chars.has(it.character)) err(`Vernehmung: unbekannte Person "${it.character}"`);
    for (const t of it.topics) {
      checkCond(t.unlock, `Frage ${it.character}.${t.id}`);
      t.responses.forEach((r, idx) => {
        checkCond(r.when, `Antwort ${it.character}.${t.id}#${idx}`);
        if (r.reveals) {
          needInsight(r.reveals, `Antwort ${it.character}.${t.id}#${idx}`);
          addSource(r.reveals, `Vernehmung ${it.character}.${t.id}`);
        }
      });
      if (t.responses[t.responses.length - 1].when) err(`Frage ${it.character}.${t.id}: Die letzte Antwort muss eine Standardantwort ohne "when" sein.`);
    }
  }
  for (const p of def.puzzles) {
    checkCond(p.unlock, `Rätsel ${p.id}`);
    for (const e of p.evidence) if (!evidence.has(e)) err(`Rätsel ${p.id}: unbekannter Beweis "${e}"`);
    for (const r of p.reveals) {
      needInsight(r, `Rätsel ${p.id}`);
      addSource(r, `Rätsel ${p.id}`);
    }
    if ('choice' in p.answer) {
      if (p.input.kind !== 'choice') err(`Rätsel ${p.id}: Auswahl-Antwort erfordert input.kind=choice`);
      else if (!p.input.options.some((o) => o.id === (p.answer as { choice: string }).choice)) err(`Rätsel ${p.id}: richtige Option existiert nicht.`);
    }
    if ('order' in p.answer) {
      if (p.input.kind !== 'order') err(`Rätsel ${p.id}: Reihenfolge-Antwort erfordert input.kind=order`);
      else {
        const items = p.input.items.map((i) => i.id).sort().join(',');
        if ([...p.answer.order].sort().join(',') !== items) err(`Rätsel ${p.id}: Lösungsreihenfolge muss alle Elemente genau einmal enthalten.`);
      }
    }
    if ('accept' in p.answer && p.input.kind !== 'text') err(`Rätsel ${p.id}: Textantwort erfordert input.kind=text`);
    if (p.hints.length < 2) warn(`Rätsel ${p.id}: weniger als zwei Hilfestufen.`);
  }
  for (const e of def.events) {
    checkCond(e.trigger.when, `Ereignis ${e.id}`);
    for (const r of e.reveals) {
      needInsight(r, `Ereignis ${e.id}`);
      addSource(r, `Ereignis ${e.id}`);
    }
  }
  if (def.accusation.proof) {
    const correct = def.accusation.proof.options.filter((o) => o.correct);
    if (correct.length !== 1) err(`Anklage: Beweisfrage braucht genau eine richtige Option (gefunden: ${correct.length}).`);
  }

  /* ---------- Lösung ---------- */
  const sol = def.solution;
  const culprit = chars.get(sol.culprit);
  if (!culprit) err(`Lösung: unbekannter Täter "${sol.culprit}"`);
  else if (culprit.role !== 'suspect') err(`Lösung: Täter "${sol.culprit}" ist nicht als verdächtig markiert.`);
  for (const a of sol.accomplices) if (!chars.has(a)) err(`Lösung: unbekannter Komplize "${a}"`);
  sol.keyInsights.forEach((k) => needInsight(k, 'Lösung.keyInsights'));
  sol.chain.forEach((c) => needInsight(c.insight, 'Lösung.chain'));
  for (const k of sol.keyInsights) if (!sol.chain.some((c) => c.insight === k)) warn(`Lösung: Schlüssel-Erkenntnis "${k}" wird in der Lösungskette nicht erklärt.`);
  for (const r of sol.redHerrings) {
    if (r.character && !chars.has(r.character)) err(`Falsche Fährte: unbekannte Person "${r.character}"`);
    needInsight(r.debunkedBy, `Falsche Fährte "${r.clue}"`);
  }
  if (culprit && !sol.keyInsights.some((k) => insights.get(k)?.characters.includes(culprit.id))) {
    err(`Fairness: Keine Schlüssel-Erkenntnis belastet den Täter "${culprit.name}" direkt (characters-Feld).`);
  }
  const suspects = def.characters.filter((c) => c.role === 'suspect');
  if (suspects.length < 3) err('Ein Fall braucht mindestens drei Verdächtige.');
  if (sol.redHerrings.length === 0) warn('Keine falschen Fährten definiert.');

  for (const i of def.insights) if (!insightSources.has(i.id)) err(`Erkenntnis "${i.id}" kann durch nichts aufgedeckt werden.`);

  /* ---------- Zeitlinie ---------- */
  const timelineInsights = def.insights.filter((i) => i.timeline).sort((a, b) => a.timeline!.sort - b.timeline!.sort);
  const sorts = new Set<number>();
  for (const i of timelineInsights) {
    if (sorts.has(i.timeline!.sort)) warn(`Zeitlinie: doppelter Sortierwert ${i.timeline!.sort} (${i.id}).`);
    sorts.add(i.timeline!.sort);
  }
  const hhmm = (s: string) => {
    const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
    return m ? Number(m[1]) * 60 + Number(m[2]) : null;
  };
  let prev: number | null = null;
  for (const i of timelineInsights) {
    const v = hhmm(i.timeline!.time);
    if (v !== null && prev !== null && v < prev && prev - v < 12 * 60) warn(`Zeitlinie: "${i.id}" (${i.timeline!.time}) liegt vor dem vorherigen Eintrag, obwohl der Sortierwert größer ist.`);
    if (v !== null) prev = v;
  }
  if (timelineInsights.length < 3) warn('Zeitlinie: weniger als drei rekonstruierbare Zeitpunkte.');

  if (errors.length) return { ok: false, errors, warnings, stats: { ...emptyStats }, def };

  /* ---------- Simulation ---------- */
  const sim = simulate(def, 0);
  const reached = sim.insights;
  let simWrongCache: ReturnType<typeof simulate> | undefined;
  const simWrong = () => (simWrongCache ??= simulate(def, 3));
  for (const i of def.insights) if (!reached.has(i.id) && !simWrong().insights.has(i.id)) err(`Unerreichbar: Erkenntnis "${i.id}" (${i.title}).`);
  for (const e of def.evidence) if (!sim.evidence.has(e.id)) {
    if (simWrong().evidence.has(e.id)) warn(`Beweis "${e.id}" ist nur nach falscher Anschuldigung erreichbar.`);
    else err(`Unerreichbar: Beweis "${e.id}" (${e.title}).`);
  }
  for (const p of def.puzzles) if (!sim.puzzles.has(p.id)) err(`Unlösbar/unerreichbar: Rätsel "${p.id}" (${p.title}).`);
  for (const t of topics) if (!sim.topics.has(t)) err(`Unerreichbar: Vernehmungsfrage "${t}".`);
  for (const c of def.characters) if (!sim.characters.has(c.id)) err(`Unerreichbar: Person "${c.id}".`);
  for (const e of def.events) if (!sim.events.has(e.id) && !simWrong().events.has(e.id)) err(`Ereignis "${e.id}" kann nie ausgelöst werden.`);
  for (const k of sol.keyInsights) if (!reached.has(k)) err(`Fairness: Schlüssel-Erkenntnis "${k}" ist ohne falsche Anschuldigung nicht erreichbar.`);
  for (const r of sol.redHerrings) if (!reached.has(r.debunkedBy)) err(`Falsche Fährte "${r.clue}" lässt sich nicht fair auflösen.`);
  for (const it of def.interrogations)
    for (const t of it.topics)
      t.responses.forEach((r, idx) => {
        if (!sim.responses.has(`${it.character}.${t.id}#${idx}`)) warn(`Antwort ${it.character}.${t.id}#${idx} wird nie ausgewählt (verdeckt durch frühere Antwort?).`);
      });

  /* ---------- Umfang ---------- */
  const g = GUIDE[def.difficulty];
  const inRange = (n: number, [a, b]: [number, number], label: string) => {
    if (n < a || n > b) warn(`Umfang: ${n} ${label} (Richtwert ${def.difficulty}: ${a}–${b}).`);
  };
  inRange(suspects.length, g.suspects, 'Verdächtige');
  inRange(def.evidence.length, g.evidence, 'Beweismittel');
  inRange(def.puzzles.length, g.puzzles, 'Rätsel');

  const statements =
    def.evidence.filter((e) => e.content.kind === 'audio' || (e.content.kind === 'document' && e.content.docType === 'statement')).length +
    def.interrogations.length;
  return {
    ok: errors.length === 0,
    errors,
    warnings,
    def,
    stats: {
      suspects: suspects.length,
      characters: def.characters.length,
      evidence: def.evidence.length,
      insights: def.insights.length,
      puzzles: def.puzzles.length,
      statements,
      connections: def.connections.length,
      events: def.events.length,
      redHerrings: sol.redHerrings.length,
      reachableInsights: reached.size,
    },
  };
}

/** Perfektes Ermittlerteam: führt alles aus, was möglich ist, bis zum Fixpunkt. */
export function simulate(def: CaseDefinition, wrongAccusations: number) {
  const state = createInitialState(def);
  const engine = new GameEngine(def, state, { timedEvents: true });
  const T0 = 1_000_000;
  engine.now = () => T0 + 24 * 3600_000; // unbegrenzte Spielzeit
  state.status = 'active';
  state.runningSince = T0;
  state.phaseIndex = def.phases.length - 1; // Spielleitung kann jede Phase erreichen
  for (let i = 0; i < wrongAccusations; i++) state.accusations.push({ suspect: '_', correct: false, at: 0, via: 'sim' });
  const actor = { kind: 'viewer' as const, name: 'sim', participantId: 'sim' };
  const responses = new Set<string>();
  const topicsAsked = new Set<string>();

  const snapshot = () => JSON.stringify([state.insights, state.puzzles, state.events, state.topics, state.connections, state.marks, state.announcedEvidence]);
  const askAll = () => {
    for (const [charId, ts] of computeAvailability(def, state, engine.now()).topics) {
      for (const t of ts) {
        const r = engine.ask(charId, t, actor);
        if (r.ok) {
          topicsAsked.add(`${charId}.${t}`);
          responses.add(`${charId}.${t}#${(r.data as { responseIndex: number }).responseIndex}`);
        }
      }
    }
  };
  // Schrittweise: nach jeder einzelnen Entdeckung werden alle Fragen erneut gestellt,
  // damit auch Antworten erfasst werden, die nur in Zwischenständen auftreten.
  const actions = (): (() => boolean)[] => {
    const list: (() => boolean)[] = [];
    const avail = computeAvailability(def, state, engine.now());
    for (const e of def.evidence) if (avail.evidence.has(e.id)) for (const h of e.hotspots) if (!state.marks[`${e.id}:${h.item}`]) list.push(() => engine.markItem(e.id, h.item, actor).ok);
    for (const c of def.connections) if (!state.connections[c.id]) list.push(() => engine.connect(c.a, c.b, actor).ok);
    for (const p of def.puzzles) {
      if (!avail.puzzles.has(p.id) || state.puzzles[p.id]?.solvedAt !== undefined) continue;
      const answer = 'accept' in p.answer ? p.answer.accept[0] : 'choice' in p.answer ? p.answer.choice : p.answer.order;
      list.push(() => engine.solvePuzzle(p.id, answer, actor).ok);
    }
    for (const ev of avail.events) list.push(() => engine.fireEvent(ev).ok);
    return list;
  };
  for (let round = 0; round < 2000; round++) {
    const before = snapshot();
    engine.settle({ ok: true, message: '', discoveries: [], awards: [] });
    askAll();
    for (const act of actions()) {
      const pre = snapshot();
      act();
      if (snapshot() !== pre) break;
    }
    if (snapshot() === before) break;
  }
  const avail = computeAvailability(def, state, engine.now());
  return {
    insights: new Set(Object.keys(state.insights)),
    evidence: avail.evidence,
    puzzles: new Set(Object.entries(state.puzzles).filter(([, p]) => p.solvedAt !== undefined).map(([k]) => k)),
    topics: topicsAsked,
    characters: avail.characters,
    events: new Set(Object.keys(state.events)),
    responses,
  };
}
