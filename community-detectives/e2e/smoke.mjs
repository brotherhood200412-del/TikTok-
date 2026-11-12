/**
 * End-to-End-Rauchtest mit Playwright gegen einen laufenden Server
 * (Standard: http://localhost:8787, gebaut mit `npm run build`).
 * Ablauf: Streamer-Login → Fall starten → Zuschauer tritt bei → Ermittlung
 * starten → Beweis markieren → Abstimmung → Overlay → Auflösung.
 */
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = await import('playwright').catch(() => require('playwright'));
import { mkdirSync } from 'node:fs';

const BASE = process.env.E2E_BASE ?? 'http://localhost:8787';
const SHOTS = process.env.E2E_SHOTS ?? 'e2e/screenshots';
mkdirSync(SHOTS, { recursive: true });
const log = (m) => console.log(`• ${m}`);
const fail = (m) => {
  console.error(`✘ ${m}`);
  process.exit(1);
};

const browser = await chromium.launch();
try {
  const streamer = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const sp = await streamer.newPage();
  sp.on('pageerror', (e) => fail(`JS-Fehler (Streamer): ${e.message}`));
  const login = `e2e_${Date.now().toString(36)}`;
  await sp.goto(BASE);
  await sp.getByPlaceholder('streamer_name').fill(login);
  await sp.getByRole('button', { name: 'Anmelden' }).click();
  await sp.waitForURL('**/dashboard');
  await sp.getByText('Fallbibliothek').waitFor();
  log('Streamer angemeldet, Bibliothek sichtbar');
  await sp.screenshot({ path: `${SHOTS}/01-dashboard.png` });

  const card = sp.locator('article', { hasText: 'Der perfekte Einbruch' });
  await card.getByRole('button', { name: /starten|spielen/ }).click();
  await sp.getByRole('button', { name: /Akte öffnen/ }).click();
  await sp.waitForURL('**/control/**');
  await sp.getByText('Kontrollzentrum').first().waitFor();
  const code = (await sp.locator('header b.font-mono').first().textContent()).trim();
  log(`Sitzung erstellt, Code ${code}`);

  // Zuschauer (mobil)
  const viewer = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const vp = await viewer.newPage();
  vp.on('pageerror', (e) => fail(`JS-Fehler (Zuschauer): ${e.message}`));
  await vp.goto(`${BASE}/play/${code}`);
  await vp.getByPlaceholder('Dein Ermittlername').fill('Sherlock');
  await vp.getByRole('button', { name: 'Beitreten' }).click();
  await vp.getByText('Der perfekte Einbruch').first().waitFor();
  log('Zuschauer beigetreten');
  await vp.screenshot({ path: `${SHOTS}/02-viewer-akte.png` });

  await sp.getByRole('button', { name: /Ermittlung starten/ }).click();
  await vp.getByText('Ermittlung läuft').waitFor();
  log('Ermittlung gestartet');

  // Beweis öffnen und Hotspot markieren
  await vp.locator('nav').getByRole('button', { name: 'Beweise' }).click();
  await vp.getByRole('button', { name: /Foto Gehweg/ }).click();
  await vp.getByRole('button', { name: 'Scherben auf dem Gehweg' }).first().click();
  await vp.getByRole('button', { name: /Als verdächtig markieren/ }).click();
  await vp.getByText(/Von innen eingeschlagen|Scherben liegen außen/).first().waitFor();
  log('Hotspot markiert → Erkenntnis aufgedeckt');
  await vp.screenshot({ path: `${SHOTS}/03-viewer-beweis.png` });
  await vp.keyboard.press('Escape');

  // Overlay
  const overlayUrl = await (async () => {
    const r = await sp.request.get(`${BASE}/api/me`);
    return (await r.json()).streamer.overlayUrl.replace(/^https?:\/\/[^/]+/, BASE);
  })();
  const ov = await (await browser.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
  ov.on('pageerror', (e) => fail(`JS-Fehler (Overlay): ${e.message}`));
  await ov.goto(overlayUrl);
  await ov.getByText('Der perfekte Einbruch').waitFor();
  log('Overlay verbunden');

  // Abstimmung über Vernehmung
  await sp.getByRole('button', { name: 'Starten', exact: true }).click();
  await vp.getByText('Abstimmung läuft').waitFor();
  await vp.getByRole('button', { name: /Jonas Wendt/ }).click();
  await sp.getByText('1 Stimmen').first().waitFor();
  log('Stimme gezählt');
  await ov.waitForTimeout(600);
  await ov.screenshot({ path: `${SHOTS}/04-overlay-vote.png`, omitBackground: true });
  await sp.getByRole('button', { name: 'Jetzt auswerten' }).click();
  await vp.getByText('Vernehmung läuft').first().waitFor();
  log('Abstimmungsergebnis angewendet → Vernehmung läuft');
  await sp.screenshot({ path: `${SHOTS}/05-control.png` });

  // Spoilerschutz: Zuschauer-HTML darf die Täterauflösung nicht enthalten
  const html = await vp.content();
  if (html.includes('stahl das Bild, das er selbst gerettet hatte')) fail('Lösung im Zuschauer-DOM gefunden!');
  log('Spoilerschutz geprüft');

  // Auflösung
  sp.on('dialog', (d) => d.accept());
  await sp.getByRole('button', { name: /Auflösung zeigen/ }).click();
  await vp.getByText('Abschlussbericht').waitFor();
  log('Auflösung beim Zuschauer sichtbar');
  await vp.screenshot({ path: `${SHOTS}/06-viewer-loesung.png`, fullPage: false });
  await ov.waitForTimeout(500);
  await ov.screenshot({ path: `${SHOTS}/07-overlay-reveal.png` });
  console.log('✔ E2E-Rauchtest erfolgreich');
} finally {
  await browser.close();
}
