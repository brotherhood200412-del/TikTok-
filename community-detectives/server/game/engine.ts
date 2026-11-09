/**
 * Deterministische Spiel-Engine.
 *
 * Die Engine kennt die vollständige Wahrheit eines Falls und verändert den
 * Spielstand ausschließlich über definierte Aktionen. Sie enthält keinerlei
 * Zufall und keine KI – gleiche Eingaben führen immer zum gleichen Ergebnis.
 */
import type { CaseDefinition, Condition, Puzzle } from '../../shared/case/schema.js';
import type { FeedEntry, Mood, SessionStatus } from '../../shared/views.js';
import { evaluate, type ConditionContext } from './conditions.js';

export interface Actor {
  participantId?: string;
  name?: string;
  /** 'streamer' für Aktionen der Spielleitung */
  kind: 'viewer' | 'streamer' | 'system' | 'community';
}

export interface Discovery {
  at: number; // Spielzeit in ms
  by?: string;
  byId?: string;
  via: 'start' | 'hotspot' | 'connection' | 'puzzle' | 'interrogation' | 'event' | 'streamer';
}

export interface GameState {
  v: 1;
  status: SessionStatus;
  phaseIndex: number;
  elapsedMs: number;
  runningSince: number | null;
  insights: Record<string, Discovery>;
  manualEvidence: string[];
  announcedEvidence: string[];
  announcedCharacters: string[];
  puzzles: Record<string, { solvedAt?: number; by?: string; byId?: string; hints: number; attempts: number }>;
  topics: Record<string, { at: number; response: number }>;
  events: Record<string, { at: number }>;
  connections: Record<string, { at: number; by?: string; byId?: string }>;
  marks: Record<string, { at: number; by?: string; byId?: string }>;
  interrogation: { character: string; last?: { topic: string; response: number } } | null;
  spotlight: { type: 'evidence' | 'character' | 'insight' | 'puzzle'; id: string } | null;
  task: string | null;
  stress: Record<string, number>;
  accusations: { suspect: string; correct: boolean; at: number; proof?: string; proofCorrect?: boolean; via: string }[];
  feed: FeedEntry[];
  feedSeq: number;
  pausedFrom?: SessionStatus;
}

export interface Award {
  participantId: string;
  amount: number;
  reason: string;
  ref: string;
}

export interface ActionResult {
  ok: boolean;
  code?: string;
  message: string;
  discoveries: { kind: 'insight' | 'evidence' | 'event' | 'character' | 'puzzle'; id: string; title: string }[];
  awards: Award[];
  data?: Record<string, unknown>;
}

export const POINTS = {
  hotspot: 30,
  connection: 40,
  puzzle: 60,
  puzzleHintPenalty: 10,
  puzzleMin: 20,
} as const;

const FEED_LIMIT = 80;

export function createInitialState(def: CaseDefinition): GameState {
  const state: GameState = {
    v: 1,
    status: 'lobby',
    phaseIndex: 0,
    elapsedMs: 0,
    runningSince: null,
    insights: {},
    manualEvidence: [],
    announcedEvidence: [],
    announcedCharacters: [],
    puzzles: {},
    topics: {},
    events: {},
    connections: {},
    marks: {},
    interrogation: null,
    spotlight: null,
    task: def.phases[0]?.goal ?? null,
    stress: {},
    accusations: [],
    feed: [],
    feedSeq: 0,
  };
  const avail = computeAvailability(def, state, 0);
  state.announcedEvidence = [...avail.evidence];
  state.announcedCharacters = [...avail.characters];
  return state;
}

export function normalizeAnswer(s: string): string {
  return s
    .toLowerCase()
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/ß/g, 'ss')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]/g, '');
}

export function gameMs(state: GameState, now: number): number {
  return state.elapsedMs + (state.runningSince !== null ? Math.max(0, now - state.runningSince) : 0);
}

export interface Availability {
  evidence: Set<string>;
  characters: Set<string>;
  puzzles: Set<string>;
  topics: Map<string, string[]>; // character -> topicIds
  events: Set<string>; // auslösbar, aber noch nicht ausgelöst
  ctx: ConditionContext;
}

export function buildContext(def: CaseDefinition, state: GameState, now: number, evidence: Set<string>): ConditionContext {
  return {
    insights: new Set(Object.keys(state.insights)),
    evidence,
    puzzles: new Set(Object.entries(state.puzzles).filter(([, p]) => p.solvedAt !== undefined).map(([k]) => k)),
    events: new Set(Object.keys(state.events)),
    topics: new Set(Object.keys(state.topics)),
    phaseIndex: state.phaseIndex,
    phaseOrder: def.phases.map((p) => p.id),
    minutes: Math.floor(gameMs(state, now) / 60000),
    wrongAccusations: state.accusations.filter((a) => !a.correct).length,
  };
}

export function computeAvailability(def: CaseDefinition, state: GameState, now: number): Availability {
  // Fixpunkt: Beweise können von anderen Beweisen abhängen.
  let evidence = new Set<string>(state.manualEvidence);
  for (let pass = 0; pass < def.evidence.length + 1; pass++) {
    const ctx = buildContext(def, state, now, evidence);
    const next = new Set<string>(state.manualEvidence);
    for (const e of def.evidence) if (evaluate(e.unlock, ctx)) next.add(e.id);
    if (next.size === evidence.size && [...next].every((x) => evidence.has(x))) break;
    evidence = next;
  }
  const ctx = buildContext(def, state, now, evidence);
  const characters = new Set(def.characters.filter((c) => evaluate(c.unlock, ctx)).map((c) => c.id));
  const puzzles = new Set(def.puzzles.filter((p) => evaluate(p.unlock, ctx)).map((p) => p.id));
  const topics = new Map<string, string[]>();
  for (const it of def.interrogations) {
    if (!characters.has(it.character)) continue;
    topics.set(
      it.character,
      it.topics.filter((t) => evaluate(t.unlock, ctx)).map((t) => t.id),
    );
  }
  const events = new Set(
    def.events.filter((e) => !state.events[e.id] && evaluate(e.trigger.when, ctx)).map((e) => e.id),
  );
  return { evidence, characters, puzzles, topics, events, ctx };
}

/* ------------------------------------------------------------------ */

export class GameEngine {
  private insightIdx: Map<string, CaseDefinition['insights'][number]>;
  constructor(
    public readonly def: CaseDefinition,
    public state: GameState,
    private opts: { timedEvents: boolean } = { timedEvents: true },
  ) {
    this.insightIdx = new Map(def.insights.map((i) => [i.id, i]));
  }

  setOptions(opts: { timedEvents: boolean }) {
    this.opts = opts;
  }

  now(): number {
    return Date.now();
  }

  availability(now = this.now()) {
    return computeAvailability(this.def, this.state, now);
  }

  private result(ok: boolean, message: string, extra: Partial<ActionResult> = {}): ActionResult {
    return { ok, message, discoveries: [], awards: [], ...extra };
  }

  private t(now = this.now()) {
    return gameMs(this.state, now);
  }

  pushFeed(type: FeedEntry['type'], text: string, extra: Partial<FeedEntry> = {}) {
    this.state.feedSeq += 1;
    this.state.feed.push({ id: this.state.feedSeq, at: this.t(), type, text, ...extra });
    if (this.state.feed.length > FEED_LIMIT) this.state.feed.splice(0, this.state.feed.length - FEED_LIMIT);
  }

  private requirePlayable(): ActionResult | null {
    if (this.state.status === 'active' || this.state.status === 'finale') return null;
    if (this.state.status === 'paused') return this.result(false, 'Die Ermittlung ist pausiert.', { code: 'paused' });
    if (this.state.status === 'lobby') return this.result(false, 'Die Ermittlung hat noch nicht begonnen.', { code: 'not_started' });
    return this.result(false, 'Der Fall ist abgeschlossen.', { code: 'closed' });
  }

  /** Erkenntnis aufdecken und Folgeereignisse abarbeiten. */
  revealInsight(id: string, actor: Actor, via: Discovery['via'], res: ActionResult): boolean {
    if (this.state.insights[id]) return false;
    const ins = this.insightIdx.get(id);
    if (!ins) return false;
    this.state.insights[id] = { at: this.t(), by: actor.name, byId: actor.participantId, via };
    res.discoveries.push({ kind: 'insight', id, title: ins.title });
    this.pushFeed('insight', ins.title, { by: actor.name, ref: id });
    return true;
  }

  /** Nach jeder Änderung: neue Beweise/Personen melden, automatische Ereignisse auslösen. */
  settle(res: ActionResult, now = this.now()) {
    for (let guard = 0; guard < 50; guard++) {
      const avail = this.availability(now);
      let changed = false;
      for (const ev of this.def.events) {
        if (this.state.events[ev.id] || !avail.events.has(ev.id)) continue;
        const timed = ev.trigger.minutes !== undefined;
        if (timed && !this.opts.timedEvents) continue; // nur manuell auslösbar
        if (timed && avail.ctx.minutes < (ev.trigger.minutes ?? 0)) continue;
        if (!timed && ev.trigger.when === undefined) continue; // reine Spielleiter-Ereignisse
        if (this.state.status !== 'active' && this.state.status !== 'finale') continue;
        this.fireEventInternal(ev.id, res);
        changed = true;
      }
      if (!changed) break;
    }
    const avail = this.availability(now);
    for (const id of avail.evidence) {
      if (!this.state.announcedEvidence.includes(id)) {
        this.state.announcedEvidence.push(id);
        const e = this.def.evidence.find((x) => x.id === id)!;
        res.discoveries.push({ kind: 'evidence', id, title: e.title });
        this.pushFeed('evidence', e.title, { ref: id });
      }
    }
    for (const id of avail.characters) {
      if (!this.state.announcedCharacters.includes(id)) {
        this.state.announcedCharacters.push(id);
        const c = this.def.characters.find((x) => x.id === id)!;
        res.discoveries.push({ kind: 'character', id, title: c.name });
        this.pushFeed('character', c.name, { ref: id });
      }
    }
  }

  private fireEventInternal(id: string, res: ActionResult) {
    const ev = this.def.events.find((e) => e.id === id)!;
    this.state.events[id] = { at: this.t() };
    res.discoveries.push({ kind: 'event', id, title: ev.title });
    this.pushFeed('event', ev.title, { ref: id, detail: ev.text });
    for (const ins of ev.reveals) this.revealInsight(ins, { kind: 'system' }, 'event', res);
  }

  /* ---------------------------- Spielleitung ---------------------------- */

  start(now = this.now()): ActionResult {
    const res = this.result(true, 'Ermittlung gestartet.');
    if (this.state.status !== 'lobby') return this.result(false, 'Bereits gestartet.', { code: 'state' });
    this.state.status = 'active';
    this.state.runningSince = now;
    this.pushFeed('system', 'Die Ermittlung beginnt.');
    this.settle(res, now);
    return res;
  }

  pause(now = this.now()): ActionResult {
    if (this.state.status !== 'active' && this.state.status !== 'finale') return this.result(false, 'Nicht aktiv.', { code: 'state' });
    this.state.elapsedMs = gameMs(this.state, now);
    this.state.runningSince = null;
    this.state.pausedFrom = this.state.status;
    this.state.status = 'paused';
    this.pushFeed('system', 'Ermittlung pausiert.');
    return this.result(true, 'Pausiert.');
  }

  resume(now = this.now()): ActionResult {
    if (this.state.status !== 'paused') return this.result(false, 'Nicht pausiert.', { code: 'state' });
    const from = this.state.pausedFrom ?? 'active';
    this.state.status = from === 'finale' ? 'finale' : 'active';
    this.state.runningSince = now;
    this.pushFeed('system', 'Ermittlung fortgesetzt.');
    const res = this.result(true, 'Fortgesetzt.');
    this.settle(res, now);
    return res;
  }

  /** Nach Server-Neustart: Laufzeit nicht für die Ausfallzeit zählen. */
  freezeClock(now = this.now()) {
    this.state.elapsedMs = gameMs(this.state, now);
    if (this.state.runningSince !== null) this.state.runningSince = now;
  }

  setPhase(phaseId: string): ActionResult {
    const idx = this.def.phases.findIndex((p) => p.id === phaseId);
    if (idx < 0) return this.result(false, 'Unbekannte Phase.', { code: 'not_found' });
    const res = this.result(true, `Phase: ${this.def.phases[idx].title}`);
    this.state.phaseIndex = idx;
    this.state.task = this.def.phases[idx].goal;
    this.pushFeed('phase', this.def.phases[idx].title, { detail: this.def.phases[idx].goal });
    this.settle(res);
    return res;
  }

  setTask(task: string | null): ActionResult {
    this.state.task = task && task.trim() ? task.trim().slice(0, 200) : null;
    return this.result(true, 'Aufgabe aktualisiert.');
  }

  setSpotlight(spot: GameState['spotlight']): ActionResult {
    if (spot) {
      const avail = this.availability();
      const ok =
        (spot.type === 'evidence' && avail.evidence.has(spot.id)) ||
        (spot.type === 'character' && avail.characters.has(spot.id)) ||
        (spot.type === 'insight' && !!this.state.insights[spot.id]) ||
        (spot.type === 'puzzle' && avail.puzzles.has(spot.id));
      if (!ok) return this.result(false, 'Dieses Element ist (noch) nicht freigeschaltet.', { code: 'locked' });
    }
    this.state.spotlight = spot;
    return this.result(true, 'Fokus gesetzt.');
  }

  unlockEvidence(id: string): ActionResult {
    if (!this.def.evidence.some((e) => e.id === id)) return this.result(false, 'Unbekanntes Beweismittel.', { code: 'not_found' });
    if (!this.state.manualEvidence.includes(id)) this.state.manualEvidence.push(id);
    const res = this.result(true, 'Beweismittel freigegeben.');
    this.settle(res);
    return res;
  }

  fireEvent(id: string): ActionResult {
    const ev = this.def.events.find((e) => e.id === id);
    if (!ev) return this.result(false, 'Unbekanntes Ereignis.', { code: 'not_found' });
    if (this.state.events[id]) return this.result(false, 'Ereignis wurde bereits ausgelöst.', { code: 'duplicate' });
    const avail = this.availability();
    if (!avail.events.has(id)) return this.result(false, 'Die Voraussetzungen für dieses Ereignis sind noch nicht erfüllt.', { code: 'locked' });
    const res = this.result(true, `Ereignis „${ev.title}“ ausgelöst.`);
    this.fireEventInternal(id, res);
    this.settle(res);
    return res;
  }

  /** Zeitgesteuerte Ereignisse prüfen (wird regelmäßig vom Server aufgerufen). */
  tick(now = this.now()): ActionResult {
    const res = this.result(true, 'tick');
    if (this.state.status === 'active' || this.state.status === 'finale') this.settle(res, now);
    return res;
  }

  /* ---------------------------- Ermittlung ---------------------------- */

  markItem(evidenceId: string, itemId: string, actor: Actor): ActionResult {
    const blocked = this.requirePlayable();
    if (blocked) return blocked;
    const ev = this.def.evidence.find((e) => e.id === evidenceId);
    if (!ev || !this.availability().evidence.has(evidenceId)) return this.result(false, 'Beweismittel nicht verfügbar.', { code: 'locked' });
    if (!itemIds(ev.content).includes(itemId)) return this.result(false, 'Unbekanntes Detail.', { code: 'not_found' });
    const hs = ev.hotspots.find((h) => h.item === itemId);
    const key = `${evidenceId}:${itemId}`;
    if (!hs) return this.result(false, 'Nichts Auffälliges – zumindest nicht für sich allein.', { code: 'miss' });
    if (this.state.marks[key]) {
      return this.result(true, 'Dieses Detail hat das Team bereits gesichert.', { code: 'known', data: { insight: hs.insight } });
    }
    this.state.marks[key] = { at: this.t(), by: actor.name, byId: actor.participantId };
    const res = this.result(true, hs.feedback ?? 'Treffer! Ein wichtiges Detail.');
    const isNew = this.revealInsight(hs.insight, actor, 'hotspot', res);
    if (isNew && actor.participantId) res.awards.push({ participantId: actor.participantId, amount: POINTS.hotspot, reason: 'hotspot', ref: key });
    this.settle(res);
    res.data = { insight: hs.insight };
    return res;
  }

  connect(a: string, b: string, actor: Actor): ActionResult {
    const blocked = this.requirePlayable();
    if (blocked) return blocked;
    if (a === b) return this.result(false, 'Wähle zwei verschiedene Elemente.', { code: 'invalid' });
    const avail = this.availability();
    const known = (x: string) => avail.evidence.has(x) || !!this.state.insights[x] || avail.characters.has(x);
    if (!known(a) || !known(b)) return this.result(false, 'Mindestens ein Element ist nicht verfügbar.', { code: 'locked' });
    const conn = this.def.connections.find((c) => (c.a === a && c.b === b) || (c.a === b && c.b === a));
    if (!conn) return this.result(false, 'Diese Verbindung ergibt (noch) keinen Sinn.', { code: 'miss' });
    if (this.state.connections[conn.id]) return this.result(true, 'Diese Verbindung kennt das Team bereits.', { code: 'known' });
    this.state.connections[conn.id] = { at: this.t(), by: actor.name, byId: actor.participantId };
    const res = this.result(true, 'Verbindung bestätigt!');
    this.revealInsight(conn.insight, actor, 'connection', res);
    if (actor.participantId) res.awards.push({ participantId: actor.participantId, amount: POINTS.connection, reason: 'connection', ref: conn.id });
    this.settle(res);
    return res;
  }

  checkAnswer(p: Puzzle, answer: unknown): boolean {
    if ('accept' in p.answer) {
      if (typeof answer !== 'string') return false;
      const n = normalizeAnswer(answer);
      return n.length > 0 && p.answer.accept.some((a) => normalizeAnswer(a) === n);
    }
    if ('choice' in p.answer) return answer === p.answer.choice;
    if ('order' in p.answer) {
      return Array.isArray(answer) && answer.length === p.answer.order.length && p.answer.order.every((x, i) => answer[i] === x);
    }
    return false;
  }

  solvePuzzle(puzzleId: string, answer: unknown, actor: Actor): ActionResult {
    const blocked = this.requirePlayable();
    if (blocked) return blocked;
    const p = this.def.puzzles.find((x) => x.id === puzzleId);
    if (!p || !this.availability().puzzles.has(puzzleId)) return this.result(false, 'Rätsel nicht verfügbar.', { code: 'locked' });
    const ps = (this.state.puzzles[puzzleId] ??= { hints: 0, attempts: 0 });
    if (ps.solvedAt !== undefined) return this.result(true, 'Bereits gelöst.', { code: 'known' });
    ps.attempts += 1;
    if (!this.checkAnswer(p, answer)) return this.result(false, 'Das passt nicht. Prüft die Beweise noch einmal.', { code: 'wrong' });
    ps.solvedAt = this.t();
    ps.by = actor.name;
    ps.byId = actor.participantId;
    const res = this.result(true, p.success);
    this.pushFeed('puzzle', p.title, { by: actor.name, ref: p.id });
    res.discoveries.push({ kind: 'puzzle', id: p.id, title: p.title });
    for (const ins of p.reveals) this.revealInsight(ins, actor, 'puzzle', res);
    if (actor.participantId) {
      const amount = Math.max(POINTS.puzzleMin, POINTS.puzzle - ps.hints * POINTS.puzzleHintPenalty);
      res.awards.push({ participantId: actor.participantId, amount, reason: 'puzzle', ref: p.id });
    }
    this.settle(res);
    return res;
  }

  revealHint(puzzleId: string): ActionResult {
    const p = this.def.puzzles.find((x) => x.id === puzzleId);
    if (!p || !this.availability().puzzles.has(puzzleId)) return this.result(false, 'Rätsel nicht verfügbar.', { code: 'locked' });
    const ps = (this.state.puzzles[puzzleId] ??= { hints: 0, attempts: 0 });
    if (ps.solvedAt !== undefined) return this.result(false, 'Rätsel ist bereits gelöst.', { code: 'known' });
    if (ps.hints >= p.hints.length) return this.result(false, 'Keine weiteren Hinweise vorhanden.', { code: 'exhausted' });
    ps.hints += 1;
    this.pushFeed('hint', `Hinweis ${ps.hints}/${p.hints.length} zu „${p.title}“`, { detail: p.hints[ps.hints - 1], ref: p.id });
    return this.result(true, p.hints[ps.hints - 1]);
  }

  /** Spielleitung kann ein Rätsel auflösen, falls die Community feststeckt (keine Punkte). */
  forceSolvePuzzle(puzzleId: string): ActionResult {
    const p = this.def.puzzles.find((x) => x.id === puzzleId);
    if (!p) return this.result(false, 'Unbekanntes Rätsel.', { code: 'not_found' });
    const ps = (this.state.puzzles[puzzleId] ??= { hints: 0, attempts: 0 });
    if (ps.solvedAt !== undefined) return this.result(false, 'Bereits gelöst.', { code: 'known' });
    ps.solvedAt = this.t();
    ps.by = 'Spielleitung';
    const res = this.result(true, p.success);
    this.pushFeed('puzzle', p.title, { by: 'Spielleitung', ref: p.id });
    for (const ins of p.reveals) this.revealInsight(ins, { kind: 'streamer', name: 'Spielleitung' }, 'streamer', res);
    this.settle(res);
    return res;
  }

  startInterrogation(characterId: string): ActionResult {
    const it = this.def.interrogations.find((i) => i.character === characterId);
    if (!it) return this.result(false, 'Diese Person kann nicht vernommen werden.', { code: 'not_found' });
    if (!this.availability().characters.has(characterId)) return this.result(false, 'Person noch nicht bekannt.', { code: 'locked' });
    this.state.interrogation = { character: characterId };
    this.state.spotlight = { type: 'character', id: characterId };
    const c = this.def.characters.find((x) => x.id === characterId)!;
    this.pushFeed('interrogation', `Vernehmung: ${c.name}`, { ref: characterId, detail: it.intro });
    return this.result(true, `Vernehmung von ${c.name} gestartet.`);
  }

  endInterrogation(): ActionResult {
    this.state.interrogation = null;
    if (this.state.spotlight?.type === 'character') this.state.spotlight = null;
    return this.result(true, 'Vernehmung beendet.');
  }

  ask(characterId: string, topicId: string, actor: Actor): ActionResult {
    const blocked = this.requirePlayable();
    if (blocked) return blocked;
    const it = this.def.interrogations.find((i) => i.character === characterId);
    const topic = it?.topics.find((t) => t.id === topicId);
    if (!it || !topic) return this.result(false, 'Unbekannte Frage.', { code: 'not_found' });
    const avail = this.availability();
    if (!avail.topics.get(characterId)?.includes(topicId)) return this.result(false, 'Diese Frage ist noch nicht möglich.', { code: 'locked' });
    const idx = topic.responses.findIndex((r) => evaluate(r.when, avail.ctx));
    const response = topic.responses[idx === -1 ? topic.responses.length - 1 : idx];
    const responseIndex = topic.responses.indexOf(response);
    const key = `${characterId}.${topicId}`;
    this.state.topics[key] = { at: this.t(), response: responseIndex };
    this.state.interrogation = { character: characterId, last: { topic: topicId, response: responseIndex } };
    this.state.stress[characterId] = Math.min(100, Math.max(this.state.stress[characterId] ?? 0, response.stress));
    const c = this.def.characters.find((x) => x.id === characterId)!;
    const res = this.result(true, response.text, { data: { mood: response.mood as Mood, responseIndex } });
    this.pushFeed('answer', `${c.name}: „${topic.question}“`, { ref: key, detail: response.text, mood: response.mood as Mood });
    if (response.reveals) this.revealInsight(response.reveals, actor.kind === 'viewer' ? actor : { kind: 'community', name: actor.name ?? 'Community' }, 'interrogation', res);
    this.settle(res);
    return res;
  }

  /* ---------------------------- Finale ---------------------------- */

  enterFinale(): ActionResult {
    if (this.state.status !== 'active') return this.result(false, 'Das Finale kann nur aus einer laufenden Ermittlung gestartet werden.', { code: 'state' });
    this.state.status = 'finale';
    this.state.task = this.def.accusation.question;
    this.pushFeed('phase', 'Finale: Die Anklage', { detail: this.def.accusation.question });
    return this.result(true, 'Finale gestartet.');
  }

  cancelFinale(): ActionResult {
    if (this.state.status !== 'finale') return this.result(false, 'Kein Finale aktiv.', { code: 'state' });
    this.state.status = 'active';
    this.state.task = this.def.phases[this.state.phaseIndex].goal;
    return this.result(true, 'Zurück zur Ermittlung.');
  }

  accuse(suspectId: string, proofId: string | undefined, via: string): ActionResult {
    if (this.state.status !== 'finale' && this.state.status !== 'active') return this.result(false, 'Jetzt ist keine Anklage möglich.', { code: 'state' });
    const c = this.def.characters.find((x) => x.id === suspectId && x.role === 'suspect');
    if (!c) return this.result(false, 'Unbekannte verdächtige Person.', { code: 'not_found' });
    const correct = suspectId === this.def.solution.culprit;
    const proofOpt = this.def.accusation.proof?.options.find((o) => o.id === proofId);
    const entry = { suspect: suspectId, correct, at: this.t(), proof: proofId, proofCorrect: proofOpt ? proofOpt.correct : undefined, via };
    this.state.accusations.push(entry);
    const res = this.result(true, correct ? 'Die Anklage sitzt.' : 'Die Anklage hält nicht stand.', { data: { correct } });
    if (correct) {
      this.state.status = 'solved';
      this.pushFeed('accusation', `Anklage gegen ${c.name}: Treffer!`, { ref: suspectId });
    } else {
      this.state.status = 'active';
      this.state.task = 'Die Anklage ist geplatzt. Neue Spuren prüfen!';
      const accomplice = this.def.solution.accomplices.includes(suspectId);
      this.pushFeed('accusation', accomplice ? `Anklage gegen ${c.name}: mitschuldig – aber nicht hauptverantwortlich!` : `Anklage gegen ${c.name} gescheitert.`, { ref: suspectId });
      res.data = { correct, accomplice };
      this.settle(res);
    }
    return res;
  }

  reveal(now = this.now()): ActionResult {
    if (this.state.status === 'revealed' || this.state.status === 'ended') return this.result(false, 'Bereits aufgelöst.', { code: 'state' });
    this.state.elapsedMs = gameMs(this.state, now);
    this.state.runningSince = null;
    this.state.status = 'revealed';
    this.state.spotlight = null;
    this.state.interrogation = null;
    this.state.task = 'Auflösung';
    this.pushFeed('reveal', this.def.solution.headline);
    return this.result(true, 'Auflösung angezeigt.');
  }

  end(): ActionResult {
    this.state.status = 'ended';
    this.state.runningSince = null;
    return this.result(true, 'Sitzung beendet.');
  }
}

export function itemIds(content: CaseDefinition['evidence'][number]['content']): string[] {
  switch (content.kind) {
    case 'document':
    case 'audio':
      return content.lines.map((l) => l.id);
    case 'photo':
      return content.elements.map((e) => e.id);
    case 'map':
      return [...content.places.map((p) => p.id), ...content.routes.map((r) => r.id)];
    case 'messages':
      return content.messages.map((m) => m.id);
    case 'table':
      return content.rows.map((r) => r.id);
    case 'object':
      return content.details.map((d) => d.id);
  }
}

export type { Condition };
