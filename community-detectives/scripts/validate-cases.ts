/** Prüft alle Fälle in content/cases (oder die übergebenen Dateien). */
import path from 'node:path';
import { loadAllCases, loadCaseFile } from '../server/game/caseLoader.js';

const files = process.argv.slice(2);
const results = files.length ? await Promise.all(files.map((f) => loadCaseFile(path.resolve(f)))) : await loadAllCases();
let failed = 0;
for (const r of results) {
  const name = path.basename(r.file);
  const s = r.report.stats;
  console.log(`\n${r.report.ok ? '✔' : '✘'} ${name}${r.def ? ` – ${r.def.title} (${r.def.difficulty})` : ''}`);
  if (r.def) console.log(`  ${s.suspects} Verdächtige · ${s.evidence} Beweise · ${s.insights} Erkenntnisse (${s.reachableInsights} erreichbar) · ${s.puzzles} Rätsel · ${s.statements} Aussagen/Vernehmungen · ${s.connections} Verbindungen · ${s.events} Ereignisse · ${s.redHerrings} falsche Fährten`);
  for (const e of r.report.errors) console.log(`  ✘ ${e}`);
  for (const w of r.report.warnings) console.log(`  ⚠ ${w}`);
  if (!r.report.ok) failed++;
}
console.log(`\n${results.length - failed}/${results.length} Fälle gültig.`);
process.exit(failed ? 1 : 0);
