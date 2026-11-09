import express, { type NextFunction, type Request, type Response, Router } from 'express';
import { z } from 'zod';
import { config } from '../config.js';
import { prisma } from '../db.js';
import {
  GUEST_COOKIE,
  STATE_COOKIE,
  authFromToken,
  cookieOpts,
  createAuthSession,
  destroyAuthSession,
  isAdmin,
  makeOAuthState,
  readOAuthState,
  safeReturn,
  SESSION_COOKIE,
  signGuest,
  upsertStreamer,
  verifyGuest,
  type AuthInfo,
} from '../auth/auth.js';
import { importCases } from '../game/importCases.js';
import { listLibrary, pickCase } from '../game/library.js';
import type { SessionManager } from '../game/manager.js';
import { ActionError, sanitize } from '../game/session.js';
import { randomToken } from '../security/crypto.js';
import { RateLimiter } from '../security/rateLimit.js';
import { authorizeUrl, exchangeCode, getUserByToken, revokeToken, storeTokens, TwitchError } from '../twitch/api.js';
import type { ChatBridge } from '../twitch/chatBridge.js';

declare module 'express-serve-static-core' {
  interface Request {
    auth?: AuthInfo | null;
  }
}

const apiLimiter = new RateLimiter(120, 4);
const authLimiter = new RateLimiter(10, 0.2);

const wrap = (fn: (req: Request, res: Response) => Promise<unknown>) => (req: Request, res: Response, next: NextFunction) => {
  fn(req, res).catch(next);
};

function body<T extends z.ZodType>(schema: T, req: Request): z.infer<T> {
  const r = schema.safeParse(req.body ?? {});
  if (!r.success) throw new ActionError(`Ungültige Eingabe: ${r.error.issues.map((i) => `${i.path.join('.')} ${i.message}`).join(', ')}`, 'validation');
  return r.data;
}

async function currentStreamer(req: Request) {
  if (req.auth?.kind !== 'streamer' || !req.auth.streamerId) throw new ActionError('Bitte als Streamer anmelden.', 'unauthorized');
  const s = await prisma.streamer.findUnique({ where: { id: req.auth.streamerId }, include: { token: { select: { scopes: true, expiresAt: true } } } });
  if (!s) throw new ActionError('Account nicht gefunden.', 'unauthorized');
  return s;
}

function requireAdmin(req: Request) {
  if (!isAdmin(req.auth?.login) && !(config.devLogin && !config.isProd && req.auth?.kind === 'streamer')) {
    throw new ActionError('Nur für Administratoren.', 'forbidden');
  }
}

export function apiRouter(manager: SessionManager, chat: ChatBridge) {
  const r = Router();
  r.use(express.json({ limit: '32kb' }));

  r.use((req, res, next) => {
    if (!apiLimiter.take(req.ip ?? 'unknown')) {
      res.status(429).json({ error: 'Zu viele Anfragen.' });
      return;
    }
    authFromToken(req.cookies?.[SESSION_COOKIE])
      .then((a) => {
        req.auth = a;
        next();
      })
      .catch(next);
  });

  /* ------------------------------ Öffentlich ------------------------------ */

  r.get('/config', (_req, res) => {
    res.json({ twitchEnabled: config.twitchEnabled, devLogin: config.devLogin, chatSimulator: config.chatSimulator, publicUrl: config.PUBLIC_URL });
  });

  r.get(
    '/me',
    wrap(async (req, res) => {
      if (!req.auth) return res.json({ auth: null });
      if (req.auth.kind === 'streamer') {
        const s = await currentStreamer(req);
        const active = manager.activeForStreamer(s.id) ?? null;
        const mods = await prisma.moderator.findMany({ where: { streamerId: s.id }, orderBy: { twitchLogin: 'asc' } });
        return res.json({
          auth: req.auth,
          streamer: {
            id: s.id,
            login: s.login,
            displayName: s.displayName,
            profileImage: s.profileImage,
            plan: s.plan,
            overlayUrl: `${config.PUBLIC_URL.replace(/\/$/, '')}/overlay/${s.overlayToken}`,
            twitchLinked: !!s.token,
            scopes: s.token?.scopes ?? [],
            chat: chat.status(s.id, !!s.token),
            activeSessionId: active?.id ?? null,
            moderators: mods.map((m) => m.twitchLogin),
            isAdmin: isAdmin(s.login) || (config.devLogin && !config.isProd),
          },
        });
      }
      return res.json({ auth: req.auth });
    }),
  );

  r.get(
    '/play/:code',
    wrap(async (req, res) => {
      const s = await manager.getByCode(String(req.params.code));
      if (!s || s.state.status === 'ended') return res.status(404).json({ error: 'Keine laufende Ermittlung mit diesem Code.' });
      const guest = verifyGuest(req.cookies?.[GUEST_COOKIE]);
      res.json({
        sessionId: s.id,
        code: s.joinCode,
        title: s.def.title,
        tagline: s.def.tagline,
        accent: s.def.accent,
        streamer: s.streamer.displayName,
        status: s.state.status,
        allowGuests: s.settings.allowGuests,
        guestsCanVote: s.settings.guestsCanVote,
        hasGuestKey: !!guest,
      });
    }),
  );

  r.post(
    '/play/:code/guest',
    wrap(async (req, res) => {
      if (!authLimiter.take(`guest:${req.ip}`)) throw new ActionError('Zu viele Versuche.', 'rate');
      const { name } = body(z.object({ name: z.string().min(2).max(24) }), req);
      const clean = sanitize(name, 24).replace(/[^\p{L}\p{N} _.-]/gu, '');
      if (clean.length < 2) throw new ActionError('Bitte einen Namen mit mindestens zwei Zeichen wählen.');
      const s = await manager.getByCode(String(req.params.code));
      if (!s) throw new ActionError('Ermittlung nicht gefunden.', 'not_found');
      if (!s.settings.allowGuests) throw new ActionError('Diese Ermittlung erlaubt nur Twitch-Logins.', 'guests_disabled');
      const key = verifyGuest(req.cookies?.[GUEST_COOKIE]) ?? randomToken(16);
      res.cookie(GUEST_COOKIE, signGuest(key), cookieOpts(7 * 86400_000));
      res.json({ ok: true, name: `${clean} (Gast)` });
    }),
  );

  /* ------------------------------ Anmeldung ------------------------------ */

  r.get('/auth/twitch/login', (req, res) => {
    if (!config.twitchEnabled) return res.status(400).send('Twitch ist nicht konfiguriert (TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET).');
    const role = req.query.role === 'viewer' ? 'viewer' : 'streamer';
    const { state, nonce } = makeOAuthState({ role, returnTo: safeReturn(String(req.query.return ?? (role === 'streamer' ? '/dashboard' : '/'))) });
    res.cookie(STATE_COOKIE, nonce, cookieOpts(10 * 60_000));
    const redirect = `${config.PUBLIC_URL.replace(/\/$/, '')}/api/auth/twitch/callback`;
    res.redirect(authorizeUrl(state, role === 'streamer' ? config.twitchScopes : [], redirect, role === 'streamer'));
  });

  r.get(
    '/auth/twitch/callback',
    wrap(async (req, res) => {
      if (!authLimiter.take(`cb:${req.ip}`)) return res.status(429).send('Zu viele Anmeldeversuche.');
      const st = readOAuthState(String(req.query.state ?? ''), req.cookies?.[STATE_COOKIE]);
      res.clearCookie(STATE_COOKIE, { path: '/' });
      if (!st) return res.status(400).send('Ungültiger oder abgelaufener Anmeldevorgang. Bitte erneut versuchen.');
      if (req.query.error) return res.redirect(`${st.returnTo}${st.returnTo.includes('?') ? '&' : '?'}login=abgebrochen`);
      const redirect = `${config.PUBLIC_URL.replace(/\/$/, '')}/api/auth/twitch/callback`;
      try {
        const tokens = await exchangeCode(String(req.query.code ?? ''), redirect);
        const user = await getUserByToken(tokens.access_token);
        if (st.role === 'streamer') {
          const missing = config.twitchScopes.filter((s) => !(tokens.scope ?? []).includes(s));
          if (missing.length) return res.status(400).send(`Fehlende Berechtigungen: ${missing.join(', ')}`);
          const streamer = await upsertStreamer({ id: user.id, login: user.login, displayName: user.display_name, profileImage: user.profile_image_url });
          await storeTokens(streamer.id, tokens);
          await createAuthSession(res, { kind: 'streamer', streamerId: streamer.id, twitchUserId: user.id, login: user.login, displayName: user.display_name });
          await chat.restart(streamer.id);
        } else {
          // Zuschauer: Token wird nur zur Identifikation genutzt und sofort widerrufen.
          await createAuthSession(res, { kind: 'viewer', streamerId: null, twitchUserId: user.id, login: user.login, displayName: user.display_name });
          void revokeToken(tokens.access_token);
        }
        res.redirect(st.returnTo);
      } catch (e) {
        console.error('[oauth]', e);
        res.status(502).send(e instanceof TwitchError ? `Twitch-Anmeldung fehlgeschlagen: ${e.message}` : 'Anmeldung fehlgeschlagen.');
      }
    }),
  );

  r.post(
    '/auth/dev/login',
    wrap(async (req, res) => {
      if (!config.devLogin) throw new ActionError('Der Entwicklungs-Login ist deaktiviert.', 'forbidden');
      const { login, role } = body(z.object({ login: z.string().regex(/^[a-zA-Z0-9_]{3,25}$/, 'Twitch-ähnlicher Name (3–25 Zeichen)'), role: z.enum(['streamer', 'viewer']) }), req);
      if (role === 'streamer') {
        const s = await upsertStreamer({ login, displayName: login });
        if (s.plan === 'free' && !config.isProd) await prisma.streamer.update({ where: { id: s.id }, data: { plan: 'premium' } });
        await createAuthSession(res, { kind: 'streamer', streamerId: s.id, twitchUserId: null, login: s.login, displayName: s.displayName });
      } else {
        await createAuthSession(res, { kind: 'viewer', streamerId: null, twitchUserId: `dev:${login.toLowerCase()}`, login: login.toLowerCase(), displayName: login });
      }
      res.json({ ok: true });
    }),
  );

  r.post(
    '/auth/logout',
    wrap(async (req, res) => {
      await destroyAuthSession(req, res);
      res.json({ ok: true });
    }),
  );

  /* ------------------------------ Streamer ------------------------------ */

  r.get(
    '/library',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      res.json({ plan: s.plan, cases: await listLibrary({ id: s.id, plan: s.plan }) });
    }),
  );

  r.post(
    '/library/assign',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      const { difficulty } = body(z.object({ difficulty: z.enum(['einsteiger', 'fortgeschritten', 'experte', 'meisterdetektiv']).optional() }), req);
      const pick = pickCase(await listLibrary({ id: s.id, plan: s.plan }), { difficulty });
      if (!pick) throw new ActionError('Kein spielbarer Fall verfügbar.', 'not_found');
      res.json({ case: pick });
    }),
  );

  r.post(
    '/sessions',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      const input = body(
        z.object({
          caseId: z.string().min(1),
          settings: z
            .object({
              allowGuests: z.boolean().optional(),
              guestsCanVote: z.boolean().optional(),
              timedEvents: z.boolean().optional(),
              discussion: z.boolean().optional(),
              theories: z.boolean().optional(),
              voteSeconds: z.number().int().min(15).max(600).optional(),
            })
            .optional(),
        }),
        req,
      );
      const session = await manager.create({ id: s.id, plan: s.plan }, input.caseId, input.settings ?? {});
      if (!session) throw new ActionError('Sitzung konnte nicht erstellt werden.');
      void chat.ensure(s.id);
      res.status(201).json({ id: session.id, joinCode: session.joinCode });
    }),
  );

  r.get(
    '/sessions',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      const rows = await prisma.gameSession.findMany({
        where: { streamerId: s.id },
        orderBy: { createdAt: 'desc' },
        take: 50,
        include: { case: { select: { title: true, difficulty: true, genre: true } }, _count: { select: { participants: true } } },
      });
      res.json({
        sessions: rows.map((r) => ({
          id: r.id,
          caseId: r.caseId,
          title: r.case.title,
          difficulty: r.case.difficulty,
          genre: r.case.genre,
          status: r.status,
          joinCode: r.joinCode,
          participants: r._count.participants,
          createdAt: r.createdAt,
          endedAt: r.endedAt,
          solved: Array.isArray((r.state as { accusations?: { correct: boolean }[] }).accusations)
            ? (r.state as { accusations: { correct: boolean }[] }).accusations.some((a) => a.correct)
            : false,
        })),
      });
    }),
  );

  r.get(
    '/sessions/:id/results',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      const row = await prisma.gameSession.findFirst({ where: { id: String(req.params.id), streamerId: s.id }, include: { case: true } });
      if (!row) throw new ActionError('Nicht gefunden.', 'not_found');
      const state = row.state as { insights?: Record<string, unknown>; accusations?: { suspect: string; correct: boolean }[]; elapsedMs?: number; puzzles?: Record<string, { solvedAt?: number }> };
      const [top, count, theories, votes] = await Promise.all([
        prisma.participant.findMany({ where: { sessionId: row.id, banned: false }, orderBy: { points: 'desc' }, take: 25 }),
        prisma.participant.count({ where: { sessionId: row.id } }),
        prisma.theory.count({ where: { sessionId: row.id } }),
        prisma.vote.count({ where: { sessionId: row.id } }),
      ]);
      const def = row.case.data as { insights: unknown[]; puzzles: unknown[] };
      res.json({
        id: row.id,
        title: row.case.title,
        status: row.status,
        elapsedMs: state.elapsedMs ?? 0,
        insights: Object.keys(state.insights ?? {}).length,
        insightsTotal: def.insights.length,
        puzzlesSolved: Object.values(state.puzzles ?? {}).filter((p) => p.solvedAt !== undefined).length,
        puzzlesTotal: def.puzzles.length,
        accusations: state.accusations ?? [],
        participants: count,
        theories,
        votes,
        leaderboard: top.map((p) => ({ id: p.id, name: p.displayName, points: p.points, team: p.team })),
      });
    }),
  );

  r.post(
    '/sessions/:id/unload',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      const live = await manager.get(String(req.params.id));
      if (!live || live.streamerId !== s.id) throw new ActionError('Nicht gefunden.', 'not_found');
      if (live.state.status !== 'ended') throw new ActionError('Nur beendete Sitzungen können archiviert werden.');
      await manager.unload(live.id);
      res.json({ ok: true });
    }),
  );

  r.post(
    '/sessions/:id/simulate-chat',
    wrap(async (req, res) => {
      if (!config.chatSimulator) throw new ActionError('Chat-Simulator ist deaktiviert.', 'forbidden');
      const s = await currentStreamer(req);
      const live = await manager.get(String(req.params.id));
      if (!live || live.streamerId !== s.id) throw new ActionError('Nicht gefunden.', 'not_found');
      const { user, text } = body(z.object({ user: z.string().regex(/^[a-zA-Z0-9_]{2,25}$/), text: z.string().min(1).max(500) }), req);
      const result = await chat.handle(live, { userId: `sim:${user.toLowerCase()}`, userLogin: user.toLowerCase(), userName: user, text });
      res.json({ ok: true, result });
    }),
  );

  r.get(
    '/community/leaderboard',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      const rows = await prisma.participant.groupBy({
        by: ['twitchUserId'],
        where: { session: { streamerId: s.id }, twitchUserId: { not: null }, banned: false },
        _sum: { points: true },
        _count: { _all: true },
        orderBy: { _sum: { points: 'desc' } },
        take: 25,
      });
      const names = await prisma.participant.findMany({
        where: { twitchUserId: { in: rows.map((r) => r.twitchUserId!) }, session: { streamerId: s.id } },
        orderBy: { lastSeenAt: 'desc' },
        distinct: ['twitchUserId'],
        select: { twitchUserId: true, displayName: true },
      });
      const nameMap = new Map(names.map((n) => [n.twitchUserId, n.displayName]));
      res.json({ entries: rows.map((r) => ({ name: nameMap.get(r.twitchUserId) ?? '?', points: r._sum.points ?? 0, cases: r._count._all })) });
    }),
  );

  r.post(
    '/streamer/overlay-token',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      const token = randomToken(24);
      await prisma.streamer.update({ where: { id: s.id }, data: { overlayToken: token } });
      res.json({ overlayUrl: `${config.PUBLIC_URL.replace(/\/$/, '')}/overlay/${token}` });
    }),
  );

  r.post(
    '/streamer/moderators',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      const { login } = body(z.object({ login: z.string().regex(/^[a-zA-Z0-9_]{3,25}$/) }), req);
      await prisma.moderator.upsert({ where: { streamerId_twitchLogin: { streamerId: s.id, twitchLogin: login.toLowerCase() } }, create: { streamerId: s.id, twitchLogin: login.toLowerCase() }, update: {} });
      await manager.refreshModerators(s.id);
      res.json({ ok: true });
    }),
  );

  r.delete(
    '/streamer/moderators/:login',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      await prisma.moderator.deleteMany({ where: { streamerId: s.id, twitchLogin: String(req.params.login).toLowerCase() } });
      await manager.refreshModerators(s.id);
      res.json({ ok: true });
    }),
  );

  r.post(
    '/streamer/twitch/reconnect',
    wrap(async (req, res) => {
      const s = await currentStreamer(req);
      await chat.restart(s.id);
      res.json({ ok: true });
    }),
  );

  /* ------------------------------ Administration ------------------------------ */

  r.get(
    '/admin/cases',
    wrap(async (req, res) => {
      requireAdmin(req);
      const rows = await prisma.caseDefinition.findMany({ orderBy: { title: 'asc' }, include: { reservations: { include: { streamer: { select: { login: true } } } }, _count: { select: { sessions: true } } } });
      res.json({
        cases: rows.map((r) => ({
          id: r.id,
          title: r.title,
          version: r.version,
          genre: r.genre,
          difficulty: r.difficulty,
          tier: r.tier,
          published: r.published,
          exclusive: r.exclusive,
          eventTag: r.eventTag,
          importedAt: r.importedAt,
          validation: r.validation,
          sessions: r._count.sessions,
          reservations: r.reservations.map((x) => x.streamer.login),
        })),
      });
    }),
  );

  r.post(
    '/admin/cases/import',
    wrap(async (req, res) => {
      requireAdmin(req);
      res.json({ results: await importCases() });
    }),
  );

  r.post(
    '/admin/cases/:id/publish',
    wrap(async (req, res) => {
      requireAdmin(req);
      const { published } = body(z.object({ published: z.boolean() }), req);
      const row = await prisma.caseDefinition.findUnique({ where: { id: String(req.params.id) } });
      if (!row) throw new ActionError('Nicht gefunden.', 'not_found');
      if (published && !(row.validation as { ok?: boolean }).ok) throw new ActionError('Fälle mit Validierungsfehlern können nicht veröffentlicht werden.');
      await prisma.caseDefinition.update({ where: { id: row.id }, data: { published } });
      res.json({ ok: true });
    }),
  );

  r.post(
    '/admin/reservations',
    wrap(async (req, res) => {
      requireAdmin(req);
      const { caseId, login } = body(z.object({ caseId: z.string(), login: z.string() }), req);
      const s = await prisma.streamer.findUnique({ where: { login: login.toLowerCase() } });
      if (!s) throw new ActionError('Streamer nicht gefunden (muss sich einmal angemeldet haben).', 'not_found');
      await prisma.caseReservation.upsert({ where: { caseId_streamerId: { caseId, streamerId: s.id } }, create: { caseId, streamerId: s.id }, update: {} });
      res.json({ ok: true });
    }),
  );

  r.post(
    '/admin/streamers/:login/plan',
    wrap(async (req, res) => {
      requireAdmin(req);
      const { plan } = body(z.object({ plan: z.enum(['free', 'creator', 'premium']) }), req);
      await prisma.streamer.update({ where: { login: String(req.params.login).toLowerCase() }, data: { plan } });
      res.json({ ok: true });
    }),
  );

  /* ------------------------------ Fehler ------------------------------ */

  r.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
    if (err instanceof ActionError) {
      const status = { unauthorized: 401, forbidden: 403, not_found: 404, rate: 429, busy: 409, locked: 403 }[err.code] ?? 400;
      return res.status(status).json({ error: err.message, code: err.code });
    }
    console.error('[api]', err);
    res.status(500).json({ error: 'Interner Fehler.' });
  });
  return r;
}
