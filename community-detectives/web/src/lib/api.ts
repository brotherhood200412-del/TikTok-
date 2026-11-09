export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
  }
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: init.method ?? (init.body ? 'POST' : 'GET'),
    credentials: 'same-origin',
    headers: init.body ? { 'Content-Type': 'application/json' } : undefined,
    body: init.body ? JSON.stringify(init.body) : undefined,
  });
  const data = (await res.json().catch(() => ({}))) as { error?: string; code?: string };
  if (!res.ok) throw new ApiError(data.error ?? `Fehler ${res.status}`, res.status, data.code);
  return data as T;
}

export interface AppConfig {
  twitchEnabled: boolean;
  devLogin: boolean;
  chatSimulator: boolean;
  publicUrl: string;
}

export interface MeResponse {
  auth: { kind: 'streamer' | 'viewer'; login: string | null; displayName: string | null; twitchUserId: string | null } | null;
  streamer?: {
    id: string;
    login: string;
    displayName: string;
    profileImage: string | null;
    plan: 'free' | 'creator' | 'premium';
    overlayUrl: string;
    twitchLinked: boolean;
    scopes: string[];
    chat: { enabled: boolean; connected: boolean; status: string; lastError: string | null };
    activeSessionId: string | null;
    moderators: string[];
    isAdmin: boolean;
  };
}
