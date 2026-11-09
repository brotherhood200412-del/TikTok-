import 'dotenv/config';
import { z } from 'zod';

const bool = (def: boolean) =>
  z
    .string()
    .optional()
    .transform((v) => (v === undefined || v === '' ? def : ['1', 'true', 'yes', 'on'].includes(v.toLowerCase())));

const schema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  PORT: z.coerce.number().int().default(8787),
  PUBLIC_URL: z.string().url().default('http://localhost:5173'),
  DATABASE_URL: z.string().min(1, 'DATABASE_URL fehlt'),
  SESSION_SECRET: z.string().min(16).optional(),
  TOKEN_ENCRYPTION_KEY: z.string().optional(),
  TWITCH_CLIENT_ID: z.string().optional(),
  TWITCH_CLIENT_SECRET: z.string().optional(),
  TWITCH_AUTH_BASE: z.string().url().default('https://id.twitch.tv'),
  TWITCH_API_BASE: z.string().url().default('https://api.twitch.tv/helix'),
  TWITCH_EVENTSUB_WS_URL: z.string().default('wss://eventsub.wss.twitch.tv/ws'),
  ALLOW_DEV_LOGIN: bool(false),
  ENABLE_CHAT_SIMULATOR: bool(false),
  ADMIN_LOGINS: z.string().default(''),
  DEFAULT_PLAN: z.enum(['free', 'creator', 'premium']).default('free'),
  BOT_IGNORE_LIST: z.string().default('nightbot,streamelements,streamlabs,moobot,fossabot,wizebot,soundalerts,sery_bot,botrixoficial,kofistreambot'),
  TRUST_PROXY: bool(false),
});

// Auf Render ist die öffentliche Adresse automatisch bekannt.
const parsed = schema.safeParse({ ...process.env, PUBLIC_URL: process.env.PUBLIC_URL || process.env.RENDER_EXTERNAL_URL || undefined });
if (!parsed.success) {
  console.error('Ungültige Konfiguration:\n' + parsed.error.issues.map((i) => ` - ${i.path.join('.')}: ${i.message}`).join('\n'));
  process.exit(1);
}
const env = parsed.data;
const isProd = env.NODE_ENV === 'production';

if (isProd && (!env.SESSION_SECRET || !env.TOKEN_ENCRYPTION_KEY)) {
  console.error('In Produktion müssen SESSION_SECRET und TOKEN_ENCRYPTION_KEY gesetzt sein.');
  process.exit(1);
}

export const config = {
  ...env,
  isProd,
  twitchEnabled: !!(env.TWITCH_CLIENT_ID && env.TWITCH_CLIENT_SECRET),
  /** Lokaler Login ohne Twitch – nur außerhalb der Produktion oder explizit erlaubt. */
  devLogin: env.ALLOW_DEV_LOGIN || (!isProd && !(env.TWITCH_CLIENT_ID && env.TWITCH_CLIENT_SECRET)),
  chatSimulator: env.ENABLE_CHAT_SIMULATOR || !isProd,
  sessionSecret: env.SESSION_SECRET ?? 'dev-only-session-secret-change-me',
  encryptionKey: env.TOKEN_ENCRYPTION_KEY ?? 'dev-only-encryption-key-change-me',
  adminLogins: env.ADMIN_LOGINS.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean),
  botIgnore: new Set(env.BOT_IGNORE_LIST.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean)),
  twitchScopes: ['user:read:chat', 'user:write:chat'],
};
export type AppConfig = typeof config;
