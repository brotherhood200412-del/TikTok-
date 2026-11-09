import cookieParser from 'cookie-parser';
import express from 'express';
import helmet from 'helmet';
import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { config } from './config.js';
import { prisma } from './db.js';
import { SessionManager } from './game/manager.js';
import { apiRouter } from './http/routes.js';
import { Realtime } from './realtime/realtime.js';
import { ChatBridge } from './twitch/chatBridge.js';

export async function createApp(opts: { serveStatic?: boolean } = {}) {
  const app = express();
  if (config.TRUST_PROXY) app.set('trust proxy', 1);
  app.disable('x-powered-by');
  app.use(
    helmet({
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          scriptSrc: ["'self'"],
          styleSrc: ["'self'", "'unsafe-inline'"],
          imgSrc: ["'self'", 'data:', 'https://static-cdn.jtvnw.net'],
          connectSrc: ["'self'", 'ws:', 'wss:'],
          fontSrc: ["'self'", 'data:'],
          frameAncestors: ["'self'"],
        },
      },
      crossOriginEmbedderPolicy: false,
    }),
  );
  app.use(cookieParser());

  const server = createServer(app);
  // Hooks werden nach Erzeugung der Realtime-Schicht verdrahtet.
  const manager = new SessionManager({ changed: () => {}, personal: () => {}, say: () => {}, notifyStreamer: () => {} });
  const chat = new ChatBridge(manager);
  const realtime = new Realtime(server, manager, chat);
  manager.setHooks({
    changed: (s) => realtime.changed(s),
    personal: (s, p) => realtime.personal(s, p),
    say: (s, t) => chat.say(s, t),
    notifyStreamer: (s, k, t) => realtime.notifyStreamer(s, k, t),
  });

  app.get('/healthz', async (_req, res) => {
    try {
      await prisma.$queryRaw`SELECT 1`;
      res.json({ ok: true, sessions: manager.all().length });
    } catch {
      res.status(503).json({ ok: false });
    }
  });
  app.use('/api', apiRouter(manager, chat));

  const dist = path.resolve(import.meta.dirname, '../dist/web');
  if (opts.serveStatic !== false && existsSync(dist)) {
    app.use(express.static(dist, { index: false, maxAge: '1h' }));
    app.get(/^\/(?!api|socket\.io).*/, (_req, res) => res.sendFile(path.join(dist, 'index.html')));
  }

  return { app, server, manager, chat, realtime };
}
