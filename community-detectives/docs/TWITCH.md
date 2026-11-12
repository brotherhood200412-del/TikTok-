# Twitch-Anbindung

COMMUNITY DETECTIVES nutzt ausschließlich offizielle, aktuelle Twitch-Schnittstellen:

| Zweck | Schnittstelle |
|---|---|
| Anmeldung Streamer & Zuschauer | OAuth 2.0 Authorization Code Flow (`id.twitch.tv/oauth2/authorize`, `/token`) |
| Benutzerdaten | Helix `GET /users` |
| Chat lesen | EventSub **WebSocket** (`wss://eventsub.wss.twitch.tv/ws`), Abo `channel.chat.message` v1 |
| Chat schreiben | Helix `POST /chat/messages` |

Kein IRC, keine veralteten PubSub-Themen.

## Einrichtung

1. <https://dev.twitch.tv/console/apps> → „Anwendung registrieren“.
2. OAuth-Redirect-URL: `<PUBLIC_URL>/api/auth/twitch/callback`. `PUBLIC_URL` muss exakt der Adresse entsprechen, unter der Nutzer die App öffnen.
3. Client-ID und ein Client-Secret in `.env` eintragen:
   ```
   TWITCH_CLIENT_ID=…
   TWITCH_CLIENT_SECRET=…
   ```
4. Server neu starten. Der Entwicklungs-Login verschwindet automatisch, sobald Twitch konfiguriert ist (außer `ALLOW_DEV_LOGIN=true`).

## Berechtigungen (Scopes)

- **Streamer**: `user:read:chat`, `user:write:chat`. Die Anmeldung wird abgelehnt, wenn Twitch weniger Rechte bestätigt.
- **Zuschauer**: keine Scopes. Das Token dient nur zur Identifikation und wird sofort widerrufen.

Der Bot schreibt **mit dem Konto des Streamers** in dessen Chat (Absender = Broadcaster). Ein separates Bot-Konto ist nicht nötig.

## Ablauf im Hintergrund

1. Streamer startet eine Ermittlung → `ChatBridge.ensure()` öffnet einen EventSub-WebSocket.
2. Twitch sendet `session_welcome` → der Server legt innerhalb der Frist das Abo `channel.chat.message` (condition: `broadcaster_user_id` = `user_id` = Streamer) an.
3. `session_keepalive` hält einen Watchdog am Leben. Bleibt er aus, wird neu verbunden (exponentielles Backoff bis 60 s).
4. `session_reconnect` → Verbindung zur neuen URL, nahtloser Wechsel, **ohne** neues Abo.
5. `revocation` (z. B. Berechtigung entzogen) → Status „revoked“, sichtbar im Kontrollzentrum; Streamer meldet sich neu an.
6. Doppelte Nachrichten werden über `message_id` verworfen.
7. Abgelaufene Access-Tokens werden vor Ablauf bzw. bei HTTP 401 automatisch per Refresh-Token erneuert und verschlüsselt gespeichert.

## Fehlerbehebung

| Symptom | Ursache / Lösung |
|---|---|
| „redirect_mismatch“ bei der Anmeldung | Redirect-URL in der Twitch-Konsole ≠ `<PUBLIC_URL>/api/auth/twitch/callback` |
| Status „not_linked“ | Streamer hat sich nur lokal, nicht mit Twitch angemeldet → „Mit Twitch verbinden“ im Dashboard |
| Status „error“ mit 401/403 | Token widerrufen oder Scopes fehlen → neu anmelden; der Client verbindet sich in diesem Fall bewusst **nicht** in einer Schleife neu |
| Status „reconnecting“ | Netzwerkproblem; Wiederverbindung läuft automatisch. „Neu verbinden“ im Dashboard erzwingt einen Neustart |
| Bot antwortet nicht | Einstellung „Antworten im Twitch-Chat“ im Kontrollzentrum prüfen; Antworten haben bewusst Cooldowns |

## Testen ohne Twitch

- **Chat-Simulator** im Kontrollzentrum (außerhalb von Produktion aktiv).
- `tests/twitch.test.ts` startet einen lokalen Mock für OAuth, Helix und EventSub-WebSocket und prüft Anmeldung, verschlüsselte Token-Speicherung, Abo-Anlage, Chatbefehle, Antworten, Token-Refresh bei 401, `session_reconnect` und Wiederverbindung nach Abbruch. Die Basis-URLs lassen sich dafür über `TWITCH_AUTH_BASE`, `TWITCH_API_BASE` und `TWITCH_EVENTSUB_WS_URL` umstellen.
