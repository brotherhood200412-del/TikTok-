/**
 * Anmeldung: Twitch OAuth (Streamer & verifizierte Zuschauer), lokaler
 * Entwicklungs-Login, Gastzugang. Sitzungen sind zufällige Tokens in einem
 * httpOnly-Cookie; in der Datenbank liegt nur der SHA-256-Hash.
 */
import type { Request, Response } from 'express';
import { createHmac } from 'node:crypto';
import { config } from '../config.js';
import { prisma } from '../db.js';
import { randomToken, safeEqual, sha256 } from '../security/crypto.js';

export const SESSION_COOKIE = 'cd_session';
export const GUEST_COOKIE = 'cd_guest';
export const STATE_COOKIE = 'cd_oauth';
const SESSION_DAYS = 30;

export interface AuthInfo {
  kind: 'streamer' | 'viewer';
  streamerId: string | null;
  twitchUserId: string | null;
  login: string | null;
  displayName: string | null;
}

export const cookieOpts = (maxAgeMs: number) => ({
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: config.isProd,
  path: '/',
  maxAge: maxAgeMs,
});

export async function createAuthSession(res: Response, data: Omit<AuthInfo, 'kind'> & { kind: AuthInfo['kind'] }) {
  const token = randomToken();
  await prisma.authSession.create({
    data: { id: sha256(token), ...data, expiresAt: new Date(Date.now() + SESSION_DAYS * 86400_000) },
  });
  res.cookie(SESSION_COOKIE, token, cookieOpts(SESSION_DAYS * 86400_000));
}

export async function authFromToken(token: string | undefined): Promise<AuthInfo | null> {
  if (!token || token.length > 200) return null;
  const row = await prisma.authSession.findUnique({ where: { id: sha256(token) } });
  if (!row || row.expiresAt < new Date()) return null;
  return { kind: row.kind as AuthInfo['kind'], streamerId: row.streamerId, twitchUserId: row.twitchUserId, login: row.login, displayName: row.displayName };
}

export async function destroyAuthSession(req: Request, res: Response) {
  const token = req.cookies?.[SESSION_COOKIE];
  if (token) await prisma.authSession.deleteMany({ where: { id: sha256(token) } });
  res.clearCookie(SESSION_COOKIE, { path: '/' });
}

export function parseCookies(header: string | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!header) return out;
  for (const part of header.split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    const v = part.slice(i + 1).trim();
    try {
      out[k] = decodeURIComponent(v);
    } catch {
      out[k] = v;
    }
  }
  return out;
}

/* ------------------------------ Gastschlüssel ------------------------------ */

/** Signierter Gastschlüssel, damit Gäste nach einem Reload dieselbe Identität behalten. */
export function signGuest(key: string) {
  return `${key}.${createHmac('sha256', config.sessionSecret).update(key).digest('base64url').slice(0, 22)}`;
}
export function verifyGuest(value: string | undefined): string | null {
  if (!value) return null;
  const [key, sig] = value.split('.');
  if (!key || !sig) return null;
  const expected = signGuest(key).split('.')[1];
  return safeEqual(sig, expected) ? key : null;
}

/* ------------------------------ OAuth-State ------------------------------ */

export function makeOAuthState(payload: { role: 'streamer' | 'viewer'; returnTo: string }) {
  const nonce = randomToken(16);
  const body = Buffer.from(JSON.stringify({ ...payload, nonce, t: Date.now() })).toString('base64url');
  const sig = createHmac('sha256', config.sessionSecret).update(body).digest('base64url');
  return { state: `${body}.${sig}`, nonce };
}

export function readOAuthState(state: string, nonceCookie: string | undefined): { role: 'streamer' | 'viewer'; returnTo: string } | null {
  const [body, sig] = state.split('.');
  if (!body || !sig) return null;
  const expected = createHmac('sha256', config.sessionSecret).update(body).digest('base64url');
  if (!safeEqual(sig, expected)) return null;
  const data = JSON.parse(Buffer.from(body, 'base64url').toString()) as { role: 'streamer' | 'viewer'; returnTo: string; nonce: string; t: number };
  if (!nonceCookie || !safeEqual(data.nonce, nonceCookie)) return null;
  if (Date.now() - data.t > 10 * 60_000) return null;
  return { role: data.role, returnTo: safeReturn(data.returnTo) };
}

/** Nur relative Pfade innerhalb der App zulassen (kein Open Redirect). */
export function safeReturn(p: string | undefined) {
  if (!p || !p.startsWith('/') || p.startsWith('//') || p.includes('\\')) return '/';
  return p.slice(0, 200);
}

export async function upsertStreamer(user: { id?: string | null; login: string; displayName: string; profileImage?: string | null }) {
  const login = user.login.toLowerCase();
  const existing = user.id
    ? await prisma.streamer.findFirst({ where: { OR: [{ twitchUserId: user.id }, { login }] } })
    : await prisma.streamer.findUnique({ where: { login } });
  if (existing) {
    return prisma.streamer.update({
      where: { id: existing.id },
      data: { login, displayName: user.displayName, profileImage: user.profileImage ?? existing.profileImage, twitchUserId: user.id ?? existing.twitchUserId },
    });
  }
  return prisma.streamer.create({
    data: {
      login,
      displayName: user.displayName,
      twitchUserId: user.id ?? null,
      profileImage: user.profileImage ?? null,
      overlayToken: randomToken(24),
      plan: config.DEFAULT_PLAN,
    },
  });
}

export const isAdmin = (login: string | null | undefined) => !!login && config.adminLogins.includes(login.toLowerCase());
