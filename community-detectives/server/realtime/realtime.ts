/**
 * Echtzeit-Schicht (Socket.IO).
 *
 * Räume pro Sitzung und Rolle:
 *   v:<sid>        Zuschauer (nur öffentliche Sicht)
 *   m:<sid>        Moderation (öffentliche Sicht + ausgeblendete Inhalte)
 *   o:<sid>        Streamer (zusätzlich geheime Spielleiter-Daten)
 *   ov:<streamer>  OBS-Overlay
 *   p:<sid>:<pid>  persönliche Daten eines Teilnehmenden
 *
 * Änderungen werden gedrosselt (max. 4×/s) und nur als Differenz
 * (geänderte Top-Level-Felder) verschickt – wichtig für große Chats.
 */
import type { Server as HttpServer } from 'node:http';
import { Server, type Socket } from 'socket.io';
import { z } from 'zod';
import type { Role } from '../../shared/views.js';
import { GUEST_COOKIE, SESSION_COOKIE, authFromToken, parseCookies, verifyGuest, type AuthInfo } from '../auth/auth.js';
import { config } from '../config.js';
import { prisma } from '../db.js';
import type { SessionManager } from '../game/manager.js';
import { ActionError, sanitize, type LiveSession } from '../game/session.js';
import { RateLimiter } from '../security/rateLimit.js';
import type { ChatBridge } from '../twitch/chatBridge.js';

interface SocketData {
  role: Role;
  sessionId?: string;
  streamerId?: string;
  participantId?: string;
  auth: AuthInfo | null;
  moderator: boolean;
}

type Ack = (r: { ok: boolean; message?: string; code?: string; data?: unknown }) => void;

const connLimiter = new RateLimiter(20, 0.5);
const eventLimiter = new RateLimiter(30, 5);

const viewerActions = {
  mark: z.object({ evidence: z.string().max(64), item: z.string().max(64) }),
  connect: z.object({ a: z.string().max(64), b: z.string().max(64) }),
  answer: z.object({ puzzle: z.string().max(64), answer: z.union([z.string().max(120), z.array(z.string().max(64)).max(20)]) }),
  vote: z.object({ option: z.number().int().min(0).max(20) }),
  theory: z.object({ suspect: z.string().max(64), text: z.string().max(400), evidence: z.array(z.string().max(64)).max(5).default([]) }),
  upvote: z.object({ theory: z.string().max(64) }),
  message: z.object({ text: z.string().max(280) }),
  team: z.object({ team: z.string().max(32) }),
  hint: z.object({}),
};
const modActions = {
  theoryStatus: z.object({ theory: z.string(), status: z.enum(['visible', 'hidden', 'featured']) }),
  hideMessage: z.object({ message: z.string() }),
  ban: z.object({ participant: z.string(), banned: z.boolean() }),
};

export class Realtime {
  io: Server;
  private pending = new Map<string, NodeJS.Timeout>();
  private lastSent = new Map<string, Map<string, string>>();

  constructor(
    http: HttpServer,
    private manager: SessionManager,
    private chat: ChatBridge,
  ) {
    this.io = new Server(http, {
      path: '/socket.io',
      maxHttpBufferSize: 32 * 1024,
      perMessageDeflate: { threshold: 2048 },
      cors: config.isProd ? undefined : { origin: true, credentials: true },
    });
    this.io.use((socket, next) => {
      const ip = socket.handshake.address;
      if (!connLimiter.take(ip)) return next(new Error('Zu viele Verbindungen – bitte kurz warten.'));
      next();
    });
    this.io.on('connection', (socket) => void this.onConnection(socket).catch((e) => this.fail(socket, e)));
    chat.onBotMessage = (streamerId, text) => {
      const s = this.manager.activeForStreamer(streamerId);
      if (s) this.io.to(`o:${s.id}`).emit('bot', { text, at: Date.now() });
    };
    chat.onStatus = (streamerId, status) => {
      const s = this.manager.activeForStreamer(streamerId);
      if (s) this.io.to(`o:${s.id}`).emit('chatStatus', status);
    };
  }

  private fail(socket: Socket, e: unknown) {
    socket.emit('fatal', { message: e instanceof ActionError ? e.message : 'Verbindung fehlgeschlagen.', code: e instanceof ActionError ? e.code : 'error' });
    if (!(e instanceof ActionError)) console.error('[socket]', e);
    socket.disconnect(true);
  }

  /* ------------------------------ Verbindungsaufbau ------------------------------ */

  private async onConnection(socket: Socket) {
    const cookies = parseCookies(socket.handshake.headers.cookie);
    const auth = await authFromToken(cookies[SESSION_COOKIE]);
    const hs = z
      .object({
        mode: z.enum(['viewer', 'control', 'overlay']),
        code: z.string().max(12).optional(),
        sessionId: z.string().max(40).optional(),
        overlayToken: z.string().max(64).optional(),
        guestName: z.string().max(40).optional(),
      })
      .safeParse(socket.handshake.auth);
    if (!hs.success) throw new ActionError('Ungültige Verbindung.');
    const data = socket.data as SocketData;
    data.auth = auth;
    data.moderator = false;

    if (hs.data.mode === 'overlay') {
      const streamer = hs.data.overlayToken ? await prisma.streamer.findUnique({ where: { overlayToken: hs.data.overlayToken } }) : null;
      if (!streamer) throw new ActionError('Ungültiger Overlay-Link.', 'forbidden');
      data.role = 'overlay';
      data.streamerId = streamer.id;
      await socket.join(`ov:${streamer.id}`);
      const s = this.manager.activeForStreamer(streamer.id);
      socket.emit('overlay', s ? s.overlayView(config.PUBLIC_URL) : null);
      return;
    }

    if (hs.data.mode === 'control') {
      if (auth?.kind !== 'streamer' || !auth.streamerId) throw new ActionError('Bitte als Streamer anmelden.', 'unauthorized');
      const s = hs.data.sessionId ? await this.manager.get(hs.data.sessionId) : null;
      if (!s || s.streamerId !== auth.streamerId) throw new ActionError('Sitzung nicht gefunden.', 'not_found');
      data.role = 'owner';
      data.sessionId = s.id;
      data.streamerId = s.streamerId;
      await socket.join(`o:${s.id}`);
      socket.emit('snapshot', this.ownerView(s));
      socket.emit('chatStatus', this.chat.status(s.streamerId, !!(await prisma.twitchToken.findUnique({ where: { streamerId: s.streamerId }, select: { streamerId: true } }))));
      void this.chat.ensure(s.streamerId);
      socket.on('control', (action: unknown, payload: unknown, ack: Ack) => void this.onControl(socket, s, action, payload, ack));
      socket.on('mod', (action: unknown, payload: unknown, ack: Ack) => void this.onMod(socket, s, action, payload, ack));
      return;
    }

    // Zuschauer
    const s = hs.data.code ? await this.manager.getByCode(hs.data.code) : null;
    if (!s || s.state.status === 'ended') throw new ActionError('Keine laufende Ermittlung mit diesem Code.', 'not_found');
    let identity;
    if (auth?.twitchUserId) {
      identity = { twitchUserId: auth.twitchUserId, login: auth.login ?? undefined, displayName: auth.displayName ?? auth.login ?? 'Ermittler', source: 'web' as const };
    } else {
      const guestKey = verifyGuest(cookies[GUEST_COOKIE]);
      const name = sanitize(hs.data.guestName ?? '', 30);
      if (!guestKey || name.length < 2) throw new ActionError('Bitte zuerst einen Namen wählen oder mit Twitch anmelden.', 'need_identity');
      identity = { guestKey, displayName: name.endsWith('(Gast)') ? name : `${name} (Gast)`, source: 'web' as const };
    }
    const p = await s.join(identity, socket.handshake.address);
    if (p.banned) throw new ActionError('Du wurdest von dieser Ermittlung ausgeschlossen.', 'banned');
    data.role = 'viewer';
    data.sessionId = s.id;
    data.participantId = p.id;
    data.moderator = !!(auth?.login && s.moderatorLogins.has(auth.login.toLowerCase())) || (auth?.kind === 'streamer' && auth.streamerId === s.streamerId);
    await socket.join([`v:${s.id}`, `p:${s.id}:${p.id}`]);
    if (data.moderator) await socket.join(`m:${s.id}`);
    socket.emit('snapshot', { ...s.publicView({ moderator: data.moderator }), discussion: s.discussion({ moderator: data.moderator }) });
    socket.emit('me', s.personal(p.id, { verified: !!p.twitchUserId, moderator: data.moderator }));
    socket.on('act', (action: unknown, payload: unknown, ack: Ack) => void this.onViewerAction(socket, s, action, payload, ack));
    if (data.moderator) socket.on('mod', (action: unknown, payload: unknown, ack: Ack) => void this.onMod(socket, s, action, payload, ack));
  }

  /* ------------------------------ Aktionen ------------------------------ */

  private guard(socket: Socket, ack: unknown): ack is Ack {
    if (typeof ack !== 'function') return false;
    if (!eventLimiter.take(socket.id)) {
      (ack as Ack)({ ok: false, message: 'Zu viele Aktionen in kurzer Zeit.', code: 'rate' });
      return false;
    }
    return true;
  }

  private async onViewerAction(socket: Socket, s: LiveSession, action: unknown, payload: unknown, ack: unknown) {
    if (!this.guard(socket, ack)) return;
    const pid = (socket.data as SocketData).participantId!;
    try {
      if (typeof action !== 'string' || !(action in viewerActions)) throw new ActionError('Unbekannte Aktion.');
      const schema = viewerActions[action as keyof typeof viewerActions];
      const parsed = schema.safeParse(payload ?? {});
      if (!parsed.success) throw new ActionError('Ungültige Eingabe.');
      const p = parsed.data as Record<string, any>;
      let result: { ok: boolean; message: string; code?: string; data?: unknown } = { ok: true, message: 'OK' };
      switch (action) {
        case 'mark':
          result = await s.mark(pid, p.evidence, p.item);
          break;
        case 'connect':
          result = await s.connect(pid, p.a, p.b);
          break;
        case 'answer':
          result = await s.answer(pid, p.puzzle, p.answer);
          break;
        case 'vote':
          s.castVote(pid, p.option);
          result = { ok: true, message: 'Stimme gezählt.' };
          break;
        case 'theory':
          await s.submitTheory(pid, p.suspect, p.text, p.evidence);
          result = { ok: true, message: 'Theorie eingereicht.' };
          break;
        case 'upvote':
          await s.upvoteTheory(pid, p.theory);
          break;
        case 'message':
          await s.postMessage(pid, p.text);
          break;
        case 'team':
          await s.setTeam(pid, p.team);
          result = { ok: true, message: 'Team gewählt.' };
          break;
        case 'hint': {
          const n = s.requestHint(pid);
          result = { ok: true, message: `Hinweis angefragt (${n}/${s.settings.hintRequestThreshold}). Die Spielleitung entscheidet.` };
          break;
        }
      }
      ack({ ok: result.ok, message: result.message, code: result.code, data: result.data });
      this.personal(s, pid);
    } catch (e) {
      ack(this.errorAck(e));
    }
  }

  private async onMod(socket: Socket, s: LiveSession, action: unknown, payload: unknown, ack: unknown) {
    if (!this.guard(socket, ack)) return;
    try {
      if (typeof action !== 'string' || !(action in modActions)) throw new ActionError('Unbekannte Aktion.');
      const parsed = modActions[action as keyof typeof modActions].safeParse(payload ?? {});
      if (!parsed.success) throw new ActionError('Ungültige Eingabe.');
      const p = parsed.data as Record<string, any>;
      if (action === 'theoryStatus') await s.moderateTheory(p.theory, p.status);
      if (action === 'hideMessage') await s.hideMessage(p.message);
      if (action === 'ban') {
        await s.setBanned(p.participant, p.banned);
        if (p.banned) this.io.to(`p:${s.id}:${p.participant}`).emit('fatal', { message: 'Du wurdest von der Moderation ausgeschlossen.', code: 'banned' });
      }
      void s.log(`mod:${action}`, { by: (socket.data as SocketData).auth?.login ?? 'streamer', ...p });
      ack({ ok: true, message: 'Erledigt.' });
    } catch (e) {
      ack(this.errorAck(e));
    }
  }

  private async onControl(socket: Socket, s: LiveSession, action: unknown, payload: unknown, ack: unknown) {
    if (typeof ack !== 'function') return;
    try {
      if (typeof action !== 'string') throw new ActionError('Unbekannte Aktion.');
      const res = await s.control(action, (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>);
      (ack as Ack)({ ok: true, message: res.message, data: 'data' in res ? res.data : undefined });
      if (action === 'end') {
        this.chat.stop(s.streamerId);
        this.io.to(`ov:${s.streamerId}`).emit('overlay', null);
      }
    } catch (e) {
      (ack as Ack)(this.errorAck(e));
    }
  }

  private errorAck(e: unknown) {
    if (e instanceof ActionError) return { ok: false, message: e.message, code: e.code };
    console.error('[action]', e);
    return { ok: false, message: 'Interner Fehler.', code: 'error' };
  }

  /* ------------------------------ Verteilen ------------------------------ */

  private ownerView(s: LiveSession) {
    return {
      ...s.publicView({ moderator: true }),
      discussion: s.discussion({ moderator: true }),
      secrets: s.secrets(),
      sessionSettings: s.settings,
      participantList: [...s.participants.values()]
        .sort((a, b) => b.points - a.points)
        .slice(0, 300)
        .map((p) => ({ id: p.id, name: p.displayName, points: p.points, team: p.team, banned: p.banned, source: p.source, verified: !!p.twitchUserId })),
      hintRequests: s.hintRequests.size,
      lastVote: s.publicVote(s.lastVote),
      overlayPreview: s.overlayView(config.PUBLIC_URL),
    };
  }

  changed(s: LiveSession) {
    if (this.pending.has(s.id)) return;
    this.pending.set(
      s.id,
      setTimeout(() => {
        this.pending.delete(s.id);
        try {
          this.flush(s);
        } catch (e) {
          console.error('[flush]', e);
        }
      }, 250),
    );
  }

  private diff(room: string, view: Record<string, unknown>) {
    let last = this.lastSent.get(room);
    if (!last) this.lastSent.set(room, (last = new Map()));
    const patch: Record<string, unknown> = {};
    let changed = false;
    for (const [k, v] of Object.entries(view)) {
      if (k === 'serverNow') continue;
      const str = JSON.stringify(v ?? null);
      if (last.get(k) !== str) {
        last.set(k, str);
        patch[k] = v;
        changed = true;
      }
    }
    if (!changed) return null;
    patch.serverNow = Date.now();
    return patch;
  }

  flush(s: LiveSession) {
    const rooms = this.io.sockets.adapter.rooms;
    if (rooms.get(`v:${s.id}`)?.size) {
      const p = this.diff(`v:${s.id}`, { ...s.publicView(), discussion: s.discussion() });
      if (p) this.io.to(`v:${s.id}`).except(`m:${s.id}`).emit('patch', p);
    }
    if (rooms.get(`m:${s.id}`)?.size) {
      const p = this.diff(`m:${s.id}`, { ...s.publicView({ moderator: true }), discussion: s.discussion({ moderator: true }) });
      if (p) this.io.to(`m:${s.id}`).emit('patch', p);
    }
    if (rooms.get(`o:${s.id}`)?.size) {
      const p = this.diff(`o:${s.id}`, this.ownerView(s));
      if (p) this.io.to(`o:${s.id}`).emit('patch', p);
    }
    if (rooms.get(`ov:${s.streamerId}`)?.size) {
      const view = s.state.status === 'ended' ? null : s.overlayView(config.PUBLIC_URL);
      const str = JSON.stringify({ ...view, serverNow: 0 });
      const last = this.lastSent.get(`ov:${s.streamerId}`) ?? new Map();
      if (last.get('all') !== str) {
        last.set('all', str);
        this.lastSent.set(`ov:${s.streamerId}`, last);
        this.io.to(`ov:${s.streamerId}`).emit('overlay', view);
      }
    }
  }

  personal(s: LiveSession, pid: string) {
    const p = s.participants.get(pid);
    if (!p) return;
    const sockets = this.io.sockets.adapter.rooms.get(`p:${s.id}:${pid}`);
    if (!sockets?.size) return;
    for (const sid of sockets) {
      const sock = this.io.sockets.sockets.get(sid);
      if (!sock) continue;
      sock.emit('me', s.personal(pid, { verified: !!p.twitchUserId, moderator: (sock.data as SocketData).moderator }));
    }
  }

  notifyStreamer(s: LiveSession, kind: string, text: string) {
    this.io.to(`o:${s.id}`).emit('notice', { kind, text, at: Date.now() });
  }
}
