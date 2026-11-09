import { config } from './config.js';
import { prisma } from './db.js';
import { createApp } from './app.js';

const { server, manager, chat } = await createApp();
const restored = await manager.restoreAll();
manager.startTicker();
for (const s of manager.all()) if (s.state.status !== 'ended') void chat.ensure(s.streamerId);

server.listen(config.PORT, () => {
  console.log(`COMMUNITY DETECTIVES Server läuft auf Port ${config.PORT}`);
  console.log(`  Öffentliche URL: ${config.PUBLIC_URL}`);
  console.log(`  Twitch: ${config.twitchEnabled ? 'konfiguriert' : 'nicht konfiguriert (lokaler Entwicklungs-Login aktiv)'}`);
  console.log(`  Wiederhergestellte Sitzungen: ${restored}`);
});

let stopping = false;
async function shutdown(signal: string) {
  if (stopping) return;
  stopping = true;
  console.log(`${signal} empfangen – speichere Spielstände …`);
  chat.stopAll();
  await manager.shutdown();
  await prisma.$disconnect();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
}
process.on('SIGINT', () => void shutdown('SIGINT'));
process.on('SIGTERM', () => void shutdown('SIGTERM'));
