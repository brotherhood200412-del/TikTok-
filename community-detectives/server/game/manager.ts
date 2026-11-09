import type { Tier } from '../../shared/case/schema.js';
import type { PublicTheory } from '../../shared/views.js';
import { prisma } from '../db.js';
import { joinCode } from '../security/crypto.js';
import { createInitialState, type GameState } from './engine.js';
import { getCaseDefinition, listLibrary, tierAllows } from './library.js';
import { ActionError, DEFAULT_SETTINGS, LiveSession, type SessionHooks, type SessionSettings } from './session.js';

const OPEN_STATUSES = ['lobby', 'active', 'paused', 'finale', 'solved', 'revealed'];

export class SessionManager {
  private sessions = new Map<string, LiveSession>();
  private byCode = new Map<string, string>();
  private ticker: NodeJS.Timeout | null = null;
  private loading = new Map<string, Promise<LiveSession | null>>();

  constructor(private hooks: SessionHooks) {}

  setHooks(h: SessionHooks) {
    this.hooks = h;
  }

  startTicker() {
    this.ticker = setInterval(() => {
      for (const s of this.sessions.values()) {
        try {
          s.tick();
        } catch (e) {
          console.error('[tick]', e);
        }
      }
    }, 5000);
  }

  async shutdown() {
    if (this.ticker) clearInterval(this.ticker);
    await Promise.all([...this.sessions.values()].map((s) => s.save()));
    for (const s of this.sessions.values()) s.dispose();
  }

  all() {
    return [...this.sessions.values()];
  }

  activeForStreamer(streamerId: string) {
    return this.all().find((s) => s.streamerId === streamerId && s.state.status !== 'ended');
  }

  async create(streamer: { id: string; plan: Tier }, caseId: string, settings: Partial<SessionSettings> = {}) {
    const existing = await prisma.gameSession.findFirst({ where: { streamerId: streamer.id, status: { in: OPEN_STATUSES } } });
    if (existing) throw new ActionError('Es läuft bereits eine Ermittlung. Beende sie zuerst.', 'busy');
    const row = await prisma.caseDefinition.findUnique({ where: { id: caseId } });
    if (!row || !row.published) throw new ActionError('Fall nicht gefunden.', 'not_found');
    const lib = await listLibrary(streamer);
    const entry = lib.find((e) => e.id === caseId);
    if (!entry || !entry.playable || !tierAllows(streamer.plan, row.tier)) throw new ActionError(entry?.lockedReason ?? 'Dieser Fall ist für dich nicht freigeschaltet.', 'locked');
    const def = await getCaseDefinition(caseId);
    if (!def) throw new ActionError('Fall konnte nicht geladen werden.');
    const state = createInitialState(def);
    const merged: SessionSettings = { ...DEFAULT_SETTINGS, ...settings, overlay: { ...DEFAULT_SETTINGS.overlay, ...(settings.overlay ?? {}) } };
    let code = joinCode();
    for (let i = 0; i < 5 && (await prisma.gameSession.findUnique({ where: { joinCode: code } })); i++) code = joinCode();
    const created = await prisma.gameSession.create({
      data: { streamerId: streamer.id, caseId, caseVersion: row.version, joinCode: code, status: 'lobby', state: state as object, settings: merged as object },
    });
    return this.load(created.id);
  }

  async get(id: string): Promise<LiveSession | null> {
    const s = this.sessions.get(id);
    if (s) return s;
    if (!this.loading.has(id)) this.loading.set(id, this.load(id).finally(() => this.loading.delete(id)));
    return this.loading.get(id)!;
  }

  async getByCode(code: string): Promise<LiveSession | null> {
    const c = code.toUpperCase();
    const id = this.byCode.get(c);
    if (id) return this.get(id);
    const row = await prisma.gameSession.findUnique({ where: { joinCode: c }, select: { id: true } });
    return row ? this.get(row.id) : null;
  }

  /** Lädt eine Sitzung inklusive aller Teilnehmenden, Theorien und offener Abstimmung aus der Datenbank. */
  private async load(id: string): Promise<LiveSession | null> {
    const row = await prisma.gameSession.findUnique({ where: { id }, include: { streamer: true } });
    if (!row) return null;
    const def = await getCaseDefinition(row.caseId);
    if (!def) return null;
    const state = row.state as unknown as GameState;
    const settings: SessionSettings = {
      ...DEFAULT_SETTINGS,
      ...(row.settings as object),
      overlay: { ...DEFAULT_SETTINGS.overlay, ...((row.settings as { overlay?: object }).overlay ?? {}) },
    };
    const session = new LiveSession(
      row.id,
      row.streamerId,
      { login: row.streamer.login, displayName: row.streamer.displayName, twitchUserId: row.streamer.twitchUserId },
      row.joinCode,
      def,
      state,
      settings,
      {
        changed: (s) => this.hooks.changed(s),
        personal: (s, p) => this.hooks.personal(s, p),
        say: (s, t) => this.hooks.say(s, t),
        notifyStreamer: (s, k, t) => this.hooks.notifyStreamer(s, k, t),
      },
    );
    // Ausfallzeit nicht als Spielzeit zählen.
    session.engine.freezeClock();

    const [participants, theories, messages, mods, openVote] = await Promise.all([
      prisma.participant.findMany({ where: { sessionId: id } }),
      prisma.theory.findMany({ where: { sessionId: id }, include: { participant: { select: { displayName: true } } }, orderBy: { createdAt: 'asc' } }),
      prisma.message.findMany({ where: { sessionId: id }, include: { participant: { select: { displayName: true } } }, orderBy: { createdAt: 'desc' }, take: 150 }),
      prisma.moderator.findMany({ where: { streamerId: row.streamerId } }),
      prisma.vote.findFirst({ where: { sessionId: id, status: 'open' }, include: { ballots: true } }),
    ]);
    for (const p of participants) {
      session.participants.set(p.id, {
        id: p.id,
        displayName: p.displayName,
        login: p.login,
        twitchUserId: p.twitchUserId,
        guestKey: p.guestKey,
        team: p.team,
        points: p.points,
        banned: p.banned,
        source: p.source as 'chat' | 'web',
      });
      session.identities.set(session.identityKey(p), p.id);
    }
    session.theories = theories.map((t) => ({
      id: t.id,
      author: t.participant.displayName,
      authorId: t.participantId,
      suspectId: t.suspectId,
      text: t.text,
      evidenceIds: t.evidenceIds,
      upvotes: t.upvoterIds.length,
      status: t.status as PublicTheory['status'],
      createdAt: t.createdAt.getTime(),
      upvoters: new Set(t.upvoterIds),
    }));
    session.messages = messages.reverse().map((m) => ({ id: m.id, author: m.participant.displayName, authorId: m.participantId, text: m.text, at: m.createdAt.getTime(), hidden: m.hidden }));
    session.moderatorLogins = new Set(mods.map((m) => m.twitchLogin.toLowerCase()));
    if (openVote && OPEN_STATUSES.includes(row.status)) session.restoreVote(openVote, openVote.ballots);

    this.sessions.set(id, session);
    this.byCode.set(row.joinCode, id);
    return session;
  }

  async restoreAll() {
    const rows = await prisma.gameSession.findMany({ where: { status: { in: OPEN_STATUSES } }, select: { id: true } });
    for (const r of rows) await this.get(r.id).catch((e) => console.error('[restore]', r.id, e));
    return rows.length;
  }

  /** Beendete Sitzungen aus dem Speicher entfernen. */
  async unload(id: string) {
    const s = this.sessions.get(id);
    if (!s) return;
    await s.save();
    s.dispose();
    this.sessions.delete(id);
    this.byCode.delete(s.joinCode);
  }

  async refreshModerators(streamerId: string) {
    const mods = await prisma.moderator.findMany({ where: { streamerId } });
    for (const s of this.all()) if (s.streamerId === streamerId) s.moderatorLogins = new Set(mods.map((m) => m.twitchLogin.toLowerCase()));
  }
}
