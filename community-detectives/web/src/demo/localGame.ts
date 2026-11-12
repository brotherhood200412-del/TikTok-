/**
 * Browser-Vorschau: dieselbe Spiel-Engine wie auf dem Server, aber komplett
 * im Browser. Ersetzt Server, Datenbank und Socket.IO durch einen lokalen
 * Spielstand (gespeichert im Browser). Für die Vorschau ohne Hosting.
 */
import { parse } from 'yaml';
import { caseSchema, type CaseDefinition } from '../../../shared/case/schema';
import { TEAMS, type DiscussionMessage, type OverlayView, type PersonalState, type PublicCaseView, type PublicTheory, type PublicVote } from '../../../shared/views';
import { matchName, matchTeam, parseChatCommand } from '../../../server/game/commands';
import { GameEngine, createInitialState, gameMs, type ActionResult, type Award, type GameState } from '../../../server/game/engine';
import { buildGameView, buildStreamerSecrets } from '../../../server/game/projection';
import type { AckResult, Handshake, LocalConnection, LocalHandlers, LocalTransport } from '../lib/live';
import einbruch from '../../../content/cases/der-perfekte-einbruch.yaml?raw';
import zug from '../../../content/cases/der-letzte-zug.yaml?raw';
import identitaet from '../../../content/cases/die-verschwundene-identitaet.yaml?raw';
import villa from '../../../content/cases/villa-falkenstein.yaml?raw';
import akte from '../../../content/cases/akte-1987.yaml?raw';

export const CASES: CaseDefinition[] = [einbruch, zug, identitaet, villa, akte].map((y) => caseSchema.parse(parse(y)));

const STORE_KEY = 'cd_demo_v1';
const ME = 'me';

interface Participant {
  id: string;
  name: string;
  points: number;
  team: string | null;
  source: 'web' | 'chat';
}
interface Vote {
  id: string;
  kind: string;
  question: string;
  options: { label: string; ref?: string }[];
  ballots: Record<string, number>;
  endsAt: number;
  status: 'open' | 'closed' | 'cancelled';
  winner?: number;
  tie?: number[];
  applied?: boolean;
}
interface Saved {
  caseId: string;
  code: string;
  myName: string;
  state: GameState;
  participants: Participant[];
  awards: string[];
  theories: (PublicTheory & { upvoters: string[] })[];
  messages: DiscussionMessage[];
  vote: Vote | null;
  lastVote: Vote | null;
  settings: Record<string, any>;
}

const DEFAULT_SETTINGS = {
  allowGuests: true,
  guestsCanVote: true,
  discussion: true,
  theories: true,
  timedEvents: true,
  bareNumberVotes: true,
  chatReplies: true,
  voteSeconds: 45,
  autoApplyVotes: true,
  hintRequestThreshold: 3,
  overlay: { position: 'right', showLeaderboard: true, showFeed: true, showJoin: true, scale: 1 },
};

function load(): Saved | null {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as Saved) : null;
  } catch {
    return null;
  }
}

export class LocalGame implements LocalTransport {
  data: Saved | null = load();
  engine: GameEngine | null = null;
  def: CaseDefinition | null = null;
  private conns = new Set<{ hs: Handshake; h: LocalHandlers }>();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private voteTimer: ReturnType<typeof setTimeout> | null = null;
  private hintRequests = 0;

  constructor() {
    if (this.data) this.boot();
    setInterval(() => {
      if (!this.engine) return;
      const r = this.engine.tick();
      if (r.discoveries.length) this.apply(r);
    }, 5000);
  }

  private boot() {
    const d = this.data!;
    this.def = CASES.find((c) => c.id === d.caseId) ?? null;
    if (!this.def) {
      this.data = null;
      return;
    }
    this.engine = new GameEngine(this.def, d.state, { timedEvents: d.settings.timedEvents });
    this.engine.freezeClock();
    if (d.vote?.status === 'open') this.armVote();
  }

  /* ------------------------------ Verwaltung ------------------------------ */

  newGame(caseId: string, myName: string) {
    const def = CASES.find((c) => c.id === caseId)!;
    const code = Array.from({ length: 6 }, () => 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[Math.floor(Math.random() * 32)]).join('');
    this.data = {
      caseId,
      code,
      myName: myName || 'Ermittler',
      state: createInitialState(def),
      participants: [{ id: ME, name: myName || 'Ermittler', points: 0, team: null, source: 'web' }],
      awards: [],
      theories: [],
      messages: [],
      vote: null,
      lastVote: null,
      settings: structuredClone(DEFAULT_SETTINGS),
    };
    if (this.voteTimer) clearTimeout(this.voteTimer);
    this.boot();
    this.engine!.start();
    this.save();
    this.changed();
  }

  reset() {
    this.data = null;
    this.engine = null;
    this.def = null;
    try {
      localStorage.removeItem(STORE_KEY);
    } catch {
      /* ignore */
    }
  }

  private save() {
    if (!this.data || !this.engine) return;
    const s = this.engine.state;
    this.data.state = { ...s, elapsedMs: gameMs(s, Date.now()), runningSince: s.runningSince === null ? null : Date.now() };
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(this.data));
    } catch {
      /* Speicher nicht verfügbar – Spiel läuft trotzdem */
    }
    this.data.state = s;
  }

  private changed() {
    if (this.timer) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.save();
      for (const c of this.conns) this.push(c);
    }, 60);
  }

  private push(c: { hs: Handshake; h: LocalHandlers }) {
    if (!this.data || !this.engine) {
      c.h.fatal({ message: 'Keine Ermittlung aktiv. Starte einen Fall.', code: 'not_found' });
      return;
    }
    if (c.hs.mode === 'overlay') return c.h.overlay(this.overlayView());
    if (c.hs.mode === 'control') return c.h.snapshot(this.ownerView());
    c.h.snapshot({ ...this.publicView(), discussion: this.data.messages });
    c.h.me(this.personal());
  }

  connect(hs: Handshake, h: LocalHandlers): LocalConnection {
    const c = { hs, h };
    this.conns.add(c);
    setTimeout(() => this.push(c), 0);
    return {
      close: () => this.conns.delete(c),
      emit: async (event, action, payload) => {
        try {
          const r = event === 'control' ? await this.control(action, (payload ?? {}) as Record<string, unknown>) : event === 'mod' ? this.mod(action, payload as Record<string, any>) : this.act(action, payload as Record<string, any>);
          this.changed();
          return r;
        } catch (e) {
          return { ok: false, message: (e as Error).message, code: 'error' };
        }
      },
    };
  }

  /* ------------------------------ Punkte ------------------------------ */

  private award(a: Award) {
    const d = this.data!;
    const key = `${a.participantId}|${a.reason}|${a.ref}`;
    if (d.awards.includes(key)) return;
    d.awards.push(key);
    const p = d.participants.find((x) => x.id === a.participantId);
    if (p) p.points += a.amount;
  }

  private apply(r: ActionResult) {
    for (const a of r.awards) this.award(a);
    const ins = r.discoveries.filter((x) => x.kind === 'insight');
    if (ins.length) this.bot(`🔎 Neue Erkenntnis: ${ins.map((x) => x.title).join(' · ')}`);
    this.changed();
  }

  private bot(text: string) {
    for (const c of this.conns) if (c.hs.mode === 'control') c.h.bot({ text, at: Date.now() });
  }

  private participant(id: string, name: string, source: 'web' | 'chat') {
    const d = this.data!;
    let p = d.participants.find((x) => x.id === id);
    if (!p) {
      p = { id, name, points: 0, team: null, source };
      d.participants.push(p);
    }
    return p;
  }

  /* ------------------------------ Zuschauer ------------------------------ */

  private act(action: string, p: Record<string, any>): AckResult {
    const e = this.engine!;
    const actor = { kind: 'viewer' as const, participantId: ME, name: this.data!.myName };
    let r: ActionResult;
    switch (action) {
      case 'mark':
        r = e.markItem(String(p.evidence), String(p.item), actor);
        break;
      case 'connect':
        r = e.connect(String(p.a), String(p.b), actor);
        break;
      case 'answer':
        r = e.solvePuzzle(String(p.puzzle), p.answer, actor);
        break;
      case 'vote':
        this.castVote(ME, Number(p.option));
        return { ok: true, message: 'Stimme gezählt.' };
      case 'theory':
        this.addTheory(ME, String(p.suspect), String(p.text ?? ''), p.evidence ?? []);
        return { ok: true, message: 'Theorie eingereicht.' };
      case 'upvote': {
        const t = this.data!.theories.find((x) => x.id === p.theory);
        if (!t) throw new Error('Theorie nicht gefunden.');
        if (t.authorId === ME) throw new Error('Eigene Theorien kannst du nicht unterstützen.');
        t.upvoters = t.upvoters.includes(ME) ? t.upvoters.filter((x) => x !== ME) : [...t.upvoters, ME];
        t.upvotes = t.upvoters.length;
        return { ok: true, message: 'Gespeichert.' };
      }
      case 'message': {
        const text = String(p.text ?? '').trim().slice(0, 280);
        if (!text) throw new Error('Leere Nachricht.');
        this.data!.messages.push({ id: `m${Date.now()}`, author: this.data!.myName, authorId: ME, text, at: Date.now() });
        return { ok: true };
      }
      case 'team':
        if (!TEAMS.some((t) => t.id === p.team)) throw new Error('Unbekanntes Team.');
        this.participant(ME, this.data!.myName, 'web').team = String(p.team);
        return { ok: true, message: 'Team gewählt.' };
      case 'hint':
        this.hintRequests += 1;
        for (const c of this.conns) if (c.hs.mode === 'control') c.h.notice({ kind: 'hint', text: `${this.hintRequests} Hinweis-Anfrage(n) aus der Community.`, at: Date.now() });
        return { ok: true, message: 'Hinweis angefragt. Die Spielleitung (Streamer-Ansicht) kann ihn freigeben.' };
      default:
        throw new Error('Unbekannte Aktion.');
    }
    this.apply(r);
    return { ok: r.ok, message: r.message, code: r.code, data: r.data };
  }

  private mod(action: string, p: Record<string, any>): AckResult {
    const d = this.data!;
    if (action === 'theoryStatus') {
      const t = d.theories.find((x) => x.id === p.theory);
      if (t) {
        if (p.status === 'featured') d.theories.forEach((x) => x.status === 'featured' && (x.status = 'visible'));
        t.status = p.status;
      }
    }
    if (action === 'hideMessage') {
      const m = d.messages.find((x) => x.id === p.message);
      if (m) m.hidden = true;
    }
    return { ok: true, message: 'Erledigt.' };
  }

  private addTheory(pid: string, suspect: string, text: string, evidence: string[]) {
    const d = this.data!;
    const s = this.def!.characters.find((c) => c.id === suspect && c.role === 'suspect');
    if (!s) throw new Error('Unbekannte verdächtige Person.');
    if (text.trim().length < 10) throw new Error('Begründe deine Theorie in mindestens 10 Zeichen.');
    const p = d.participants.find((x) => x.id === pid)!;
    d.theories.push({ id: `t${Date.now()}${Math.random().toString(36).slice(2, 5)}`, author: p.name, authorId: pid, suspectId: suspect, text: text.trim().slice(0, 400), evidenceIds: evidence.slice(0, 5), upvotes: 0, status: 'visible', createdAt: Date.now(), upvoters: [] });
    this.engine!.pushFeed('theory', `${p.name} verdächtigt ${s.name}`, { by: p.name });
    this.award({ participantId: pid, amount: 5, reason: 'theory', ref: String(d.theories.filter((t) => t.authorId === pid).length) });
  }

  /* ------------------------------ Abstimmungen ------------------------------ */

  private castVote(pid: string, idx: number) {
    const v = this.data!.vote;
    if (!v || v.status !== 'open') throw new Error('Gerade läuft keine Abstimmung.');
    if (!Number.isInteger(idx) || idx < 0 || idx >= v.options.length) throw new Error('Ungültige Option.');
    v.ballots[pid] = idx;
  }

  private armVote() {
    const v = this.data!.vote!;
    if (this.voteTimer) clearTimeout(this.voteTimer);
    this.voteTimer = setTimeout(() => {
      this.closeVote();
      this.changed();
    }, Math.max(500, v.endsAt - Date.now()));
  }

  private startVote(kind: string, question?: string, options?: string[], seconds?: number) {
    const d = this.data!;
    const e = this.engine!;
    const def = this.def!;
    if (d.vote?.status === 'open') throw new Error('Es läuft bereits eine Abstimmung.');
    const avail = e.availability();
    let opts: { label: string; ref?: string }[] = [];
    let q = question?.trim() || '';
    switch (kind) {
      case 'interrogate':
        opts = def.characters.filter((c) => avail.characters.has(c.id) && def.interrogations.some((i) => i.character === c.id)).map((c) => ({ label: c.name, ref: c.id }));
        q ||= 'Wen sollen wir als Nächstes vernehmen?';
        break;
      case 'question': {
        const cur = e.state.interrogation;
        if (!cur) throw new Error('Starte zuerst eine Vernehmung.');
        const it = def.interrogations.find((i) => i.character === cur.character)!;
        const open = avail.topics.get(cur.character) ?? [];
        opts = it.topics.filter((t) => open.includes(t.id)).map((t) => ({ label: t.question, ref: t.id }));
        q ||= 'Welche Frage stellen wir?';
        break;
      }
      case 'examine':
        opts = def.evidence.filter((x) => avail.evidence.has(x.id)).map((x) => ({ label: x.title, ref: x.id }));
        q ||= 'Welches Beweisstück nehmen wir unter die Lupe?';
        break;
      case 'accuse':
        opts = def.characters.filter((c) => c.role === 'suspect' && avail.characters.has(c.id)).map((c) => ({ label: c.name, ref: c.id }));
        q ||= def.accusation.question;
        break;
      case 'proof':
        if (!def.accusation.proof) throw new Error('Dieser Fall hat keine Beweisfrage.');
        opts = def.accusation.proof.options.map((o) => ({ label: o.label, ref: o.id }));
        q ||= def.accusation.proof.question;
        break;
      case 'hint': {
        const pid = e.state.spotlight?.type === 'puzzle' ? e.state.spotlight.id : null;
        if (!pid) throw new Error('Setze zuerst ein Rätsel in den Fokus.');
        opts = [
          { label: 'Ja, Hinweis aufdecken', ref: pid },
          { label: 'Nein, wir schaffen das allein', ref: '' },
        ];
        q ||= 'Hinweis aufdecken?';
        break;
      }
      case 'custom':
        opts = (options ?? []).filter(Boolean).map((label) => ({ label }));
        if (!q) throw new Error('Bitte eine Frage angeben.');
        break;
    }
    if (opts.length < 2) throw new Error('Eine Abstimmung braucht mindestens zwei Optionen.');
    const secs = Math.min(600, Math.max(15, seconds ?? d.settings.voteSeconds));
    d.vote = { id: `v${Date.now()}`, kind, question: q, options: opts.slice(0, 9), ballots: {}, endsAt: Date.now() + secs * 1000, status: 'open' };
    e.pushFeed('vote', q);
    this.bot(`🗳️ ${q} ${d.vote.options.map((o, i) => `${i + 1}) ${o.label}`).join('  ')} → !a <Nummer>`);
    this.armVote();
  }

  private closeVote() {
    const d = this.data!;
    const v = d.vote;
    if (!v || v.status !== 'open') return;
    if (this.voteTimer) clearTimeout(this.voteTimer);
    v.status = 'closed';
    const counts = v.options.map(() => 0);
    Object.values(v.ballots).forEach((i) => counts[i]++);
    const max = Math.max(...counts);
    const leaders = counts.map((c, i) => (c === max ? i : -1)).filter((i) => i >= 0);
    if (max > 0 && leaders.length === 1) v.winner = leaders[0];
    else if (max > 0) v.tie = leaders;
    d.lastVote = v;
    d.vote = null;
    for (const pid of Object.keys(v.ballots)) this.award({ participantId: pid, amount: 2, reason: 'vote', ref: v.id });
    const label = v.winner !== undefined ? v.options[v.winner].label : v.tie ? 'Gleichstand' : 'keine Stimmen';
    this.engine!.pushFeed('vote', `Ergebnis: ${label}`);
    if (v.winner !== undefined && d.settings.autoApplyVotes) this.applyVote(v, v.winner);
  }

  private applyVote(v: Vote, index: number) {
    if (v.applied) throw new Error('Ergebnis wurde bereits angewendet.');
    v.applied = true;
    v.winner = index;
    const e = this.engine!;
    const def = this.def!;
    const opt = v.options[index];
    let r: ActionResult | null = null;
    if (v.kind === 'interrogate') r = e.startInterrogation(opt.ref!);
    if (v.kind === 'question' && e.state.interrogation) r = e.ask(e.state.interrogation.character, opt.ref!, { kind: 'community', name: 'Community' });
    if (v.kind === 'examine') r = e.setSpotlight({ type: 'evidence', id: opt.ref! });
    if (v.kind === 'hint' && opt.ref) r = e.revealHint(opt.ref);
    if (v.kind === 'accuse') {
      r = e.accuse(opt.ref!, undefined, `vote:${v.id}`);
      if (r.ok && (r.data as { correct: boolean }).correct) {
        const ci = v.options.findIndex((o) => o.ref === def.solution.culprit);
        for (const [pid, i] of Object.entries(v.ballots)) if (i === ci) this.award({ participantId: pid, amount: 20, reason: 'accuse', ref: v.id });
        for (const t of this.data!.theories) if (t.suspectId === def.solution.culprit) this.award({ participantId: t.authorId, amount: 50, reason: 'theory_correct', ref: 'final' });
      }
    }
    if (v.kind === 'proof') {
      const last = e.state.accusations.at(-1);
      const correct = def.accusation.proof?.options.find((o) => o.id === opt.ref)?.correct ?? false;
      if (last) {
        last.proof = opt.ref;
        last.proofCorrect = correct;
      }
      e.pushFeed('accusation', correct ? 'Beweisführung überzeugt!' : 'Beweisführung wackelt …', { detail: opt.label });
    }
    if (r) this.apply(r);
  }

  /* ------------------------------ Spielleitung ------------------------------ */

  private async control(action: string, p: Record<string, unknown>): Promise<AckResult> {
    const e = this.engine!;
    const d = this.data!;
    const str = (k: string) => String(p[k] ?? '');
    let r: ActionResult;
    switch (action) {
      case 'start':
        r = e.start();
        break;
      case 'pause':
        r = e.pause();
        break;
      case 'resume':
        r = e.resume();
        break;
      case 'phase':
        r = e.setPhase(str('phase'));
        break;
      case 'task':
        r = e.setTask(typeof p.task === 'string' ? p.task : null);
        break;
      case 'spotlight':
        r = e.setSpotlight(p.type ? { type: str('type') as 'evidence', id: str('id') } : null);
        break;
      case 'unlockEvidence':
        r = e.unlockEvidence(str('evidence'));
        break;
      case 'fireEvent':
        r = e.fireEvent(str('event'));
        break;
      case 'hint':
        r = e.revealHint(str('puzzle'));
        break;
      case 'solvePuzzle':
        r = e.forceSolvePuzzle(str('puzzle'));
        break;
      case 'interrogate':
        r = e.startInterrogation(str('character'));
        break;
      case 'ask':
        if (!e.state.interrogation) throw new Error('Keine Vernehmung aktiv.');
        r = e.ask(e.state.interrogation.character, str('topic'), { kind: 'streamer', name: 'Spielleitung' });
        break;
      case 'endInterrogation':
        r = e.endInterrogation();
        break;
      case 'finale':
        r = e.enterFinale();
        break;
      case 'cancelFinale':
        r = e.cancelFinale();
        break;
      case 'accuse':
        r = e.accuse(str('suspect'), typeof p.proof === 'string' ? p.proof : undefined, 'streamer');
        break;
      case 'reveal':
        if (d.vote) d.vote.status = 'cancelled';
        d.vote = null;
        r = e.reveal();
        break;
      case 'end':
        r = e.end();
        break;
      case 'startVote':
        this.startVote(str('kind'), typeof p.question === 'string' ? p.question : undefined, Array.isArray(p.options) ? (p.options as string[]) : undefined, typeof p.seconds === 'number' ? p.seconds : undefined);
        return { ok: true, message: 'Abstimmung gestartet.' };
      case 'closeVote':
        this.closeVote();
        return { ok: true, message: 'Abstimmung beendet.' };
      case 'cancelVote':
        if (d.vote) {
          d.vote.status = 'cancelled';
          d.lastVote = d.vote;
          d.vote = null;
        }
        return { ok: true, message: 'Abstimmung abgebrochen.' };
      case 'applyVote':
        if (!d.lastVote) throw new Error('Keine abgeschlossene Abstimmung.');
        this.applyVote(d.lastVote, Number(p.index));
        return { ok: true, message: 'Ergebnis übernommen.' };
      case 'award': {
        const amount = Math.min(100, Math.max(1, Math.round(Number(p.amount))));
        this.award({ participantId: str('participant'), amount, reason: 'streamer', ref: String(Date.now()) });
        return { ok: true, message: 'Punkte vergeben.' };
      }
      case 'settings': {
        for (const k of Object.keys(p)) {
          if (k === 'overlay' && typeof p.overlay === 'object') d.settings.overlay = { ...d.settings.overlay, ...(p.overlay as object) };
          else d.settings[k] = p[k];
        }
        e.setOptions({ timedEvents: d.settings.timedEvents });
        return { ok: true, message: 'Einstellungen gespeichert.' };
      }
      default:
        throw new Error(`Unbekannte Aktion „${action}“.`);
    }
    if (!r.ok) throw new Error(r.message);
    this.apply(r);
    return { ok: true, message: r.message, data: r.data };
  }

  /** Chat-Simulator: dieselben Befehle wie im Twitch-Chat. */
  chat(user: string, text: string): string | null {
    if (!this.data || !this.engine) return null;
    const cmd = parseChatCommand(text, { bareNumbers: !!this.data.vote });
    if (!cmd) return null;
    const pid = `chat:${user.toLowerCase()}`;
    const p = this.participant(pid, user, 'chat');
    try {
      switch (cmd.cmd) {
        case 'join':
          this.bot(`🕵️ Willkommen im Ermittlerteam: ${user}!`);
          return 'joined';
        case 'vote':
          this.castVote(pid, cmd.option - 1);
          return 'voted';
        case 'team': {
          const t = matchTeam(cmd.team);
          if (t) p.team = t;
          return t ? 'team' : null;
        }
        case 'theory': {
          const view = this.publicView();
          const s = matchName(view.characters.filter((c) => c.role === 'suspect'), cmd.suspect);
          if (!s) return null;
          this.addTheory(pid, s.id, cmd.text.length >= 10 ? cmd.text : `${user} hält ${s.name} für verdächtig.`, []);
          return 'theory';
        }
        case 'suspects':
          this.bot(`🕵️ Verdächtige: ${this.publicView().characters.filter((c) => c.role === 'suspect').map((c, i) => `${i + 1}) ${c.name}`).join(' · ')}`);
          return 'suspects';
        case 'points':
          this.bot(`@${user} ${p.points} Punkte`);
          return 'points';
        case 'hint':
          this.hintRequests += 1;
          return 'hint';
        default:
          return cmd.cmd;
      }
    } catch (e) {
      return `Fehler: ${(e as Error).message}`;
    } finally {
      this.changed();
    }
  }

  /* ------------------------------ Sichten ------------------------------ */

  private publicVote(v: Vote | null): PublicVote | null {
    if (!v) return null;
    const counts = v.options.map(() => 0);
    Object.values(v.ballots).forEach((i) => counts[i]++);
    return { id: v.id, kind: v.kind, question: v.question, options: v.options, counts, total: Object.keys(v.ballots).length, endsAt: v.endsAt, status: v.status, winner: v.winner, tie: v.tie };
  }

  private leaderboard(n = 10) {
    return [...this.data!.participants].filter((p) => p.points > 0).sort((a, b) => b.points - a.points).slice(0, n).map((p) => ({ id: p.id, name: p.name, points: p.points, team: p.team }));
  }

  private teams() {
    return TEAMS.map((t) => {
      const m = this.data!.participants.filter((p) => p.team === t.id);
      return { id: t.id, label: t.label, points: m.reduce((s, p) => s + p.points, 0), members: m.length };
    });
  }

  publicView(): PublicCaseView {
    const d = this.data!;
    const now = Date.now();
    const recent = d.vote ?? (d.lastVote && now - d.lastVote.endsAt < 120_000 ? d.lastVote : null);
    return {
      ...buildGameView(this.def!, this.engine!.state, now),
      sessionId: 'local',
      joinCode: d.code,
      streamer: { login: 'vorschau', displayName: 'Vorschau' },
      serverNow: now,
      vote: this.publicVote(recent),
      theories: d.theories.map(({ upvoters: _u, ...t }) => t).sort((a, b) => b.upvotes - a.upvotes || b.createdAt - a.createdAt),
      leaderboard: this.leaderboard(),
      teams: this.teams(),
      participants: d.participants.length,
      settings: { allowGuests: true, discussion: d.settings.discussion, theories: d.settings.theories },
    };
  }

  private personal(): PersonalState {
    const d = this.data!;
    const me = d.participants.find((p) => p.id === ME)!;
    return {
      participantId: ME,
      displayName: me.name,
      points: me.points,
      team: me.team,
      rank: 1 + d.participants.filter((p) => p.points > me.points).length,
      verified: false,
      moderator: true,
      myVote: d.vote?.ballots[ME] ?? null,
      upvoted: d.theories.filter((t) => t.upvoters.includes(ME)).map((t) => t.id),
    };
  }

  private ownerView() {
    const d = this.data!;
    return {
      ...this.publicView(),
      discussion: d.messages,
      secrets: buildStreamerSecrets(this.def!, this.engine!.state, Date.now()),
      sessionSettings: d.settings,
      participantList: [...d.participants].sort((a, b) => b.points - a.points).map((p) => ({ id: p.id, name: p.name, points: p.points, team: p.team, banned: false, source: p.source, verified: false })),
      hintRequests: this.hintRequests,
      lastVote: this.publicVote(d.lastVote),
      overlayPreview: this.overlayView(),
    };
  }

  overlayView(): OverlayView {
    const d = this.data!;
    const def = this.def!;
    const s = this.engine!.state;
    const now = Date.now();
    const game = buildGameView(def, s, now);
    let spotlight: OverlayView['spotlight'] = null;
    const sp = s.spotlight;
    if (sp?.type === 'evidence') {
      const e = def.evidence.find((x) => x.id === sp.id);
      if (e) spotlight = { type: 'evidence', title: e.title, summary: e.summary };
    } else if (sp?.type === 'character') {
      const pc = game.characters.find((x) => x.id === sp.id);
      if (pc) {
        const last = game.interrogation?.character === pc.id ? game.interrogation.last : undefined;
        spotlight = { type: 'character', name: pc.name, occupation: pc.occupation, color: pc.color, stress: pc.stress, last: last ? { question: last.question, answer: last.answer, mood: last.mood } : undefined };
      }
    } else if (sp?.type === 'insight') {
      const i = def.insights.find((x) => x.id === sp.id);
      if (i) spotlight = { type: 'insight', title: i.title, text: i.text };
    } else if (sp?.type === 'puzzle') {
      const p = def.puzzles.find((x) => x.id === sp.id);
      if (p) spotlight = { type: 'puzzle', title: p.title, prompt: p.prompt, solved: s.puzzles[p.id]?.solvedAt !== undefined };
    }
    const revealed = s.status === 'revealed' || s.status === 'ended';
    const featured = d.theories.find((t) => t.status === 'featured');
    const recent = d.vote ?? (d.lastVote && now - d.lastVote.endsAt < 20_000 ? d.lastVote : null);
    return {
      status: s.status,
      title: def.title,
      tagline: def.tagline,
      accent: def.accent,
      joinCode: d.code,
      joinUrl: 'community-detectives',
      phase: s.status === 'finale' ? 'Finale' : def.phases[s.phaseIndex].title,
      phaseIndex: s.phaseIndex,
      phasesTotal: def.phases.length,
      task: s.task,
      elapsedMs: s.elapsedMs,
      runningSince: s.runningSince,
      serverNow: now,
      spotlight,
      vote: this.publicVote(recent),
      feed: s.feed.filter((f) => ['insight', 'evidence', 'event', 'puzzle', 'accusation', 'phase', 'character'].includes(f.type)).slice(-6),
      progress: game.progress,
      leaderboard: this.leaderboard(5),
      teams: this.teams(),
      featuredTheory: featured ? (({ upvoters: _u, ...t }) => t)(featured) : null,
      participants: d.participants.length,
      solution: revealed
        ? { culpritName: def.characters.find((c) => c.id === def.solution.culprit)?.name ?? '', headline: def.solution.headline, summary: def.solution.summary, correct: s.accusations.at(-1)?.correct ?? null }
        : undefined,
      display: d.settings.overlay,
    };
  }
}
