/**
 * Testet die echte Twitch-Integration (OAuth Authorization Code Flow,
 * Helix, EventSub-WebSocket) gegen einen lokalen Mock, der das offizielle
 * Nachrichtenformat nachbildet. Es werden keine Twitch-Funktionen im
 * Produktivcode simuliert – nur die Gegenstelle ist ein Testdouble.
 */
import express from 'express';
import { createServer, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { WebSocketServer, type WebSocket } from 'ws';
import request from 'supertest';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
async function until(fn: () => boolean, ms = 5000) {
  const t = Date.now();
  while (!fn()) {
    if (Date.now() - t > ms) throw new Error('Timeout');
    await wait(25);
  }
}

const mock = {
  subscriptions: [] as { type: string; condition: Record<string, string>; transport: { session_id: string } }[],
  chat: [] as { message: string; sender_id: string }[],
  tokenCalls: [] as string[],
  fail401Once: false,
  sockets: [] as WebSocket[],
  sessionSeq: 0,
};

let api: Server;
let wss: WebSocketServer;
let apiBase = '';
let wsBase = '';
let app: any;
let base = '';

function welcome(ws: WebSocket) {
  mock.sessionSeq += 1;
  ws.send(JSON.stringify({ metadata: { message_id: `w${mock.sessionSeq}`, message_type: 'session_welcome', message_timestamp: new Date().toISOString() }, payload: { session: { id: `sess_${mock.sessionSeq}`, status: 'connected', keepalive_timeout_seconds: 10, reconnect_url: null } } }));
}
function chatNotification(ws: WebSocket, text: string, user = { id: '9001', login: 'zuschauerin', name: 'Zuschauerin' }) {
  ws.send(
    JSON.stringify({
      metadata: { message_id: `n${Math.random()}`, message_type: 'notification', message_timestamp: new Date().toISOString(), subscription_type: 'channel.chat.message' },
      payload: {
        subscription: { type: 'channel.chat.message' },
        event: {
          broadcaster_user_id: '424242',
          chatter_user_id: user.id,
          chatter_user_login: user.login,
          chatter_user_name: user.name,
          message_id: `m${Math.random()}`,
          message: { text, fragments: [] },
          badges: [],
        },
      },
    }),
  );
}

beforeAll(async () => {
  const m = express();
  m.use(express.urlencoded({ extended: false }));
  m.use(express.json());
  m.post('/oauth2/token', (req, res) => {
    mock.tokenCalls.push(req.body.grant_type);
    if (req.body.client_secret !== 'secret') return res.status(401).json({ message: 'invalid client' });
    res.json({ access_token: `access_${mock.tokenCalls.length}`, refresh_token: `refresh_${mock.tokenCalls.length}`, expires_in: 14400, scope: ['user:read:chat', 'user:write:chat'], token_type: 'bearer' });
  });
  m.post('/oauth2/revoke', (_req, res) => res.sendStatus(200));
  m.get('/helix/users', (req, res) => {
    if (!req.headers.authorization?.startsWith('Bearer access_')) return res.sendStatus(401);
    res.json({ data: [{ id: '424242', login: 'echter_streamer', display_name: 'EchterStreamer', profile_image_url: '' }] });
  });
  m.post('/helix/eventsub/subscriptions', (req, res) => {
    mock.subscriptions.push(req.body);
    res.status(202).json({ data: [{ id: 'sub1', status: 'enabled' }] });
  });
  m.post('/helix/chat/messages', (req, res) => {
    if (mock.fail401Once) {
      mock.fail401Once = false;
      return res.sendStatus(401);
    }
    mock.chat.push(req.body);
    res.json({ data: [{ message_id: 'x', is_sent: true }] });
  });
  api = createServer(m);
  await new Promise<void>((r) => api.listen(0, r));
  apiBase = `http://127.0.0.1:${(api.address() as AddressInfo).port}`;

  wss = new WebSocketServer({ port: 0 });
  wss.on('connection', (ws) => {
    mock.sockets.push(ws);
    welcome(ws);
  });
  wsBase = `ws://127.0.0.1:${(wss.address() as AddressInfo).port}`;

  Object.assign(process.env, {
    TWITCH_CLIENT_ID: 'client',
    TWITCH_CLIENT_SECRET: 'secret',
    TWITCH_AUTH_BASE: apiBase,
    TWITCH_API_BASE: `${apiBase}/helix`,
    TWITCH_EVENTSUB_WS_URL: `${wsBase}/ws`,
    PUBLIC_URL: 'http://localhost:9999',
  });
  const { createApp } = await import('../server/app.js');
  const { importCases } = await import('../server/game/importCases.js');
  await importCases();
  app = await createApp({ serveStatic: false });
  await new Promise<void>((r) => app.server.listen(0, r));
  base = `http://127.0.0.1:${(app.server.address() as AddressInfo).port}`;
});

afterAll(async () => {
  app?.chat.stopAll();
  await app?.manager.shutdown();
  app?.realtime.io.close();
  await new Promise((r) => app?.server.close(r));
  wss.close();
  api.close();
  const { prisma } = await import('../server/db.js');
  await prisma.$disconnect();
});

describe('Twitch-Integration', () => {
  let cookie = '';
  it('OAuth: Login leitet mit State und Scopes zu Twitch weiter', async () => {
    const r = await request(base).get('/api/auth/twitch/login?role=streamer');
    expect(r.status).toBe(302);
    const loc = new URL(r.headers.location);
    expect(loc.origin).toBe(apiBase);
    expect(loc.searchParams.get('scope')).toBe('user:read:chat user:write:chat');
    expect(loc.searchParams.get('redirect_uri')).toBe('http://localhost:9999/api/auth/twitch/callback');
    const stateCookie = (r.headers['set-cookie'] as unknown as string[])[0].split(';')[0];

    // Manipulierter State wird abgelehnt
    const bad = await request(base).get(`/api/auth/twitch/callback?code=abc&state=${encodeURIComponent('foo.bar')}`).set('Cookie', stateCookie);
    expect(bad.status).toBe(400);

    const cb = await request(base).get(`/api/auth/twitch/callback?code=abc&state=${encodeURIComponent(loc.searchParams.get('state')!)}`).set('Cookie', stateCookie);
    expect(cb.status).toBe(302);
    expect(cb.headers.location).toBe('/dashboard');
    cookie = (cb.headers['set-cookie'] as unknown as string[]).map((c) => c.split(';')[0]).filter((c) => c.startsWith('cd_session')).join('; ');
    expect(cookie).toContain('cd_session=');
  });

  it('Tokens werden verschlüsselt gespeichert', async () => {
    const { prisma } = await import('../server/db.js');
    const t = await prisma.twitchToken.findFirst({ where: { streamer: { login: 'echter_streamer' } } });
    expect(t).not.toBeNull();
    expect(t!.accessTokenEnc).not.toContain('access_');
    expect(t!.scopes).toContain('user:read:chat');
  });

  it('EventSub: nach session_welcome wird channel.chat.message abonniert', async () => {
    await until(() => mock.subscriptions.length >= 1);
    const sub = mock.subscriptions[0];
    expect(sub.type).toBe('channel.chat.message');
    expect(sub.condition).toEqual({ broadcaster_user_id: '424242', user_id: '424242' });
    expect(sub.transport.session_id).toBe('sess_1');
    const me = await request(base).get('/api/me').set('Cookie', cookie);
    expect(me.body.streamer.chat.connected).toBe(true);
  });

  it('Chatnachrichten aus EventSub steuern die Ermittlung, Antworten gehen über Helix', async () => {
    const created = await request(base).post('/api/sessions').set('Cookie', cookie).send({ caseId: 'der-perfekte-einbruch' });
    expect(created.status).toBe(201);
    const live = await app.manager.get(created.body.id);
    await live.control('start', {});
    await live.control('startVote', { kind: 'interrogate', seconds: 60 });
    await until(() => mock.chat.some((c) => c.message.includes('Wen sollen wir')));
    expect(mock.chat[0].sender_id).toBe('424242');

    const ws = mock.sockets.at(-1)!;
    chatNotification(ws, '!a 2');
    chatNotification(ws, '!ermitteln', { id: '9002', login: 'detektiv', name: 'Detektiv' });
    await until(() => live.vote?.ballots.size === 1 && live.participants.size === 2);
    const p = [...live.participants.values()].find((x: any) => x.twitchUserId === '9001');
    expect(live.vote.ballots.get(p.id)).toBe(1);
  });

  it('Helix: abgelaufenes Token wird bei 401 automatisch erneuert', async () => {
    const live = app.manager.all()[0];
    const refreshesBefore = mock.tokenCalls.filter((g) => g === 'refresh_token').length;
    mock.fail401Once = true;
    app.chat.say(live, 'Test nach Token-Ablauf');
    await until(() => mock.chat.some((c) => c.message === 'Test nach Token-Ablauf'), 8000);
    expect(mock.tokenCalls.filter((g) => g === 'refresh_token').length).toBe(refreshesBefore + 1);
  });

  it('EventSub: session_reconnect migriert ohne neues Abo', async () => {
    const subsBefore = mock.subscriptions.length;
    const old = mock.sockets.at(-1)!;
    old.send(JSON.stringify({ metadata: { message_id: 'r1', message_type: 'session_reconnect', message_timestamp: new Date().toISOString() }, payload: { session: { id: 'x', status: 'reconnecting', reconnect_url: `${wsBase}/reconnect` } } }));
    await until(() => mock.sockets.length >= 2 && old.readyState === old.CLOSED, 5000);
    expect(mock.subscriptions.length).toBe(subsBefore);
    const live = app.manager.all()[0];
    chatNotification(mock.sockets.at(-1)!, '!team archiv', { id: '9003', login: 'archivar', name: 'Archivar' });
    await until(() => [...live.participants.values()].some((x: any) => x.twitchUserId === '9003' && x.team === 'archiv'));
  });

  it('EventSub: Verbindungsabbruch → automatische Wiederverbindung und neues Abo', async () => {
    const subsBefore = mock.subscriptions.length;
    mock.sockets.at(-1)!.terminate();
    await until(() => mock.subscriptions.length === subsBefore + 1, 8000);
    const me = await request(base).get('/api/me').set('Cookie', cookie);
    expect(me.body.streamer.chat.connected).toBe(true);
  });
});
