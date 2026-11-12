# Veröffentlichen auf Render (Testbetrieb)

Die Datei `render.yaml` im Hauptordner des Repositorys richtet App und Datenbank automatisch ein.

1. render.com → „Sign in with GitHub“.
2. „New +“ → „Blueprint“ → Repository `TikTok-` verbinden.
3. Branch `claude/eloquent-lamport-2yjg6q` wählen → „Apply“ / „Deploy Blueprint“.
4. Nach dem Bau (ca. 5–10 Minuten) unter „community-detectives“ den Link `https://….onrender.com` öffnen.

Testmodus: Anmeldung ohne Twitch (Entwicklungs-Login), Chat-Simulator aktiv, alle Fälle freigeschaltet.
Für echte Streams: `TWITCH_CLIENT_ID`/`TWITCH_CLIENT_SECRET` in den Render-Umgebungsvariablen setzen,
`ALLOW_DEV_LOGIN` auf `false` stellen und die Twitch-Redirect-URL `<Render-Link>/api/auth/twitch/callback` eintragen.

Hinweise zum kostenlosen Tarif: Die App schläft nach ca. 15 Minuten ohne Besuch ein und braucht beim
nächsten Aufruf bis zu einer Minute zum Aufwachen. Die kostenlose Datenbank läuft nach 30 Tagen ab.
