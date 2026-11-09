import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { io, type Socket } from 'socket.io-client';
import type { DiscussionMessage, OverlayView, PersonalState, PublicCaseView, PublicVote, StreamerSecrets } from '../../../shared/views';

export type ConnStatus = 'connecting' | 'online' | 'reconnecting' | 'fatal';

export interface AckResult<T = unknown> {
  ok: boolean;
  message?: string;
  code?: string;
  data?: T;
}

export type ViewerState = PublicCaseView & { discussion: DiscussionMessage[] };
export type OwnerState = ViewerState & {
  secrets: StreamerSecrets;
  sessionSettings: Record<string, any>;
  participantList: { id: string; name: string; points: number; team: string | null; banned: boolean; source: string; verified: boolean }[];
  hintRequests: number;
  lastVote: PublicVote | null;
  overlayPreview: OverlayView;
};

export type Handshake = { mode: 'viewer'; code: string; guestName?: string } | { mode: 'control'; sessionId: string } | { mode: 'overlay'; overlayToken: string };

/**
 * Alternative Verbindung ohne Server (Browser-Vorschau). Ist sie gesetzt,
 * nutzt useLive sie statt Socket.IO – die Oberflächen bleiben identisch.
 */
export interface LocalHandlers {
  snapshot(s: unknown): void;
  patch(p: unknown): void;
  me(m: PersonalState): void;
  overlay(o: OverlayView | null): void;
  notice(n: { kind: string; text: string; at: number }): void;
  bot(b: { text: string; at: number }): void;
  fatal(e: { message: string; code: string }): void;
}
export interface LocalConnection {
  emit(event: string, action: string, payload: unknown): Promise<AckResult<any>>;
  close(): void;
}
export interface LocalTransport {
  connect(hs: Handshake, h: LocalHandlers): LocalConnection;
}
export const LocalTransportContext = createContext<LocalTransport | null>(null);

/**
 * Verbindung zur Live-Sitzung mit automatischer Wiederverbindung.
 * Der Server sendet beim Verbinden einen vollständigen Snapshot und danach
 * nur noch geänderte Felder (patch).
 */
export function useLive<S extends object>(handshake: Handshake | null) {
  const [state, setState] = useState<S | null>(null);
  const [me, setMe] = useState<PersonalState | null>(null);
  const [overlay, setOverlay] = useState<OverlayView | null | undefined>(undefined);
  const [status, setStatus] = useState<ConnStatus>('connecting');
  const [error, setError] = useState<{ message: string; code: string } | null>(null);
  const [notices, setNotices] = useState<{ kind: string; text: string; at: number }[]>([]);
  const [bot, setBot] = useState<{ text: string; at: number }[]>([]);
  const [chatStatus, setChatStatus] = useState<{ enabled: boolean; connected: boolean; status: string; lastError: string | null } | null>(null);
  const [clockOffset, setClockOffset] = useState(0);
  const sockRef = useRef<Socket | null>(null);
  const localRef = useRef<LocalConnection | null>(null);
  const local = useContext(LocalTransportContext);
  const key = handshake ? JSON.stringify(handshake) : null;

  useEffect(() => {
    if (!key) return;
    const hs = JSON.parse(key) as Handshake;
    if (local) {
      const conn = local.connect(hs, {
        snapshot: (s) => setState(s as S),
        patch: (p) => setState((prev) => (prev ? { ...prev, ...(p as object) } : prev)),
        me: setMe,
        overlay: setOverlay,
        notice: (n) => setNotices((l) => [...l.slice(-9), n]),
        bot: (b) => setBot((l) => [...l.slice(-49), b]),
        fatal: (e) => {
          setError(e);
          setStatus('fatal');
        },
      });
      localRef.current = conn;
      setStatus('online');
      setChatStatus({ enabled: false, connected: false, status: 'disabled', lastError: null });
      return () => {
        conn.close();
        localRef.current = null;
      };
    }
    const socket = io({ path: '/socket.io', auth: hs, transports: ['websocket', 'polling'], reconnectionDelayMax: 8000, withCredentials: true });
    sockRef.current = socket;
    setStatus('connecting');
    setError(null);
    socket.on('connect', () => setStatus('online'));
    socket.on('disconnect', (reason) => {
      if (reason === 'io server disconnect') return; // fatal kommt separat
      setStatus('reconnecting');
    });
    socket.io.on('reconnect_attempt', () => setStatus('reconnecting'));
    socket.on('connect_error', (e) => {
      setStatus('reconnecting');
      setError({ message: e.message, code: 'connect' });
    });
    socket.on('fatal', (e: { message: string; code: string }) => {
      setError(e);
      setStatus('fatal');
      socket.disconnect();
    });
    socket.on('snapshot', (s: S & { serverNow: number }) => {
      setClockOffset(s.serverNow - Date.now());
      setState(s);
    });
    socket.on('patch', (p: Partial<S> & { serverNow: number }) => {
      setClockOffset(p.serverNow - Date.now());
      setState((prev) => (prev ? { ...prev, ...p } : prev));
    });
    socket.on('me', (m: PersonalState) => setMe(m));
    socket.on('overlay', (o: OverlayView | null) => {
      if (o) setClockOffset(o.serverNow - Date.now());
      setOverlay(o);
    });
    socket.on('notice', (n: { kind: string; text: string; at: number }) => setNotices((l) => [...l.slice(-9), n]));
    socket.on('bot', (b: { text: string; at: number }) => setBot((l) => [...l.slice(-49), b]));
    socket.on('chatStatus', (c) => setChatStatus(c));
    return () => {
      socket.removeAllListeners();
      socket.disconnect();
      sockRef.current = null;
    };
  }, [key, local]);

  const emit = useCallback(<T,>(event: string, action: string, payload: unknown = {}): Promise<AckResult<T>> => {
    if (localRef.current) return localRef.current.emit(event, action, payload) as Promise<AckResult<T>>;
    return new Promise((resolve) => {
      const s = sockRef.current;
      if (!s || !s.connected) return resolve({ ok: false, message: 'Keine Verbindung – wird wiederhergestellt …', code: 'offline' });
      s.timeout(10_000).emit(event, action, payload, (err: Error | null, res: AckResult<T>) => {
        if (err) resolve({ ok: false, message: 'Zeitüberschreitung – bitte erneut versuchen.', code: 'timeout' });
        else resolve(res);
      });
    });
  }, []);

  const act = useCallback(<T,>(action: string, payload?: unknown) => emit<T>('act', action, payload), [emit]);
  const control = useCallback(<T,>(action: string, payload?: unknown) => emit<T>('control', action, payload), [emit]);
  const mod = useCallback(<T,>(action: string, payload?: unknown) => emit<T>('mod', action, payload), [emit]);

  return { state, me, overlay, status, error, notices, bot, chatStatus, clockOffset, act, control, mod, setNotices };
}

/** Laufende Spielzeit (pausenbewusst). */
export function useGameClock(elapsedMs: number, runningSince: number | null, clockOffset: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (runningSince === null) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [runningSince]);
  return runningSince === null ? elapsedMs : elapsedMs + Math.max(0, now + clockOffset - runningSince);
}

export function useCountdown(endsAt: number | undefined, clockOffset: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!endsAt) return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [endsAt]);
  return endsAt ? Math.max(0, Math.ceil((endsAt - (now + clockOffset)) / 1000)) : 0;
}
