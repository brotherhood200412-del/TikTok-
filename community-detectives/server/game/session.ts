/**
 * LiveSession – eine laufende Ermittlung eines Streamers.
 *
 * Hält Engine, Teilnehmende, Abstimmung, Theorien und Diskussion im Speicher,
 * schreibt alle relevanten Änderungen in PostgreSQL und kann nach einem
 * Neustart vollständig wiederhergestellt werden.
 */
import type { CaseDefinition } from '../../shared/case/schema.js';
import {
  TEAMS,
  type DiscussionMessage,
  type LeaderboardEntry,
  type OverlaySettings,
  type OverlayView,
  type PersonalState,
  type PublicCaseView,
  type PublicTheory,
  type PublicVote,
  type StreamerSecrets,
} from '../../shared/views.js';
import { prisma } from '../db.js';
import { RateLimiter } from '../security/rateLimit.js';
import { GameEngine, gameMs, type ActionResult, type Actor, type Award, type GameState } from './engine.js';
import { buildGameView, buildStreamerSecrets } from './projection.js';

export interface SessionSettings {
  allowGuests: boolean;
  guestsCanVote: boolean;
  discussion: boolean;
  theories: boolean;
  timedEvents: boolean;
  bareNumberVotes: boolean;
  chatReplies: boolean;
  voteSeconds: number;
  autoApplyVotes: boolean;
  hintRequestThreshold: number;
  overlay: OverlaySettings;
}

export const DEFAULT_SETTINGS: SessionSettings = {
  allowGuests: true,
  guestsCanVote: true,
  discussion: true,
  theories: true,
  timedEvents: true,
  bareNumberVotes: true,
  chatReplies: true,
  voteSeconds: 60,
  autoApplyVotes: true,
  hintRequestThreshold: 5,
  overlay: { position: 'right', showLeaderboard: true, showFeed: true, showJoin: true, scale: 1 },
};

export interface ParticipantInfo {
  id: string;
  displayName: string;
  login: string | null;
  twitchUserId: string | null;
  guestKey: string | null;
  team: string | null;
  points: number;
  banned: boolean;
  source: 'chat' | 'web';
}

export interface Identity {
  twitchUserId?: string;
  login?: string;
  guestKey?: string;
  displayName: string;
  source: 'chat' | 'web';
}

export type VoteKind = 'interrogate' | 'question' | 'examine' | 'accuse' | 'proof' | 'hint' | 'custom';

interface VoteState {
  id: string;
  kind: VoteKind;
  question: string;
  options: { label: string; ref?: string }[];
  ballots: Map<string, number>;
  endsAt: number;
  status: 'open' | 'closed' | 'cancelled';
  winner?: number;
  tie?: number[];
  applied?: boolean;
  timer?: NodeJS.Timeout;
}

export interface SessionHooks {
  changed(session: LiveSession): void;
  personal(session: LiveSession, participantId: string): void;
  say(session: LiveSession, text: string): void;
  notifyStreamer(session: LiveSession, kind: string, text: string): void;
}

export class ActionError extends Error {
  constructor(
    message: string,
    public code = 'invalid',
  ) {
    super(message);
  }
}

const limits = {
  mark: new RateLimiter(6, 0.15),
  connect: new RateLimiter(4, 0.08),
  puzzle: new RateLimiter(5, 1 / 12),
  theory: new RateLimiter(2, 1 / 90),
  message: new RateLimiter(4, 1 / 4),
  upvote: new RateLimiter(10, 0.5),
  join: new RateLimiter(30, 1),
};

export const VOTE_POINTS = 2;
export const ACCUSE_POINTS = 20;
export const PROOF_POINTS = 10;
export const THEORY_CORRECT_POINTS = 50;
export const THEORY_UPVOTE_POINTS = 3;
export const THEORY_UPVOTE_CAP = 30;

export class LiveSession {
  engine: GameEngine;
  participants = new Map<string, ParticipantInfo>();
  identities = new Map<string, string>();
  vote: VoteState | null = null;
  lastVote: VoteState | null = null;
  theories: (PublicTheory & { upvoters: Set<string> })[] = [];
  messages: DiscussionMessage[] = [];
  hintRequests = new Map<string, number>();
  guestIps = new Map<string, Set<string>>();
  moderatorLogins = new Set<string>();
  private saveTimer: NodeJS.Timeout | null = null;
  private saving: Promise<void> = Promise.resolve();
  disposed = false;

  constructor(
    public readonly id: string,
    public readonly streamerId: string,
    public readonly streamer: { login: string; displayName: string; twitchUserId: string | null },
    public readonly joinCode: string,
    public readonly def: CaseDefinition,
    state: GameState,
    public settings: SessionSettings,
    private readonly hooks: SessionHooks,
  ) {
    this.engine = new GameEngine(def, state, { timedEvents: settings.timedEvents });
  }

  get state() {
    return this.engine.state;
  }

  /* ------------------------------ Persistenz ------------------------------ */

  changed(opts: { immediate?: boolean } = {}) {
    this.hooks.changed(this);
    if (this.saveTimer) clearTimeout(this.saveTimer);
    if (opts.immediate) void this.save();
    else this.saveTimer = setTimeout(() => void this.save(), 800);
  }

  async save() {
    if (this.saveTimer) clearTimeout(this.saveTimer);
    this.saveTimer = null;
    const state = { ...this.state, elapsedMs: gameMs(this.state, Date.now()), runningSince: this.state.runningSince === null ? null : Date.now() };
    this.saving = this.saving
      .then(async () => {
        await prisma.gameSession.update({
          where: { id: this.id },
          data: {
            status: this.state.status,
            state: state as object,
            settings: this.settings as object,
            endedAt: this.state.status === 'ended' ? new Date() : undefined,
          },
        });
        if (this.vote) await this.persistBallots(this.vote);
      })
      .catch((e) => console.error('[session] Speichern fehlgeschlagen', this.id, e));
    return this.saving;
  }

  private async persistBallots(v: VoteState) {
    if (!v.ballots.size) return;
    const rows = [...v.ballots].map(([participantId, optionIndex]) => ({ voteId: v.id, participantId, optionIndex }));
    // Stimmen können geändert werden: vorhandene aktualisieren, neue anlegen.
    await prisma.$transaction([
      prisma.ballot.deleteMany({ where: { voteId: v.id } }),
      prisma.ballot.createMany({ data: rows, skipDuplicates: true }),
    ]);
  }

  async log(type: string, payload: Record<string, unknown>) {
    await prisma.sessionEvent.create({ data: { sessionId: this.id, type, payload: payload as object } }).catch(() => undefined);
  }

  dispose() {
    this.disposed = true;
    if (this.vote?.timer) clearTimeout(this.vote.timer);
    if (this.saveTimer) clearTimeout(this.saveTimer);
  }

  /* ------------------------------ Teilnehmende ------------------------------ */

  identityKey(i: { twitchUserId?: string | null; guestKey?: string | null }) {
    return i.twitchUserId ? `tw:${i.twitchUserId}` : `g:${i.guestKey}`;
  }

  async join(identity: Identity, ip?: string): Promise<ParticipantInfo> {
    const key = this.identityKey(identity);
    const existingId = this.identities.get(key);
    if (existingId) {
      const p = this.participants.get(existingId)!;
      if (identity.displayName && p.displayName !== identity.displayName && identity.twitchUserId) p.displayName = identity.displayName;
      return p;
    }
    if (!identity.twitchUserId) {
      if (!this.settings.allowGuests) throw new ActionError('Diese Ermittlung erlaubt nur Twitch-Anmeldungen.', 'guests_disabled');
      if (ip) {
        const set = this.guestIps.get(ip) ?? new Set<string>();
        if (!set.has(identity.guestKey!) && set.size >= 3) throw new ActionError('Zu viele Gastzugänge von diesem Anschluss.', 'guest_limit');
        set.add(identity.guestKey!);
        this.guestIps.set(ip, set);
      }
    }
    if (!limits.join.take(`${this.id}`)) throw new ActionError('Gerade treten sehr viele bei – bitte gleich noch einmal versuchen.', 'rate');
    const where = identity.twitchUserId
      ? { sessionId_twitchUserId: { sessionId: this.id, twitchUserId: identity.twitchUserId } }
      : { sessionId_guestKey: { sessionId: this.id, guestKey: identity.guestKey! } };
    const row = await prisma.participant.upsert({
      where,
      create: {
        sessionId: this.id,
        twitchUserId: identity.twitchUserId ?? null,
        guestKey: identity.twitchUserId ? null : identity.guestKey!,
        login: identity.login ?? null,
        displayName: identity.displayName.slice(0, 40),
        source: identity.source,
      },
      update: { lastSeenAt: new Date() },
    });
    const p: ParticipantInfo = {
      id: row.id,
      displayName: row.displayName,
      login: row.login,
      twitchUserId: row.twitchUserId,
      guestKey: row.guestKey,
      team: row.team,
      points: row.points,
      banned: row.banned,
      source: row.source as 'chat' | 'web',
    };
    this.participants.set(p.id, p);
    this.identities.set(key, p.id);
    this.changed();
    return p;
  }

  participant(id: string): ParticipantInfo {
    const p = this.participants.get(id);
    if (!p) throw new ActionError('Unbekannte Person – bitte erneut beitreten.', 'not_joined');
    if (p.banned) throw new ActionError('Du wurdest von der Moderation von dieser Ermittlung ausgeschlossen.', 'banned');
    return p;
  }

  actor(p: ParticipantInfo): Actor {
    return { kind: 'viewer', participantId: p.id, name: p.displayName };
  }

  async setTeam(pid: string, team: string) {
    const p = this.participant(pid);
    if (!TEAMS.some((t) => t.id === team)) throw new ActionError('Unbekanntes Team.');
    p.team = team;
    await prisma.participant.update({ where: { id: pid }, data: { team } });
    this.changed();
    this.hooks.personal(this, pid);
  }

  async award(a: Award) {
    if (a.amount === 0) return;
    const p = this.participants.get(a.participantId);
    if (!p) return;
    try {
      await prisma.$transaction([
        prisma.pointEntry.create({ data: { sessionId: this.id, participantId: a.participantId, amount: a.amount, reason: a.reason, ref: a.ref } }),
        prisma.participant.update({ where: { id: a.participantId }, data: { points: { increment: a.amount } } }),
      ]);
      p.points += a.amount;
      this.hooks.personal(this, a.participantId);
    } catch (e) {
      // Eindeutigkeitsverletzung = Punkte wurden bereits vergeben (Anti-Farming).
      if ((e as { code?: string }).code !== 'P2002') console.error('[points]', e);
    }
  }

  async applyResult(res: ActionResult) {
    for (const a of res.awards) await this.award(a);
    if (res.discoveries.length) {
      void this.log('discoveries', { items: res.discoveries });
      const ins = res.discoveries.filter((d) => d.kind === 'insight');
      if (ins.length && this.settings.chatReplies) this.hooks.say(this, `🔎 Neue Erkenntnis: ${ins.map((d) => d.title).join(' · ')}`);
    }
    this.changed({ immediate: res.discoveries.length > 0 });
  }

  rank(pid: string): number | null {
    const p = this.participants.get(pid);
    if (!p) return null;
    let r = 1;
    for (const o of this.participants.values()) if (!o.banned && o.points > p.points) r++;
    return r;
  }

  personal(pid: string, opts: { verified: boolean; moderator: boolean }): PersonalState {
    const p = this.participants.get(pid)!;
    return {
      participantId: p.id,
      displayName: p.displayName,
      points: p.points,
      team: p.team,
      rank: this.rank(pid),
      verified: opts.verified,
      moderator: opts.moderator,
      myVote: this.vote?.ballots.get(pid) ?? null,
      upvoted: this.theories.filter((t) => t.upvoters.has(pid)).map((t) => t.id),
    };
  }

  /* ------------------------------ Ermittlungsaktionen ------------------------------ */

  private limited(limiter: RateLimiter, key: string, what: string) {
    if (!limiter.take(key)) throw new ActionError(`Langsam, Detektiv! Du kannst in ${limiter.retryAfter(key)} s wieder ${what}.`, 'rate');
  }

  async mark(pid: string, evidenceId: string, itemId: string) {
    const p = this.participant(pid);
    this.limited(limits.mark, `${this.id}:${pid}`, 'Details markieren');
    const res = this.engine.markItem(evidenceId, itemId, this.actor(p));
    await this.applyResult(res);
    return res;
  }

  async connect(pid: string, a: string, b: string) {
    const p = this.participant(pid);
    this.limited(limits.connect, `${this.id}:${pid}`, 'Verbindungen prüfen');
    const res = this.engine.connect(a, b, this.actor(p));
    await this.applyResult(res);
    return res;
  }

  async answer(pid: string, puzzleId: string, answer: unknown) {
    const p = this.participant(pid);
    this.limited(limits.puzzle, `${this.id}:${pid}:${puzzleId}`, 'eine Lösung einreichen');
    const res = this.engine.solvePuzzle(puzzleId, answer, this.actor(p));
    if (res.ok && res.code !== 'known') this.hooks.say(this, `🧩 ${p.displayName} hat das Rätsel „${this.def.puzzles.find((x) => x.id === puzzleId)?.title}“ gelöst!`);
    await this.applyResult(res);
    return res;
  }

  /** Antwort aus dem Chat: aktives Rätsel (Fokus) oder das einzige offene Rätsel. */
  activePuzzleId(): string | null {
    if (this.state.spotlight?.type === 'puzzle') return this.state.spotlight.id;
    const avail = this.engine.availability();
    const open = this.def.puzzles.filter((p) => avail.puzzles.has(p.id) && this.state.puzzles[p.id]?.solvedAt === undefined && p.input.kind === 'text');
    return open.length === 1 ? open[0].id : null;
  }

  requestHint(pid: string) {
    this.participant(pid);
    const now = Date.now();
    this.hintRequests.set(pid, now);
    for (const [k, t] of this.hintRequests) if (now - t > 180_000) this.hintRequests.delete(k);
    const n = this.hintRequests.size;
    if (n >= this.settings.hintRequestThreshold) {
      this.hintRequests.clear();
      this.hooks.notifyStreamer(this, 'hint', `${n} Ermittler bitten um einen Hinweis.`);
    }
    this.changed();
    return n;
  }

  /* ------------------------------ Theorien & Diskussion ------------------------------ */

  async submitTheory(pid: string, suspectId: string, text: string, evidenceIds: string[]) {
    if (!this.settings.theories) throw new ActionError('Theorien sind gerade deaktiviert.', 'disabled');
    const p = this.participant(pid);
    const suspect = this.def.characters.find((c) => c.id === suspectId && c.role === 'suspect');
    if (!suspect || !this.engine.availability().characters.has(suspectId)) throw new ActionError('Unbekannte verdächtige Person.');
    const clean = sanitize(text, 400);
    if (clean.length < 10) throw new ActionError('Begründe deine Theorie in mindestens 10 Zeichen.');
    const avail = this.engine.availability();
    const evs = [...new Set(evidenceIds)].filter((e) => avail.evidence.has(e) || this.state.insights[e]).slice(0, 5);
    const mine = this.theories.filter((t) => t.authorId === pid).length;
    if (mine >= 5) throw new ActionError('Du hast bereits fünf Theorien eingereicht.', 'limit');
    this.limited(limits.theory, `${this.id}:${pid}`, 'eine Theorie einreichen');
    const row = await prisma.theory.create({ data: { sessionId: this.id, participantId: pid, suspectId, text: clean, evidenceIds: evs } });
    this.theories.push({
      id: row.id,
      author: p.displayName,
      authorId: pid,
      suspectId,
      text: clean,
      evidenceIds: evs,
      upvotes: 0,
      status: 'visible',
      createdAt: row.createdAt.getTime(),
      upvoters: new Set(),
    });
    this.engine.pushFeed('theory', `${p.displayName} verdächtigt ${suspect.name}`, { by: p.displayName, ref: row.id });
    await this.award({ participantId: pid, amount: 5, reason: 'theory', ref: `n${mine + 1}` });
    this.changed();
    return row.id;
  }

  async upvoteTheory(pid: string, theoryId: string) {
    this.participant(pid);
    this.limited(limits.upvote, `${this.id}:${pid}`, 'Theorien unterstützen');
    const t = this.theories.find((x) => x.id === theoryId && x.status !== 'hidden');
    if (!t) throw new ActionError('Theorie nicht gefunden.');
    if (t.authorId === pid) throw new ActionError('Eigene Theorien kannst du nicht unterstützen.');
    if (t.upvoters.has(pid)) {
      t.upvoters.delete(pid);
    } else {
      t.upvoters.add(pid);
      // Gute Schlussfolgerungen belohnen – begrenzt, um Farming zu verhindern.
      const received = [...t.upvoters].length;
      if (received * THEORY_UPVOTE_POINTS <= THEORY_UPVOTE_CAP) await this.award({ participantId: t.authorId, amount: THEORY_UPVOTE_POINTS, reason: 'theory_upvote', ref: `${t.id}:${pid}` });
    }
    t.upvotes = t.upvoters.size;
    await prisma.theory.update({ where: { id: t.id }, data: { upvoterIds: [...t.upvoters] } });
    this.changed();
  }

  async moderateTheory(theoryId: string, status: 'visible' | 'hidden' | 'featured') {
    const t = this.theories.find((x) => x.id === theoryId);
    if (!t) throw new ActionError('Theorie nicht gefunden.');
    if (status === 'featured') for (const o of this.theories) if (o.status === 'featured') o.status = 'visible';
    t.status = status;
    await prisma.theory.update({ where: { id: theoryId }, data: { status } });
    this.changed();
  }

  async postMessage(pid: string, text: string) {
    if (!this.settings.discussion) throw new ActionError('Die Diskussion ist deaktiviert.', 'disabled');
    const p = this.participant(pid);
    this.limited(limits.message, `${this.id}:${pid}`, 'schreiben');
    const clean = sanitize(text, 280);
    if (!clean) throw new ActionError('Leere Nachricht.');
    const last = this.messages.filter((m) => m.authorId === pid).at(-1);
    if (last && last.text === clean && Date.now() - last.at < 60_000) throw new ActionError('Doppelte Nachricht.', 'duplicate');
    const row = await prisma.message.create({ data: { sessionId: this.id, participantId: pid, text: clean } });
    this.messages.push({ id: row.id, author: p.displayName, authorId: pid, text: clean, at: row.createdAt.getTime() });
    if (this.messages.length > 150) this.messages.splice(0, this.messages.length - 150);
    this.changed();
  }

  async hideMessage(id: string) {
    const m = this.messages.find((x) => x.id === id);
    if (m) m.hidden = true;
    await prisma.message.update({ where: { id }, data: { hidden: true } }).catch(() => undefined);
    this.changed();
  }

  async setBanned(pid: string, banned: boolean) {
    const p = this.participants.get(pid);
    if (!p) throw new ActionError('Unbekannt.');
    p.banned = banned;
    await prisma.participant.update({ where: { id: pid }, data: { banned } });
    if (banned && this.vote) this.vote.ballots.delete(pid);
    this.changed();
  }

  /* ------------------------------ Abstimmungen ------------------------------ */

  startVote(kind: VoteKind, input: { question?: string; options?: string[]; seconds?: number }) {
    if (this.vote?.status === 'open') throw new ActionError('Es läuft bereits eine Abstimmung.', 'busy');
    const avail = this.engine.availability();
    let question = input.question?.trim() ?? '';
    let options: { label: string; ref?: string }[] = [];
    const suspects = this.def.characters.filter((c) => c.role === 'suspect' && avail.characters.has(c.id));
    switch (kind) {
      case 'interrogate': {
        const list = this.def.characters.filter((c) => avail.characters.has(c.id) && this.def.interrogations.some((i) => i.character === c.id));
        options = list.map((c) => ({ label: c.name, ref: c.id }));
        question ||= 'Wen sollen wir als Nächstes vernehmen?';
        break;
      }
      case 'question': {
        const cur = this.state.interrogation;
        if (!cur) throw new ActionError('Starte zuerst eine Vernehmung.');
        const it = this.def.interrogations.find((i) => i.character === cur.character)!;
        const open = avail.topics.get(cur.character) ?? [];
        options = it.topics.filter((t) => open.includes(t.id)).map((t) => ({ label: t.question, ref: t.id }));
        question ||= `Welche Frage stellen wir ${this.def.characters.find((c) => c.id === cur.character)?.name}?`;
        break;
      }
      case 'examine':
        options = this.def.evidence.filter((e) => avail.evidence.has(e.id)).map((e) => ({ label: e.title, ref: e.id }));
        question ||= 'Welches Beweisstück nehmen wir gemeinsam unter die Lupe?';
        break;
      case 'accuse':
        options = suspects.map((c) => ({ label: c.name, ref: c.id }));
        question ||= this.def.accusation.question;
        if (this.state.status !== 'finale' && this.state.status !== 'active') throw new ActionError('Anklage nur während der Ermittlung oder im Finale.');
        break;
      case 'proof':
        if (!this.def.accusation.proof) throw new ActionError('Dieser Fall hat keine Beweisfrage.');
        options = this.def.accusation.proof.options.map((o) => ({ label: o.label, ref: o.id }));
        question ||= this.def.accusation.proof.question;
        break;
      case 'hint': {
        const pid = this.activePuzzleId() ?? undefined;
        if (!pid) throw new ActionError('Setze zuerst ein Rätsel in den Fokus.');
        options = [
          { label: 'Ja, Hinweis aufdecken', ref: pid },
          { label: 'Nein, wir schaffen das allein', ref: '' },
        ];
        question ||= `Hinweis für „${this.def.puzzles.find((p) => p.id === pid)?.title}“ aufdecken?`;
        break;
      }
      case 'custom':
        options = (input.options ?? []).map((o) => sanitize(o, 80)).filter(Boolean).map((label) => ({ label }));
        if (!question) throw new ActionError('Bitte eine Frage angeben.');
        break;
    }
    if (options.length < 2) throw new ActionError('Eine Abstimmung braucht mindestens zwei Optionen.');
    if (options.length > 9) options = options.slice(0, 9);
    const seconds = Math.min(600, Math.max(15, input.seconds ?? this.settings.voteSeconds));
    const v: VoteState = {
      id: `v_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
      kind,
      question: sanitize(question, 200),
      options,
      ballots: new Map(),
      endsAt: Date.now() + seconds * 1000,
      status: 'open',
    };
    this.vote = v;
    void prisma.vote
      .create({ data: { id: v.id, sessionId: this.id, kind, question: v.question, options: v.options, status: 'open', endsAt: new Date(v.endsAt) } })
      .catch((e) => console.error('[vote]', e));
    v.timer = setTimeout(() => void this.closeVote().catch((e) => console.error(e)), seconds * 1000);
    this.engine.pushFeed('vote', v.question);
    if (this.settings.chatReplies) {
      this.hooks.say(this, `🗳️ ${v.question} ${v.options.map((o, i) => `${i + 1}) ${o.label}`).join('  ')} → Abstimmen mit !a <Nummer> (${seconds} s)`);
    }
    this.changed();
    return v.id;
  }

  /** Nach Neustart: offene Abstimmung wiederherstellen. */
  restoreVote(row: { id: string; kind: string; question: string; options: unknown; endsAt: Date }, ballots: { participantId: string; optionIndex: number }[]) {
    const v: VoteState = {
      id: row.id,
      kind: row.kind as VoteKind,
      question: row.question,
      options: row.options as VoteState['options'],
      ballots: new Map(ballots.map((b) => [b.participantId, b.optionIndex])),
      endsAt: row.endsAt.getTime(),
      status: 'open',
    };
    this.vote = v;
    const ms = Math.max(1000, v.endsAt - Date.now());
    v.timer = setTimeout(() => void this.closeVote().catch((e) => console.error(e)), ms);
  }

  castVote(pid: string, optionIndex: number) {
    const p = this.participant(pid);
    const v = this.vote;
    if (!v || v.status !== 'open') throw new ActionError('Gerade läuft keine Abstimmung.', 'no_vote');
    if (!p.twitchUserId && !this.settings.guestsCanVote) throw new ActionError('Abstimmen ist nur mit Twitch-Login möglich.', 'verified_only');
    if (!Number.isInteger(optionIndex) || optionIndex < 0 || optionIndex >= v.options.length) throw new ActionError('Ungültige Option.');
    if (Date.now() > v.endsAt) throw new ActionError('Die Abstimmung ist bereits beendet.');
    v.ballots.set(pid, optionIndex);
    this.changed();
  }

  tally(v: VoteState) {
    const counts = v.options.map(() => 0);
    for (const idx of v.ballots.values()) counts[idx]++;
    return counts;
  }

  async closeVote(): Promise<VoteState | null> {
    const v = this.vote;
    if (!v || v.status !== 'open') return null;
    if (v.timer) clearTimeout(v.timer);
    v.status = 'closed';
    const counts = this.tally(v);
    const max = Math.max(...counts);
    const leaders = counts.map((c, i) => (c === max ? i : -1)).filter((i) => i >= 0);
    if (max === 0) v.tie = undefined;
    else if (leaders.length === 1) v.winner = leaders[0];
    else v.tie = leaders;
    this.lastVote = v;
    this.vote = null;
    await this.persistBallots(v).catch((e) => console.error('[vote] ballots', e));
    await prisma.vote
      .update({ where: { id: v.id }, data: { status: 'closed', closedAt: new Date(), result: { counts, winner: v.winner ?? null, tie: v.tie ?? null } } })
      .catch(() => undefined);
    for (const pid of v.ballots.keys()) await this.award({ participantId: pid, amount: VOTE_POINTS, reason: 'vote', ref: v.id });
    const label = v.winner !== undefined ? v.options[v.winner].label : v.tie ? 'Gleichstand' : 'keine Stimmen';
    this.engine.pushFeed('vote', `Ergebnis: ${label}`, { detail: v.question });
    if (this.settings.chatReplies) this.hooks.say(this, `🗳️ Ergebnis: ${label} (${v.ballots.size} Stimmen)`);
    if (v.winner !== undefined && this.settings.autoApplyVotes) await this.applyVote(v, v.winner);
    else if (v.tie) this.hooks.notifyStreamer(this, 'tie', `Gleichstand bei „${v.question}“ – bitte entscheiden.`);
    this.changed({ immediate: true });
    return v;
  }

  cancelVote() {
    const v = this.vote;
    if (!v) throw new ActionError('Keine Abstimmung aktiv.');
    if (v.timer) clearTimeout(v.timer);
    v.status = 'cancelled';
    this.lastVote = v;
    this.vote = null;
    void prisma.vote.update({ where: { id: v.id }, data: { status: 'cancelled', closedAt: new Date() } }).catch(() => undefined);
    this.changed();
  }

  /** Ergebnis anwenden (automatisch oder durch die Spielleitung bei Gleichstand). */
  async applyVote(v: VoteState, index: number): Promise<ActionResult | null> {
    if (v.applied) throw new ActionError('Ergebnis wurde bereits angewendet.');
    const opt = v.options[index];
    if (!opt) throw new ActionError('Ungültige Option.');
    v.applied = true;
    v.winner = index;
    let res: ActionResult | null = null;
    const community: Actor = { kind: 'community', name: 'Community' };
    switch (v.kind) {
      case 'interrogate':
        res = this.engine.startInterrogation(opt.ref!);
        break;
      case 'question':
        if (this.state.interrogation) res = this.engine.ask(this.state.interrogation.character, opt.ref!, community);
        break;
      case 'examine':
        res = this.engine.setSpotlight({ type: 'evidence', id: opt.ref! });
        break;
      case 'hint':
        if (opt.ref) res = this.engine.revealHint(opt.ref);
        break;
      case 'accuse': {
        res = this.engine.accuse(opt.ref!, undefined, `vote:${v.id}`);
        if (res.ok) await this.afterAccusation(res, v);
        break;
      }
      case 'proof': {
        const last = this.state.accusations.at(-1);
        const correct = this.def.accusation.proof?.options.find((o) => o.id === opt.ref)?.correct ?? false;
        if (last) {
          last.proof = opt.ref;
          last.proofCorrect = correct;
        }
        const correctIdx = v.options.findIndex((o) => this.def.accusation.proof?.options.find((p) => p.id === o.ref)?.correct);
        for (const [pid, idx] of v.ballots) if (idx === correctIdx) await this.award({ participantId: pid, amount: PROOF_POINTS, reason: 'proof', ref: v.id });
        this.engine.pushFeed('accusation', correct ? 'Beweisführung überzeugt!' : 'Beweisführung wackelt …', { detail: opt.label });
        break;
      }
      case 'custom':
        break;
    }
    if (res) await this.applyResult(res);
    this.changed({ immediate: true });
    return res;
  }

  private async afterAccusation(res: ActionResult, v?: VoteState) {
    const correct = (res.data as { correct: boolean }).correct;
    if (v) {
      const culpritIdx = v.options.findIndex((o) => o.ref === this.def.solution.culprit);
      if (correct) for (const [pid, idx] of v.ballots) if (idx === culpritIdx) await this.award({ participantId: pid, amount: ACCUSE_POINTS, reason: 'accuse', ref: v.id });
    }
    if (correct) {
      for (const t of this.theories) {
        if (t.suspectId === this.def.solution.culprit && t.status !== 'hidden') {
          await this.award({ participantId: t.authorId, amount: THEORY_CORRECT_POINTS, reason: 'theory_correct', ref: 'final' });
        }
      }
    }
    if (this.settings.chatReplies) {
      this.hooks.say(this, correct ? '⚖️ Die Anklage sitzt! Die Spielleitung bereitet die Auflösung vor …' : '⚖️ Die Anklage ist geplatzt! Die Ermittlung geht weiter …');
    }
  }

  /* ------------------------------ Spielleitung ------------------------------ */

  async control(action: string, payload: Record<string, unknown>): Promise<ActionResult | { ok: true; message: string }> {
    const e = this.engine;
    const str = (k: string) => {
      const v = payload[k];
      if (typeof v !== 'string' || !v) throw new ActionError(`Feld "${k}" fehlt.`);
      return v;
    };
    let res: ActionResult;
    switch (action) {
      case 'start':
        res = e.start();
        break;
      case 'pause':
        res = e.pause();
        break;
      case 'resume':
        res = e.resume();
        break;
      case 'phase':
        res = e.setPhase(str('phase'));
        break;
      case 'task':
        res = e.setTask(typeof payload.task === 'string' ? payload.task : null);
        break;
      case 'spotlight':
        res = e.setSpotlight(payload.type ? { type: str('type') as 'evidence', id: str('id') } : null);
        break;
      case 'unlockEvidence':
        res = e.unlockEvidence(str('evidence'));
        break;
      case 'fireEvent':
        res = e.fireEvent(str('event'));
        break;
      case 'hint':
        res = e.revealHint(str('puzzle'));
        break;
      case 'solvePuzzle':
        res = e.forceSolvePuzzle(str('puzzle'));
        break;
      case 'interrogate':
        res = e.startInterrogation(str('character'));
        break;
      case 'ask':
        if (!e.state.interrogation) throw new ActionError('Keine Vernehmung aktiv.');
        res = e.ask(e.state.interrogation.character, str('topic'), { kind: 'streamer', name: 'Spielleitung' });
        break;
      case 'endInterrogation':
        res = e.endInterrogation();
        break;
      case 'finale':
        res = e.enterFinale();
        break;
      case 'cancelFinale':
        res = e.cancelFinale();
        break;
      case 'accuse':
        res = e.accuse(str('suspect'), typeof payload.proof === 'string' ? payload.proof : undefined, 'streamer');
        if (res.ok) await this.afterAccusation(res);
        break;
      case 'reveal':
        if (this.vote) this.cancelVote();
        res = e.reveal();
        if (res.ok && this.settings.chatReplies) this.hooks.say(this, `📂 Auflösung: ${this.def.solution.headline}`);
        break;
      case 'end':
        if (this.vote) this.cancelVote();
        res = e.end();
        break;
      case 'startVote': {
        const id = this.startVote(str('kind') as VoteKind, {
          question: typeof payload.question === 'string' ? payload.question : undefined,
          options: Array.isArray(payload.options) ? (payload.options as string[]) : undefined,
          seconds: typeof payload.seconds === 'number' ? payload.seconds : undefined,
        });
        return { ok: true, message: `Abstimmung gestartet (${id}).` };
      }
      case 'closeVote':
        await this.closeVote();
        return { ok: true, message: 'Abstimmung beendet.' };
      case 'cancelVote':
        this.cancelVote();
        return { ok: true, message: 'Abstimmung abgebrochen.' };
      case 'applyVote': {
        const v = this.lastVote;
        if (!v || v.status !== 'closed') throw new ActionError('Keine abgeschlossene Abstimmung.');
        const r = await this.applyVote(v, Number(payload.index));
        return r ?? { ok: true, message: 'Ergebnis übernommen.' };
      }
      case 'award': {
        const amount = Math.round(Number(payload.amount));
        if (!Number.isFinite(amount) || amount < 1 || amount > 100) throw new ActionError('Punkte zwischen 1 und 100.');
        const pid = str('participant');
        const reason = sanitize(String(payload.reason ?? 'Spielleitung'), 60);
        await this.award({ participantId: pid, amount, reason: 'streamer', ref: `${Date.now()}` });
        const p = this.participants.get(pid);
        if (p) e.pushFeed('system', `${p.displayName} erhält ${amount} Punkte: ${reason}`);
        this.changed();
        return { ok: true, message: 'Punkte vergeben.' };
      }
      case 'settings': {
        this.updateSettings(payload);
        return { ok: true, message: 'Einstellungen gespeichert.' };
      }
      default:
        throw new ActionError(`Unbekannte Aktion "${action}".`);
    }
    void this.log(`control:${action}`, { payload, ok: res.ok, message: res.message });
    if (!res.ok) throw new ActionError(res.message, res.code);
    await this.applyResult(res);
    this.changed({ immediate: true });
    return res;
  }

  updateSettings(patch: Record<string, unknown>) {
    const s = { ...this.settings };
    for (const k of ['allowGuests', 'guestsCanVote', 'discussion', 'theories', 'timedEvents', 'bareNumberVotes', 'chatReplies', 'autoApplyVotes'] as const) {
      if (typeof patch[k] === 'boolean') s[k] = patch[k] as boolean;
    }
    if (typeof patch.voteSeconds === 'number') s.voteSeconds = Math.min(600, Math.max(15, Math.round(patch.voteSeconds)));
    if (typeof patch.hintRequestThreshold === 'number') s.hintRequestThreshold = Math.min(500, Math.max(1, Math.round(patch.hintRequestThreshold)));
    if (patch.overlay && typeof patch.overlay === 'object') {
      const o = patch.overlay as Partial<OverlaySettings>;
      s.overlay = {
        position: o.position === 'left' ? 'left' : o.position === 'right' ? 'right' : s.overlay.position,
        showLeaderboard: typeof o.showLeaderboard === 'boolean' ? o.showLeaderboard : s.overlay.showLeaderboard,
        showFeed: typeof o.showFeed === 'boolean' ? o.showFeed : s.overlay.showFeed,
        showJoin: typeof o.showJoin === 'boolean' ? o.showJoin : s.overlay.showJoin,
        scale: typeof o.scale === 'number' ? Math.min(1.6, Math.max(0.6, o.scale)) : s.overlay.scale,
      };
    }
    this.settings = s;
    this.engine.setOptions({ timedEvents: s.timedEvents });
    this.changed({ immediate: true });
  }

  tick() {
    const res = this.engine.tick();
    if (res.discoveries.length) void this.applyResult(res);
  }

  /* ------------------------------ Sichten ------------------------------ */

  publicVote(v: VoteState | null): PublicVote | null {
    if (!v) return null;
    const counts = this.tally(v);
    return {
      id: v.id,
      kind: v.kind,
      question: v.question,
      options: v.options,
      counts,
      total: v.ballots.size,
      endsAt: v.endsAt,
      status: v.status,
      winner: v.winner,
      tie: v.tie,
    };
  }

  leaderboard(limit = 10): LeaderboardEntry[] {
    return [...this.participants.values()]
      .filter((p) => !p.banned && p.points > 0)
      .sort((a, b) => b.points - a.points || a.displayName.localeCompare(b.displayName))
      .slice(0, limit)
      .map((p) => ({ id: p.id, name: p.displayName, points: p.points, team: p.team }));
  }

  teams() {
    return TEAMS.map((t) => {
      let points = 0;
      let members = 0;
      for (const p of this.participants.values()) {
        if (p.team === t.id && !p.banned) {
          points += p.points;
          members++;
        }
      }
      return { id: t.id, label: t.label, points, members };
    });
  }

  publicView(opts: { moderator?: boolean } = {}): PublicCaseView {
    const now = Date.now();
    const game = buildGameView(this.def, this.state, now);
    const recentVote = this.vote ?? (this.lastVote && now - (this.lastVote.endsAt ?? 0) < 120_000 ? this.lastVote : null);
    return {
      ...game,
      sessionId: this.id,
      joinCode: this.joinCode,
      streamer: { login: this.streamer.login, displayName: this.streamer.displayName },
      serverNow: now,
      vote: this.publicVote(recentVote),
      theories: this.theories
        .filter((t) => opts.moderator || t.status !== 'hidden')
        .sort((a, b) => (b.status === 'featured' ? 1 : 0) - (a.status === 'featured' ? 1 : 0) || b.upvotes - a.upvotes || b.createdAt - a.createdAt)
        .slice(0, 60)
        .map(({ upvoters: _u, ...t }) => t),
      leaderboard: this.leaderboard(10),
      teams: this.teams(),
      participants: this.participants.size,
      settings: { allowGuests: this.settings.allowGuests, discussion: this.settings.discussion, theories: this.settings.theories },
    };
  }

  discussion(opts: { moderator?: boolean } = {}): DiscussionMessage[] {
    return this.messages.filter((m) => opts.moderator || !m.hidden).slice(-80);
  }

  secrets(): StreamerSecrets {
    return buildStreamerSecrets(this.def, this.state, Date.now());
  }

  overlayView(publicUrl: string): OverlayView {
    const now = Date.now();
    const s = this.state;
    const def = this.def;
    let spotlight: OverlayView['spotlight'] = null;
    const sp = s.spotlight;
    if (sp?.type === 'evidence') {
      const e = def.evidence.find((x) => x.id === sp.id);
      if (e) spotlight = { type: 'evidence', title: e.title, summary: e.summary };
    } else if (sp?.type === 'character') {
      const c = def.characters.find((x) => x.id === sp.id);
      const view = buildGameView(def, s, now);
      const pc = view.characters.find((x) => x.id === sp.id);
      if (c && pc) {
        const last = view.interrogation?.character === c.id ? view.interrogation.last : undefined;
        spotlight = { type: 'character', name: c.name, occupation: c.occupation, color: pc.color, stress: pc.stress, last: last ? { question: last.question, answer: last.answer, mood: last.mood } : undefined };
      }
    } else if (sp?.type === 'insight' && s.insights[sp.id]) {
      const i = def.insights.find((x) => x.id === sp.id);
      if (i) spotlight = { type: 'insight', title: i.title, text: i.text };
    } else if (sp?.type === 'puzzle') {
      const p = def.puzzles.find((x) => x.id === sp.id);
      if (p) spotlight = { type: 'puzzle', title: p.title, prompt: p.prompt, solved: s.puzzles[p.id]?.solvedAt !== undefined };
    }
    const revealed = s.status === 'revealed' || s.status === 'ended';
    const lastAcc = s.accusations.at(-1);
    const featured = this.theories.find((t) => t.status === 'featured');
    const game = buildGameView(def, s, now);
    const recentVote = this.vote ?? (this.lastVote && now - this.lastVote.endsAt < 20_000 ? this.lastVote : null);
    return {
      status: s.status,
      title: def.title,
      tagline: def.tagline,
      accent: def.accent,
      joinCode: this.joinCode,
      joinUrl: `${publicUrl.replace(/\/$/, '')}/play/${this.joinCode}`,
      phase: s.status === 'finale' ? 'Finale' : def.phases[s.phaseIndex].title,
      phaseIndex: s.phaseIndex,
      phasesTotal: def.phases.length,
      task: s.task,
      elapsedMs: s.elapsedMs,
      runningSince: s.runningSince,
      serverNow: now,
      spotlight,
      vote: this.publicVote(recentVote),
      feed: s.feed.filter((f) => ['insight', 'evidence', 'event', 'puzzle', 'accusation', 'phase', 'character'].includes(f.type)).slice(-6),
      progress: game.progress,
      leaderboard: this.leaderboard(5),
      teams: this.teams(),
      featuredTheory: featured ? (({ upvoters: _u, ...t }) => t)(featured) : null,
      participants: this.participants.size,
      solution: revealed
        ? {
            culpritName: def.characters.find((c) => c.id === def.solution.culprit)?.name ?? '',
            headline: def.solution.headline,
            summary: def.solution.summary,
            correct: lastAcc ? lastAcc.correct : null,
          }
        : undefined,
      display: this.settings.overlay,
    };
  }
}

export function sanitize(s: string, max: number) {
  return s
    .replace(/[\u0000-\u001f\u007f​-‏‪-‮⁦-⁩]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, max);
}
