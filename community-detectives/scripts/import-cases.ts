import { importCases } from '../server/game/importCases.js';
import { prisma } from '../server/db.js';

const results = await importCases();
for (const r of results) console.log(`${r.ok ? '✔ veröffentlicht' : '✘ NICHT veröffentlicht'}  ${r.id}  ${r.title}${r.errors.length ? '\n    ' + r.errors.join('\n    ') : ''}`);
await prisma.$disconnect();
process.exit(results.every((r) => r.ok) ? 0 : 1);
