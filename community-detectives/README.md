# COMMUNITY DETECTIVES

Interaktive Krimi- und Ermittlungsplattform für Twitch-Streamer und ihre Communities.
Der Streamer ist die Spielleitung, der Chat ist das Ermittlerteam, der Fall ist die Geschichte.

- **Streamer-Kontrollzentrum**: Fall wählen oder zuweisen lassen, Phasen steuern, Vernehmungen führen, Abstimmungen starten, Hinweise und Ereignisse auslösen, Finale und Auflösung. Die Lösung ist nur hier sichtbar (mit „Streamer-Modus“, der Geheimes auf dem Bildschirm unkenntlich macht).
- **Zuschauerseite** (mobil optimiert): Akte lesen, Beweise untersuchen und verdächtige Details markieren, Verbindungen auf dem Ermittlungsboard ziehen, Rätsel lösen, abstimmen, Theorien einreichen und unterstützen, Teams, Rangliste, Diskussion.
- **OBS-Overlay** (Browserquelle, transparent): Falltitel, Phase, Aufgabe, Timer, Abstimmungen mit Countdown, Fokus (Beweis, Verdächtige/r im Verhör, Rätsel), Entdeckungen, Rangliste, Beitrittscode und die finale Auflösung.
- **Twitch-Chat**: echte Anbindung über **EventSub (WebSocket)** und die **Helix-Chat-API**, mit OAuth, verschlüsselten Tokens, automatischem Token-Refresh und Wiederverbindung.
- **Fallbibliothek**: 5 vollständige, logisch geprüfte Fälle in allen vier Schwierigkeitsgraden. Ein **Fallvalidator** simuliert ein „perfektes Ermittlerteam“ und prüft jeden Fall auf Lösbarkeit, Fairness und Sackgassen.

---

## Inhalt

1. [Schnellstart (lokal, ohne Twitch)](#schnellstart-lokal-ohne-twitch)
2. [Twitch verbinden](#twitch-verbinden)
3. [Ablauf einer Ermittlung im Stream](#ablauf-einer-ermittlung-im-stream)
4. [Chatbefehle](#chatbefehle)
5. [Die Fälle](#die-fälle)
6. [Produktion & Betrieb](#produktion--betrieb)
7. [Tests & Qualitätssicherung](#tests--qualitätssicherung)
8. [Projektstruktur](#projektstruktur)
9. [Weitere Dokumentation](#weitere-dokumentation)

---

## Schnellstart (lokal, ohne Twitch)

Voraussetzungen: **Node.js ≥ 20.19**, **PostgreSQL 14+** (oder Docker).

```bash
cd community-detectives
npm install
cp .env.example .env            # DATABASE_URL anpassen, falls nötig

# Datenbank (alternativ eine vorhandene PostgreSQL-Instanz verwenden)
docker compose up -d

npm run setup                   # Prisma-Client erzeugen, Migrationen, Fälle validieren & importieren
npm run dev                     # Server (8787) + Weboberfläche (5173)
```

Dann <http://localhost:5173> öffnen:

1. **Als Streamer**: Im Feld „Lokaler Entwicklungs-Login“ einen Namen eingeben (z. B. `mein_kanal`). Lokale Streamer erhalten automatisch den Premium-Plan, damit alle Fälle testbar sind.
2. Im Dashboard einen Fall starten → Kontrollzentrum öffnet sich.
3. **Als Zuschauer**: In einem zweiten Browser (oder privaten Fenster) `http://localhost:5173/play/<CODE>` öffnen und als Gast oder als „verifizierter Zuschauer“ (Entwicklungs-Login) beitreten.
4. **Overlay**: Den Overlay-Link aus dem Dashboard („Twitch & OBS“) öffnen.
5. **Chat testen ohne Twitch**: Im Kontrollzentrum gibt es den **Chat-Simulator**. Er nutzt exakt denselben Verarbeitungsweg wie echte EventSub-Nachrichten.

> Der Entwicklungs-Login und der Chat-Simulator sind in Produktion automatisch deaktiviert (siehe `ALLOW_DEV_LOGIN`, `ENABLE_CHAT_SIMULATOR`).

## Twitch verbinden

1. Unter <https://dev.twitch.tv/console/apps> eine Anwendung anlegen.
   - **OAuth Redirect URL**: `<PUBLIC_URL>/api/auth/twitch/callback`
     (lokal: `http://localhost:5173/api/auth/twitch/callback`)
   - Kategorie: z. B. „Chat Bot“ oder „Game Integration“.
2. `TWITCH_CLIENT_ID` und `TWITCH_CLIENT_SECRET` in `.env` eintragen, Server neu starten.
3. Auf der Startseite „Mit Twitch anmelden“. Angefragte Berechtigungen:
   - `user:read:chat` – Chatnachrichten über EventSub lesen
   - `user:write:chat` – Antworten im Chat senden (vom Streamer-Konto)
4. Sobald eine Ermittlung läuft, verbindet sich der Server per EventSub-WebSocket mit Twitch und abonniert `channel.chat.message`. Der Status steht im Kontrollzentrum oben rechts.

Zuschauer können sich optional mit Twitch anmelden (ohne zusätzliche Rechte). Dann werden Punkte aus Chat und Webseite zusammengeführt, und Abstimmungen lassen sich auf verifizierte Konten beschränken.

Details, Fehlerbilder und Sicherheitshinweise: [`docs/TWITCH.md`](docs/TWITCH.md).

> **Hinweis zum Teststand:** Die Twitch-Integration ist vollständig implementiert und wird in `tests/twitch.test.ts` gegen einen lokalen Twitch-Mock getestet, der das offizielle Nachrichtenformat nachbildet (OAuth, Helix, EventSub inkl. `session_reconnect` und Verbindungsabbruch). Ein Test gegen das echte Twitch war in der Entwicklungsumgebung mangels Zugangsdaten nicht möglich.

## Ablauf einer Ermittlung im Stream

| Schritt | Streamer (Kontrollzentrum) | Community |
|---|---|---|
| Vorbereitung | Fall wählen oder **„Fall zuweisen lassen“**, Einstellungen (Gäste, zeitgesteuerte Ereignisse, Abstimmungsdauer) | tritt über Link/Code oder `!ermitteln` bei, liest die Akte |
| Ermittlung | „Ermittlung starten“, Phasen wechseln, Aufgabe setzen, Beweise/Rätsel in den **Fokus** (Overlay) | untersucht Beweise, markiert Details, zieht Verbindungen, löst Rätsel |
| Vernehmungen | Person vernehmen, Frage stellen **oder Community wählen lassen** | stimmt über Personen und Fragen ab; Antworten hängen vom Ermittlungsstand ab |
| Dramaturgie | Ereignisse kommen automatisch (Zeit/Bedingung) oder per Knopfdruck; Hinweise freigeben | `!hinweis` sammelt Hinweis-Anfragen |
| Finale | „Finale starten“ → **Anklage-Abstimmung**, optional Beweisfrage | stimmt ab, Theorien mit dem richtigen Täter erhalten Bonuspunkte |
| Auflösung | „Auflösung zeigen“ | sieht die Beweiskette – inklusive der Hinweise, die „die ganze Zeit da“ waren |

Falsche Anklagen beenden das Spiel nicht: Die Ermittlung geht weiter, und viele Fälle reagieren mit einem neuen Ereignis.

**Punkte** gibt es für gesicherte Details (30), bestätigte Verbindungen (40), gelöste Rätsel (60, minus 10 je genutztem Hinweis, mind. 20), Teilnahme an Abstimmungen (2), Theorien (5), Unterstützung durch andere (3 je Stimme, max. 30), korrekte Anklage (20) und richtige Theorie (50). Jede Punktevergabe ist in der Datenbank eindeutig (Teilnehmende × Grund × Bezug) – doppeltes Farmen ist ausgeschlossen.

## Chatbefehle

| Befehl | Wirkung |
|---|---|
| `!ermitteln` | dem Ermittlerteam beitreten |
| `!a <Nr>` / `!abstimmen <Nr>` / bloße Zahl | in laufender Abstimmung abstimmen (bloße Zahl abschaltbar) |
| `!verdächtige` | Liste der Verdächtigen (Antwort mit Cooldown) |
| `!beweis` / `!beweis <Nr>` | Übersicht bzw. Kurzinfo zu einem Beweis |
| `!theorie <Name> <Begründung>` | Theorie einreichen |
| `!lösung <Antwort>` (auch `!code`) | Antwort für das Rätsel im Fokus |
| `!hinweis` | um einen Hinweis bitten (Schwelle einstellbar, die Spielleitung entscheidet) |
| `!team <Spurensicherung\|Analyse\|Verhör\|Archiv>` | Team wählen |
| `!punkte` | eigene Punkte und Platz |
| `!fall`, `!hilfe` | Fallinfo mit Link bzw. Befehlsübersicht |

Schutzmechanismen: Ratenbegrenzung pro Person, Ignorierliste für Bots (`BOT_IGNORE_LIST`), Antwort-Cooldowns, gedrosselte Bot-Ausgabe (max. 1 Nachricht / 2 s, Stau wird verworfen statt den Chat zu fluten), gebündelte Begrüßungen.

## Die Fälle

| Fall | Genre | Schwierigkeit | Plan | Umfang |
|---|---|---|---|---|
| Der perfekte Einbruch | Kunstdiebstahl | Einsteiger | Free | 5 Verdächtige · 17 Beweise · 3 Rätsel |
| Der letzte Zug um 23:17 | Mord | Fortgeschritten | Free | 5 Verdächtige · 20 Beweise · 4 Rätsel |
| Die verschwundene Identität | Vermisstenfall / Identitätsbetrug | Fortgeschritten | Creator | 6 Verdächtige · 18 Beweise · 5 Rätsel |
| Das Geheimnis der Villa Falkenstein | Mysteriöser Todesfall | Experte | Creator | 6 Verdächtige · 23 Beweise · 5 Rätsel |
| Akte 1987 – Der ungelöste Fall | Cold Case | Meisterdetektiv | Premium | 7 Verdächtige · 22 Beweise · 6 Rätsel |

Jeder Fall hat eine feste Wahrheit, eine Lösungskette, falsche Fährten mit fairer Auflösung, zustandsabhängige Vernehmungen, Ereignisse und eine rekonstruierbare Zeitlinie. Neue Fälle sind reine YAML-Dateien – **keine Programmänderung nötig**: [`docs/FAELLE.md`](docs/FAELLE.md).

```bash
npm run cases:validate          # alle Fälle prüfen (Fehler + Hinweise)
npm run cases:import            # gültige Fälle in die Datenbank übernehmen
```

## Produktion & Betrieb

```bash
npm ci
npm run build                   # Typprüfung + Weboberfläche nach dist/web
npx prisma migrate deploy
npm run cases:import
NODE_ENV=production PORT=8787 PUBLIC_URL=https://detectives.example.com npm start
```

- Der Node-Server liefert in Produktion auch die gebaute Weboberfläche aus (eine Domain, ein Prozess).
- **Pflicht** in Produktion: `SESSION_SECRET`, `TOKEN_ENCRYPTION_KEY` (lange Zufallswerte). Ohne sie startet der Server nicht.
- Hinter einem Reverse Proxy (TLS) `TRUST_PROXY=true` setzen und WebSockets für `/socket.io` durchreichen.
- Gesundheitscheck: `GET /healthz`.
- Beim Beenden (SIGTERM/SIGINT) werden alle Spielstände gespeichert; beim Start werden laufende Ermittlungen inkl. offener Abstimmungen wiederhergestellt. Die Ausfallzeit zählt nicht als Spielzeit.
- Verwaltung: `npm run admin -- streamers | set-plan <login> <plan> | reserve <caseId> <login> | cleanup-sessions`. Die Fallverwaltung im Browser (`/admin`) steht Logins aus `ADMIN_LOGINS` offen.

Monetarisierung ist vorbereitet (Pläne `free` / `creator` / `premium` am Streamer, `tier` am Fall, Exklusiv-Reservierungen für Events), aber es ist **kein Zahlungsanbieter** angebunden. Zuschauer zahlen nie – es gibt keine Pay-to-Win-Mechanik.

## Tests & Qualitätssicherung

```bash
npm test                        # 68 Tests: Engine, Validator, Spoilerschutz, Chat, API, Sockets, Twitch-Mock
npm run typecheck
npm run build && npm start &    # dann:
npm run test:e2e                # Playwright-Rauchtest (Streamer, Zuschauer, Overlay, Abstimmung, Auflösung)
```

Die Integrationstests verwenden eine eigene Datenbank (`community_detectives_test`, überschreibbar mit `TEST_DATABASE_URL`), die vor jedem Lauf migriert und geleert wird.

## Projektstruktur

```
community-detectives/
├── content/cases/        Fälle (YAML) – die Fallbibliothek
├── prisma/               Datenbankschema und Migrationen
├── shared/               Fallschema (zod) und Datentypen für Clients
├── server/
│   ├── game/             Engine, Projektionen (Spoilerschutz), Validator, Sitzungen, Bibliothek
│   ├── twitch/           OAuth/Helix, EventSub-WebSocket-Client, Chat-Brücke
│   ├── realtime/         Socket.IO mit Rollen-Räumen und Differenz-Updates
│   ├── http/             REST-API
│   ├── auth/             Anmeldung, Sitzungen, Gastschlüssel
│   └── security/         Verschlüsselung, Ratenbegrenzung
├── web/src/              React-Oberflächen (Landing, Dashboard, Kontrollzentrum, Zuschauer, Overlay, Admin)
├── tests/                Vitest-Tests
├── e2e/                  Playwright-Rauchtest
└── docs/                 Architektur, Fälle schreiben, Twitch
```

## Weitere Dokumentation

- [`docs/ARCHITEKTUR.md`](docs/ARCHITEKTUR.md) – Architektur, Datenmodell, Rollen, Spoilerschutz, Skalierung, Erweiterungen
- [`docs/FAELLE.md`](docs/FAELLE.md) – Fälle schreiben, Bedingungssprache, Validator
- [`docs/TWITCH.md`](docs/TWITCH.md) – Twitch-Einrichtung, Scopes, Fehlerbehebung
