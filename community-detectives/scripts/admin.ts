/**
 * Verwaltungs-CLI.
 *   npm run admin -- streamers
 *   npm run admin -- set-plan <login> <free|creator|premium>
 *   npm run admin -- reserve <caseId> <login>
 *   npm run admin -- unreserve <caseId> <login>
 *   npm run admin -- cleanup-sessions      (abgelaufene Anmeldungen löschen)
 */
import { prisma } from '../server/db.js';

const [cmd, a, b] = process.argv.slice(2);
try {
  switch (cmd) {
    case 'streamers': {
      const rows = await prisma.streamer.findMany({ orderBy: { createdAt: 'asc' }, include: { _count: { select: { sessions: true } } } });
      for (const s of rows) console.log(`${s.login.padEnd(26)} ${s.plan.padEnd(8)} Twitch:${s.twitchUserId ? 'ja ' : 'nein'} Sitzungen:${s._count.sessions}`);
      break;
    }
    case 'set-plan': {
      if (!a || !['free', 'creator', 'premium'].includes(b)) throw new Error('Aufruf: set-plan <login> <free|creator|premium>');
      await prisma.streamer.update({ where: { login: a.toLowerCase() }, data: { plan: b as 'free' } });
      console.log(`Plan von ${a} ist jetzt ${b}.`);
      break;
    }
    case 'reserve':
    case 'unreserve': {
      if (!a || !b) throw new Error(`Aufruf: ${cmd} <caseId> <login>`);
      const s = await prisma.streamer.findUniqueOrThrow({ where: { login: b.toLowerCase() } });
      if (cmd === 'reserve') await prisma.caseReservation.upsert({ where: { caseId_streamerId: { caseId: a, streamerId: s.id } }, create: { caseId: a, streamerId: s.id }, update: {} });
      else await prisma.caseReservation.deleteMany({ where: { caseId: a, streamerId: s.id } });
      console.log('Erledigt.');
      break;
    }
    case 'cleanup-sessions': {
      const r = await prisma.authSession.deleteMany({ where: { expiresAt: { lt: new Date() } } });
      console.log(`${r.count} abgelaufene Anmeldungen gelöscht.`);
      break;
    }
    default:
      console.log('Befehle: streamers | set-plan <login> <plan> | reserve <caseId> <login> | unreserve <caseId> <login> | cleanup-sessions');
  }
} catch (e) {
  console.error((e as Error).message);
  process.exitCode = 1;
} finally {
  await prisma.$disconnect();
}
