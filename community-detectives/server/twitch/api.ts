/**
 * Twitch-Anbindung über die offiziellen Schnittstellen:
 *  - OAuth 2.0 Authorization Code Flow (id.twitch.tv)
 *  - Helix API (Benutzer, Chat-Nachrichten senden, EventSub-Abos)
 * Basis-URLs sind konfigurierbar (Tests nutzen einen lokalen Mock-Server).
 */
import { config } from '../config.js';
import { prisma } from '../db.js';
import { decrypt, encrypt } from '../security/crypto.js';

export interface TwitchTokenSet {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  scope?: string[];
  token_type: string;
}

export interface TwitchUser {
  id: string;
  login: string;
  display_name: string;
  profile_image_url?: string;
}

export class TwitchError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function authorizeUrl(state: string, scopes: string[], redirectUri: string, forceVerify = false) {
  const u = new URL('/oauth2/authorize', config.TWITCH_AUTH_BASE);
  u.searchParams.set('client_id', config.TWITCH_CLIENT_ID ?? '');
  u.searchParams.set('redirect_uri', redirectUri);
  u.searchParams.set('response_type', 'code');
  u.searchParams.set('scope', scopes.join(' '));
  u.searchParams.set('state', state);
  if (forceVerify) u.searchParams.set('force_verify', 'true');
  return u.toString();
}

async function tokenRequest(params: Record<string, string>): Promise<TwitchTokenSet> {
  const res = await fetch(new URL('/oauth2/token', config.TWITCH_AUTH_BASE), {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: config.TWITCH_CLIENT_ID ?? '',
      client_secret: config.TWITCH_CLIENT_SECRET ?? '',
      ...params,
    }),
  });
  if (!res.ok) throw new TwitchError(`Token-Anfrage fehlgeschlagen (${res.status})`, res.status);
  return (await res.json()) as TwitchTokenSet;
}

export const exchangeCode = (code: string, redirectUri: string) =>
  tokenRequest({ code, grant_type: 'authorization_code', redirect_uri: redirectUri });

export const refreshToken = (refresh: string) => tokenRequest({ grant_type: 'refresh_token', refresh_token: refresh });

export async function getUserByToken(accessToken: string): Promise<TwitchUser> {
  const res = await fetch(`${config.TWITCH_API_BASE}/users`, {
    headers: { Authorization: `Bearer ${accessToken}`, 'Client-Id': config.TWITCH_CLIENT_ID ?? '' },
  });
  if (!res.ok) throw new TwitchError(`Benutzerabfrage fehlgeschlagen (${res.status})`, res.status);
  const body = (await res.json()) as { data: TwitchUser[] };
  if (!body.data[0]) throw new TwitchError('Kein Benutzer im Token', 401);
  return body.data[0];
}

export async function revokeToken(token: string) {
  await fetch(new URL('/oauth2/revoke', config.TWITCH_AUTH_BASE), {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: config.TWITCH_CLIENT_ID ?? '', token }),
  }).catch(() => undefined);
}

export async function storeTokens(streamerId: string, t: TwitchTokenSet) {
  const data = {
    accessTokenEnc: encrypt(t.access_token),
    refreshTokenEnc: encrypt(t.refresh_token),
    scopes: t.scope ?? [],
    expiresAt: new Date(Date.now() + t.expires_in * 1000),
  };
  await prisma.twitchToken.upsert({ where: { streamerId }, create: { streamerId, ...data }, update: data });
}

/**
 * Helix-Client für einen Streamer. Erneuert das Access-Token automatisch
 * (vor Ablauf und bei 401) und speichert neue Tokens verschlüsselt.
 */
export class HelixClient {
  private access: string | null = null;
  private expiresAt = 0;
  private refreshing: Promise<void> | null = null;

  constructor(public readonly streamerId: string) {}

  private async load() {
    const t = await prisma.twitchToken.findUnique({ where: { streamerId: this.streamerId } });
    if (!t) throw new TwitchError('Twitch ist für diesen Account nicht verbunden.', 401);
    this.access = decrypt(t.accessTokenEnc);
    this.expiresAt = t.expiresAt.getTime();
    return t;
  }

  private async refresh() {
    if (this.refreshing) return this.refreshing;
    this.refreshing = (async () => {
      const t = await prisma.twitchToken.findUnique({ where: { streamerId: this.streamerId } });
      if (!t) throw new TwitchError('Twitch ist nicht verbunden.', 401);
      const fresh = await refreshToken(decrypt(t.refreshTokenEnc));
      await storeTokens(this.streamerId, fresh);
      this.access = fresh.access_token;
      this.expiresAt = Date.now() + fresh.expires_in * 1000;
    })().finally(() => {
      this.refreshing = null;
    });
    return this.refreshing;
  }

  async token(): Promise<string> {
    if (!this.access) await this.load();
    if (Date.now() > this.expiresAt - 60_000) await this.refresh();
    return this.access!;
  }

  async request<T>(method: string, path: string, body?: unknown, retry = true): Promise<T> {
    const token = await this.token();
    const res = await fetch(`${config.TWITCH_API_BASE}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        'Client-Id': config.TWITCH_CLIENT_ID ?? '',
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401 && retry) {
      await this.refresh();
      return this.request<T>(method, path, body, false);
    }
    if (res.status === 429) {
      const reset = Number(res.headers.get('ratelimit-reset') ?? 0) * 1000;
      throw new TwitchError(`Twitch-Ratenlimit erreicht (Reset ${new Date(reset).toISOString()})`, 429);
    }
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new TwitchError(`Helix ${method} ${path} → ${res.status} ${text.slice(0, 200)}`, res.status);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  /** Abonniert channel.chat.message für eine EventSub-WebSocket-Sitzung. */
  subscribeChat(sessionId: string, broadcasterId: string, userId: string) {
    return this.request<{ data: { id: string; status: string }[] }>('POST', '/eventsub/subscriptions', {
      type: 'channel.chat.message',
      version: '1',
      condition: { broadcaster_user_id: broadcasterId, user_id: userId },
      transport: { method: 'websocket', session_id: sessionId },
    });
  }

  sendChatMessage(broadcasterId: string, senderId: string, message: string) {
    return this.request<{ data: { message_id: string; is_sent: boolean; drop_reason?: { message: string } }[] }>('POST', '/chat/messages', {
      broadcaster_id: broadcasterId,
      sender_id: senderId,
      message: message.slice(0, 500),
    });
  }
}
