/**
 * Integrationstest: echter Express-Server, echte PostgreSQL-Testdatenbank,
 * echte Socket.IO-Verbindungen. Prüft Login, Fallstart, Rollen-Trennung,
 * Spoilerschutz über das Netzwerk, Chatbefehle, Punkte und Wiederherstellung.
 */
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import request from 'supertest';
import { io as ioc, type Socket } from 'socket.io-client';
import { createApp } from '../server/app.js';
import { prisma } from '../server/db.js';
import { importCases } from '../server/game/importCases.js';
import { SessionManager } from '../server/game/manager.js';

let ctx: Awaited<ReturnType<typeof createApp>>;
let base: string;
const sockets: Socket[] = [];

async function login(role: 'streamer' | 'viewer', name: string) {
  const res = await request(base).post('/api/auth/dev/login').send({ login: name, role });
  expect(res.status).toBe(200);
  return (res.headers['set-cookie'] as unknown as string[]).map((c) => c.split(';')[0]).join('; ');
}

function connect(auth: Record<string, unknown>, cookie?: string) {
  const s = ioc(base, { path: '/socket.io', auth, transports: ['websocket'], extraHeaders: cookie ? { cookie } : undefined, forceNew: true, reconnection: false });
  sockets.push(s);
  return s;
}
const once = <T,>(s: Socket, ev: string) => new Promise<T>((res) => s.once(ev, res));
const emit = (s: Socket, ev: string, action: string, payload: unknown = {}) =>
  new Promise<{ ok: boolean; message?: string; code?: string }>((res) => s.emit(ev, action, payload, res));
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

beforeAll(async () => {
  const results = await importCases();
  expect(results.every((r) => r.ok)).toBe(true);
  ctx = await createApp({ serveStatic: false });
  await new Promise<void>((r) => ctx.server.listen(0, r));
  base = `http://127.0.0.1:${(ctx.server.address() as AddressInfo).port}`;
});

afterAll(async () => {
  sockets.forEach((s) => s.disconnect());
  await ctx.manager.shutdown();
  ctx.realtime.io.close();
  await new Promise((r) => ctx.server.close(r));
  await prisma.$disconnect();
});

describe('API & Echtzeit', () => {
  let cookie: string;
  let sessionId: string;
  let code: string;

  it('Gesundheitscheck und Konfiguration', async () => {
    expect((await request(base).get('/healthz')).body.ok).toBe(true);
    const cfg = await request(base).get('/api/config');
    expect(cfg.body).toMatchObject({ twitchEnabled: false, devLogin: true });
  });

  it('geschützte Endpunkte verlangen eine Anmeldung', async () => {
    expect((await request(base).get('/api/library')).status).toBe(401);
    expect((await request(base).post('/api/sessions').send({ caseId: 'der-perfekte-einbruch' })).status).toBe(401);
  });

  it('validiert Eingaben', async () => {
    const r = await request(base).post('/api/auth/dev/login').send({ login: 'x', role: 'streamer' });
    expect(r.status).toBe(400);
  });

  it('Streamer meldet sich an, sieht die Bibliothek und startet einen Fall', async () => {
    cookie = await login('streamer', 'test_streamer');
    const lib = await request(base).get('/api/library').set('Cookie', cookie);
    expect(lib.body.cases.length).toBe(5);
    expect(lib.body.cases.every((c: { playable: boolean }) => c.playable)).toBe(true);
    const assign = await request(base).post('/api/library/assign').set('Cookie', cookie).send({ difficulty: 'experte' });
    expect(assign.body.case.difficulty).toBe('experte');
    const created = await request(base).post('/api/sessions').set('Cookie', cookie).send({ caseId: 'der-perfekte-einbruch' });
    expect(created.status).toBe(201);
    sessionId = created.body.id;
    code = created.body.joinCode;
    const dup = await request(base).post('/api/sessions').set('Cookie', cookie).send({ caseId: 'der-letzte-zug' });
    expect(dup.status).toBe(409);
  });

  it('Bibliothek merkt sich gespielte Fälle und bevorzugt neue bei der Zuweisung', async () => {
    const lib = await request(base).get('/api/library').set('Cookie', cookie);
    const played = lib.body.cases.find((c: { id: string }) => c.id === 'der-perfekte-einbruch');
    expect(played.playedByMe).toBe(1);
    for (let i = 0; i < 5; i++) {
      const a = await request(base).post('/api/library/assign').set('Cookie', cookie).send({});
      expect(a.body.case.id).not.toBe('der-perfekte-einbruch');
    }
  });

  it('fremde Streamer erhalten keinen Zugriff auf die Steuerung', async () => {
    const other = await login('streamer', 'other_streamer');
    const s = connect({ mode: 'control', sessionId }, other);
    const fatal = await once<{ code: string }>(s, 'fatal');
    expect(fatal.code).toBe('not_found');
  });

  it('Zuschauer ohne Identität werden abgewiesen, Gäste können beitreten', async () => {
    const anon = connect({ mode: 'viewer', code });
    expect((await once<{ code: string }>(anon, 'fatal')).code).toBe('need_identity');
    const g = await request(base).post(`/api/play/${code}/guest`).send({ name: 'Watson' });
    expect(g.status).toBe(200);
    const guestCookie = (g.headers['set-cookie'] as unknown as string[])[0].split(';')[0];
    const guest = connect({ mode: 'viewer', code, guestName: 'Watson' }, guestCookie);
    const snap = await once<Record<string, unknown>>(guest, 'snapshot');
    expect(snap.joinCode).toBe(code);
  });

  it('kompletter Spielablauf mit Spoilerschutz, Punkten, Abstimmung und Chat', async () => {
    const control = connect({ mode: 'control', sessionId }, cookie);
    const ownerSnap = await once<Record<string, any>>(control, 'snapshot');
    expect(ownerSnap.secrets.culpritName).toBe('Jonas Wendt');

    const viewerCookie = await login('viewer', 'holmes');
    const v = connect({ mode: 'viewer', code }, viewerCookie);
    const [snap, me] = await Promise.all([once<Record<string, any>>(v, 'snapshot'), once<Record<string, any>>(v, 'me')]);
    expect(me.verified).toBe(true);
    // Spoilerschutz über das Netzwerk
    const raw = JSON.stringify(snap);
    expect(raw).not.toContain('Jonas Wendt – der Restaurator');
    expect(raw).not.toContain('"hotspots"');
    expect(raw).not.toContain('"secrets"');
    expect(snap.solution).toBeUndefined();

    // Vor dem Start keine Aktionen
    expect((await emit(v, 'act', 'mark', { evidence: 'ev_gehweg', item: 'scherben' })).code).toBe('not_started');
    expect((await emit(control, 'control', 'start')).ok).toBe(true);

    // Zuschauer dürfen nicht steuern
    v.emit('control', 'reveal', {}, () => {});
    const patch = once<Record<string, any>>(v, 'patch');
    const hit = await emit(v, 'act', 'mark', { evidence: 'ev_gehweg', item: 'scherben' });
    expect(hit.ok).toBe(true);
    const p = await patch;
    expect(p.status ?? 'active').not.toBe('revealed');
    await wait(400);
    const meAfter = await new Promise<Record<string, any>>((r) => {
      v.once('me', r);
      void emit(v, 'act', 'team', { team: 'spurensicherung' });
    });
    expect(meAfter.points).toBe(30);
    expect(meAfter.team).toBe('spurensicherung');

    // Ungültige Eingaben werden abgefangen
    expect((await emit(v, 'act', 'mark', { evidence: 123 })).ok).toBe(false);
    expect((await emit(v, 'act', 'unbekannt', {})).ok).toBe(false);

    // Abstimmung über Chat-Simulator und Web, doppelte Stimmen zählen einmal
    expect((await emit(control, 'control', 'startVote', { kind: 'interrogate', seconds: 30 })).ok).toBe(true);
    const sim = (user: string, text: string) => request(base).post(`/api/sessions/${sessionId}/simulate-chat`).set('Cookie', cookie).send({ user, text });
    expect((await sim('chatter1', '!a 5')).body.result).toBe('voted');
    await wait(1600);
    expect((await sim('chatter1', '!a 5')).body.result).toBe('voted'); // Stimme geändert/bestätigt – zählt einmal
    expect((await sim('chatter2', '5')).body.result).toBe('voted');
    expect((await sim('chatter3', 'einfach nur chat')).body.result).toBeNull();
    expect((await emit(v, 'act', 'vote', { option: 4 })).ok).toBe(true);
    const live = ctx.manager.all().find((s) => s.id === sessionId)!;
    expect(live.vote!.ballots.size).toBe(3);
    expect((await emit(control, 'control', 'closeVote')).ok).toBe(true);
    expect(live.state.interrogation?.character).toBe('wendt');

    // Bots werden ignoriert
    expect((await sim('Nightbot', '!a 1')).body.result).toBeNull();

    // Theorie + Upvote durch andere Person
    const t = await emit(v, 'act', 'theory', { suspect: 'wendt', text: 'Code 04 und die Scherben draußen sprechen gegen einen Einbruch.', evidence: ['ev_gehweg'] });
    expect(t.ok).toBe(true);
    await sim('chatter2', '!theorie Wendt hat den Code');
    expect(live.theories.length).toBe(2);
    const own = live.theories.find((x) => x.authorId === me.participantId)!;
    expect((await emit(v, 'act', 'upvote', { theory: own.id })).ok).toBe(false); // eigene Theorie

    // Finale: Anklage per Abstimmung, korrekte Wähler und Theorie-Autoren erhalten Punkte
    expect((await emit(control, 'control', 'finale')).ok).toBe(true);
    expect((await emit(control, 'control', 'startVote', { kind: 'accuse', seconds: 30 })).ok).toBe(true);
    const wendtIdx = live.vote!.options.findIndex((o) => o.ref === 'wendt');
    expect((await emit(v, 'act', 'vote', { option: wendtIdx })).ok).toBe(true);
    expect((await emit(control, 'control', 'closeVote')).ok).toBe(true);
    expect(live.state.status).toBe('solved');
    const pts = await prisma.pointEntry.findMany({ where: { participantId: me.participantId } });
    const reasons = pts.map((x) => x.reason).sort();
    expect(reasons).toEqual(expect.arrayContaining(['accuse', 'hotspot', 'theory', 'theory_correct', 'vote']));

    // Auflösung → Lösung erreicht die Zuschauer
    const solutionPatch = new Promise<Record<string, any>>((r) => v.on('patch', (x) => x.solution && r(x)));
    expect((await emit(control, 'control', 'reveal')).ok).toBe(true);
    const sp = await solutionPatch;
    expect(sp.solution.culprit).toBe('wendt');
  });

  it('Spielstand wird gespeichert und nach einem Neustart wiederhergestellt', async () => {
    const live = ctx.manager.all().find((s) => s.id === sessionId)!;
    await live.save();
    const fresh = new SessionManager({ changed: () => {}, personal: () => {}, say: () => {}, notifyStreamer: () => {} });
    const restored = await fresh.get(sessionId);
    expect(restored).not.toBeNull();
    expect(restored!.state.status).toBe('revealed');
    expect(Object.keys(restored!.state.insights)).toEqual(Object.keys(live.state.insights));
    expect(restored!.participants.size).toBe(live.participants.size);
    expect(restored!.theories.length).toBe(2);
    restored!.dispose();
  });

  it('Overlay-Link liefert nur die Overlay-Sicht', async () => {
    const st = await prisma.streamer.findUnique({ where: { login: 'test_streamer' } });
    const o = connect({ mode: 'overlay', overlayToken: st!.overlayToken });
    const view = await once<Record<string, any>>(o, 'overlay');
    expect(view.title).toBe('Der perfekte Einbruch');
    expect(view.solution.culpritName).toBe('Jonas Wendt'); // erst nach Auflösung
    const bad = connect({ mode: 'overlay', overlayToken: 'falsch' });
    expect((await once<{ code: string }>(bad, 'fatal')).code).toBe('forbidden');
  });

  it('Ergebnisse und Verlauf stehen nach Spielende bereit', async () => {
    const control = connect({ mode: 'control', sessionId }, cookie);
    await once(control, 'snapshot');
    expect((await emit(control, 'control', 'end')).ok).toBe(true);
    const res = await request(base).get(`/api/sessions/${sessionId}/results`).set('Cookie', cookie);
    expect(res.body.participants).toBeGreaterThanOrEqual(3);
    expect(res.body.accusations[0].correct).toBe(true);
    const hist = await request(base).get('/api/sessions').set('Cookie', cookie);
    expect(hist.body.sessions[0].solved).toBe(true);
  });
});
