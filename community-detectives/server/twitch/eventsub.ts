/**
 * EventSub-WebSocket-Client (offizielle Twitch-Schnittstelle für Chat-Ereignisse).
 *
 * Unterstützt:
 *  - session_welcome → Abonnement anlegen (innerhalb der 10-Sekunden-Frist)
 *  - session_keepalive → Watchdog; bleibt er aus, wird neu verbunden
 *  - session_reconnect → nahtloser Wechsel auf die neue URL
 *  - revocation → Abo widerrufen (z. B. Token entzogen) → Statusmeldung
 *  - Verbindungsabbrüche → exponentielles Backoff
 *  - Duplikat-Erkennung über message_id
 */
import WebSocket from 'ws';
import { EventEmitter } from 'node:events';

export interface ChatMessageEvent {
  messageId: string;
  broadcasterId: string;
  userId: string;
  userLogin: string;
  userName: string;
  text: string;
  badges: string[];
  isBroadcaster: boolean;
  isModerator: boolean;
}

export type EventSubStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error' | 'revoked' | 'stopped';

interface Envelope {
  metadata: { message_id: string; message_type: string; message_timestamp: string; subscription_type?: string };
  payload: Record<string, any>;
}

export interface EventSubOptions {
  url: string;
  /** Wird nach session_welcome aufgerufen, um Abos anzulegen. */
  subscribe: (sessionId: string) => Promise<void>;
  log?: (msg: string) => void;
  maxBackoffMs?: number;
  /** Toleranz zusätzlich zum Keepalive-Intervall (Standard 5 s). */
  keepaliveGraceMs?: number;
  /** Basisverzögerung für Wiederverbindungen (Standard 1 s). */
  baseBackoffMs?: number;
}

export class EventSubClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private keepaliveTimer: NodeJS.Timeout | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private keepaliveMs = 10_000;
  private attempts = 0;
  private seen: string[] = [];
  private seenSet = new Set<string>();
  private stopped = false;
  status: EventSubStatus = 'idle';
  lastError: string | null = null;
  sessionId: string | null = null;

  constructor(private readonly opts: EventSubOptions) {
    super();
  }

  start() {
    this.stopped = false;
    this.connect(this.opts.url, false);
  }

  stop() {
    this.stopped = true;
    this.clearTimers();
    this.ws?.removeAllListeners();
    this.ws?.close();
    this.ws = null;
    this.setStatus('stopped');
  }

  private setStatus(s: EventSubStatus, err?: string) {
    this.status = s;
    if (err !== undefined) this.lastError = err;
    this.emit('status', s, this.lastError);
  }

  private clearTimers() {
    if (this.keepaliveTimer) clearTimeout(this.keepaliveTimer);
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.keepaliveTimer = this.reconnectTimer = null;
  }

  private armKeepalive() {
    if (this.keepaliveTimer) clearTimeout(this.keepaliveTimer);
    this.keepaliveTimer = setTimeout(() => {
      this.opts.log?.('EventSub: Keepalive ausgeblieben – verbinde neu.');
      this.scheduleReconnect('Keepalive-Timeout');
    }, this.keepaliveMs + (this.opts.keepaliveGraceMs ?? 5_000));
  }

  private scheduleReconnect(reason: string) {
    if (this.stopped) return;
    this.clearTimers();
    this.ws?.removeAllListeners();
    try {
      this.ws?.terminate();
    } catch {
      /* ignore */
    }
    this.ws = null;
    this.attempts += 1;
    const base = this.opts.baseBackoffMs ?? 1000;
    const delay = Math.min(this.opts.maxBackoffMs ?? 60_000, base * 2 ** Math.min(this.attempts - 1, 6)) + Math.floor(Math.random() * (base / 2));
    this.setStatus('reconnecting', reason);
    this.reconnectTimer = setTimeout(() => this.connect(this.opts.url, false), delay);
  }

  private connect(url: string, isMigration: boolean) {
    if (this.stopped) return;
    if (!isMigration) this.setStatus('connecting');
    const ws = new WebSocket(url);
    const previous = isMigration ? this.ws : null;
    if (!isMigration) this.ws = ws;

    ws.on('message', (data) => {
      let msg: Envelope;
      try {
        msg = JSON.parse(data.toString());
      } catch {
        return;
      }
      this.handle(ws, msg, previous);
    });
    ws.on('close', (code) => {
      if (this.ws !== ws) return; // alte Verbindung nach Migration
      if (code === 4003 || code === 4004) this.opts.log?.(`EventSub geschlossen (${code}).`);
      this.scheduleReconnect(`Verbindung geschlossen (${code})`);
    });
    ws.on('error', (err) => {
      this.opts.log?.(`EventSub-Fehler: ${err.message}`);
      this.lastError = err.message;
    });
  }

  private handle(ws: WebSocket, msg: Envelope, previous: WebSocket | null) {
    const type = msg.metadata?.message_type;
    if (!type) return;
    if (this.seenSet.has(msg.metadata.message_id)) return;
    this.seen.push(msg.metadata.message_id);
    this.seenSet.add(msg.metadata.message_id);
    if (this.seen.length > 2000) this.seenSet.delete(this.seen.shift()!);

    switch (type) {
      case 'session_welcome': {
        const s = msg.payload.session;
        this.keepaliveMs = (s.keepalive_timeout_seconds ?? 10) * 1000;
        this.sessionId = s.id;
        if (previous) {
          // Migration: Abos bleiben bestehen, alte Verbindung schließen.
          this.ws = ws;
          previous.removeAllListeners();
          previous.close();
          this.attempts = 0;
          this.setStatus('connected', '');
          this.armKeepalive();
          return;
        }
        this.armKeepalive();
        this.opts
          .subscribe(s.id)
          .then(() => {
            this.attempts = 0;
            this.setStatus('connected', '');
          })
          .catch((e: Error) => {
            this.opts.log?.(`EventSub-Abo fehlgeschlagen: ${e.message}`);
            this.setStatus('error', e.message);
            if ((e as { status?: number }).status === 401 || (e as { status?: number }).status === 403) {
              // Ohne gültige Berechtigung nicht in einer Schleife neu verbinden.
              this.stopped = true;
              this.clearTimers();
              ws.close();
            } else this.scheduleReconnect(e.message);
          });
        return;
      }
      case 'session_keepalive':
        this.armKeepalive();
        return;
      case 'session_reconnect': {
        const url = msg.payload.session?.reconnect_url;
        if (url) this.connect(url, true);
        return;
      }
      case 'revocation':
        this.setStatus('revoked', `Abo widerrufen: ${msg.payload.subscription?.status ?? 'unbekannt'}`);
        this.emit('revoked', msg.payload.subscription);
        return;
      case 'notification': {
        this.armKeepalive();
        if (msg.metadata.subscription_type === 'channel.chat.message') {
          const e = msg.payload.event;
          const badges: string[] = (e.badges ?? []).map((b: { set_id: string }) => b.set_id);
          const chat: ChatMessageEvent = {
            messageId: e.message_id,
            broadcasterId: e.broadcaster_user_id,
            userId: e.chatter_user_id,
            userLogin: e.chatter_user_login,
            userName: e.chatter_user_name,
            text: e.message?.text ?? '',
            badges,
            isBroadcaster: badges.includes('broadcaster'),
            isModerator: badges.includes('moderator'),
          };
          this.emit('chat', chat);
        }
        return;
      }
    }
  }
}
