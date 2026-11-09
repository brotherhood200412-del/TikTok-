# Architektur

## Überblick

```
 Twitch (EventSub WS, Helix)        Browser: Zuschauer / Streamer / OBS-Overlay
          │                                   │  HTTPS + Socket.IO
          ▼                                   ▼
 ┌──────────────────────────── Node.js-Server (TypeScript) ────────────────────────────┐
 │ ChatBridge ──► LiveSession ◄── Realtime (Socket.IO, Rollen-Räume, Diff-Updates)      │
 │   (Befehle,      │  GameEngine (deterministisch)                                     │
 │   Drosselung)    │  Projektionen: Zuschauer / Moderation / Streamer / Overlay        │
 │                  ▼                                                                    │
 │            SessionManager ── Persistenz (Prisma) ──► PostgreSQL                        │
 │ REST-API (Auth, Bibliothek, Sitzungen, Admin) · Fallvalidator · Fallimport (YAML)     │
 └───────────────────────────────────────────────────────────────────────────────────────┘
```

**Stack:** TypeScript, Node.js, Express 5, Socket.IO, Prisma 7 (Driver-Adapter `pg`), PostgreSQL, React 19 + React Router, Tailwind CSS 4, Vite, zod, Vitest, Playwright.

Bewusste Entscheidung: **ein** Node-Prozess für API, WebSockets und statische Auslieferung. Das hält Betrieb und Fehlersuche einfach und reicht für mehrere tausend gleichzeitige Zuschauer pro Instanz (siehe Skalierung).

## Rollen und Rechte

| Rolle | Erkennung | Darf |
|---|---|---|
| **Streamer (owner)** | Anmeldesitzung `kind=streamer`, Eigentümer der Sitzung | alles inkl. geheimer Spielleiterdaten |
| **Moderation** | Twitch-Login steht in der Moderatorenliste des Streamers | Theorien hervorheben/ausblenden, Beiträge ausblenden, Teilnehmende sperren – **keine** Lösung |
| **Zuschauer** | Twitch-Login (verifiziert) oder Gast (signierter Gastschlüssel im Cookie) | Ermittlungsaktionen, Abstimmen, Theorien, Diskussion |
| **Overlay** | geheimer Overlay-Token in der URL (rotierbar) | nur lesen, nur Overlay-Sicht |
| **Admin** | Login in `ADMIN_LOGINS` | Fallverwaltung, Pläne, Reservierungen |

## Spoilerschutz

Die Wahrheit eines Falls (`solution`, `hotspots`, `connections`, Rätsel-Antworten, `secret`-Notizen, `gmNotes`, Bedingungen) liegt **nur auf dem Server**. Clients erhalten ausschließlich **Projektionen** (`server/game/projection.ts`):

- **Zuschauer**: nur freigeschaltete Beweise/Personen/Rätsel, gefundene Erkenntnisse, gestellte Fragen. Hotspot-Positionen werden nie gesendet – ob ein markiertes Detail relevant ist, entscheidet der Server. Gesperrte Inhalte existieren für den Client nicht.
- **Streamer**: zusätzlich `StreamerSecrets` (Lösung, Hotspots, Antworten, Freischaltbedingungen).
- **Overlay**: eine eigene, minimale Sicht.

Es gibt **keinen** API-Endpunkt, der Falldaten roh ausliefert. `tests/spoiler.test.ts` prüft für jeden Fall, dass selbst bei vollständig gelöstem (aber nicht aufgelöstem) Spielstand keine geheimen Schlüssel oder Lösungstexte in der Zuschauersicht landen; `tests/integration.test.ts` prüft das über das Netzwerk.

## Spiel-Engine

`server/game/engine.ts` ist deterministisch – keine Zufälle, keine KI. Alle Aktionen (Markieren, Verbinden, Rätsel, Vernehmung, Ereignisse, Anklage) verändern den Spielstand und liefern ein `ActionResult` mit Entdeckungen und Punktevergaben.

- **Bedingungssprache** (`conditions.ts`): `insight`, `evidence`, `puzzle`, `event`, `topic`, `phase`, `minutes`, `wrongAccusations`, kombinierbar mit `all`/`any`/`not`.
- **Verfügbarkeit** wird als Fixpunkt berechnet (Beweise dürfen von Beweisen abhängen).
- **Vernehmungen**: Jede Frage hat geordnete Antworten mit Bedingungen; die erste zutreffende gilt. Dadurch reagieren Figuren reproduzierbar auf neue Beweise.
- **Ereignisse**: zeitgesteuert (Spielminuten, pausenbewusst) und/oder bedingungsgesteuert; ohne Auslöser manuell. Zeitgesteuerte Ereignisse lassen sich pro Sitzung abschalten.
- **Spielzeit** zählt nur, während die Ermittlung läuft – Pausen und Serverausfälle nicht.

## Datenmodell (PostgreSQL)

| Tabelle | Inhalt |
|---|---|
| `Streamer`, `TwitchToken` | Konto, Plan, Overlay-Token; Twitch-Tokens AES-256-GCM-verschlüsselt |
| `AuthSession` | Anmeldesitzungen (nur SHA-256-Hash des Tokens) |
| `Moderator` | Moderatoren pro Streamer |
| `CaseDefinition`, `CaseReservation` | importierte Fälle inkl. Validierungsbericht; Exklusiv-Reservierungen |
| `GameSession` | Sitzung mit vollständigem Spielstand (JSON) und Einstellungen |
| `Participant`, `PointEntry` | Teilnehmende (eindeutig pro Twitch-ID bzw. Gastschlüssel), Punktebuchungen (eindeutig pro Grund/Bezug) |
| `Vote`, `Ballot` | Abstimmungen und Stimmen (eine pro Person) |
| `Theory`, `Message` | Theorien mit Unterstützern, Diskussion |
| `SessionEvent` | Ereignisprotokoll (Audit) |

## Echtzeit & Skalierung

- Pro Sitzung und Rolle ein Socket.IO-Raum. Änderungen werden **gedrosselt** (250 ms) und als **Differenz** (nur geänderte Top-Level-Felder) verschickt; große, selten geänderte Teile wie Beweisinhalte werden nicht erneut gesendet. `perMessageDeflate` komprimiert größere Nachrichten.
- Abstimmungen werden im Speicher gezählt und gebündelt gespeichert; Chat-Eingänge laufen durch Ratenbegrenzer, bevor sie die Datenbank erreichen.
- Für mehrere Instanzen: Socket.IO-Redis-Adapter und Sticky Sessions ergänzen und eine Sitzung jeweils einer Instanz zuordnen (der `SessionManager` ist bereits die einzige Stelle mit Sitzungszustand).

## Missbrauchsschutz

- Ratenbegrenzer (Token-Bucket) für Verbindungen pro IP, Socket-Events, Markieren, Verbinden, Rätselversuche (pro Rätsel), Theorien, Upvotes, Diskussion, Gast-Beitritte, Chatbefehle pro Nutzer.
- Gäste: max. 3 Gastidentitäten pro IP und Sitzung; Abstimmen kann auf verifizierte Twitch-Konten beschränkt werden.
- Punkte: eindeutige Buchungen, Upvote-Punkte gedeckelt, keine Selbstunterstützung, Moderation kann Personen sperren (ihre Stimmen werden entfernt).
- Eingaben werden mit zod validiert und bereinigt (Steuerzeichen, Längen).
- HTTP: Helmet inkl. CSP, httpOnly-/SameSite-Cookies, signierter OAuth-State gegen CSRF, keine offenen Redirects.

## Erweiterungen (vorbereitet)

- **Neue Fallpakete / eigene Fälle**: YAML ablegen, validieren, importieren.
- **Mehrteilige Serien / übergreifende Verschwörung**: Feld `series` (ID, Teil, Teaser) im Fall; Teaser erscheint in der Akte.
- **Saisonale Events / Exklusivfälle**: `exclusive.eventTag` + Reservierungen.
- **Mehrsprachigkeit**: Feld `language` je Fall; UI-Texte sind zentral in den Komponenten.
- **Weitere Rätseltypen**: Rätseltyp ist ein Label; die Eingabearten `text`, `choice`, `order` decken bereits Codes, Chiffren, Logik, Bild-, Audio-, Karten-, Reihenfolge- und Widerspruchsrätsel ab.
- **Langzeitstatistiken / Ranglisten zwischen Communities**: Punkte sind pro Twitch-ID gespeichert; die Community-Rangliste aggregiert bereits über alle Fälle eines Streamers.
