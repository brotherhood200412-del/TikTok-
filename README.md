# TikTok – Geld & Mindset Videos

Fertige Hochkant-Videos (1080×1920, 30 fps, **61,5 Sekunden**, also über 1 Minute für das Creator-Rewards-Programm) mit animierter Typo, Farb-Highlights, Zähler- und Diagramm-Animationen, Hintergrund-Beat und Soundeffekten.

## Fertige Videos (`videos/`)

| Datei | Thema | Farbe |
|---|---|---|
| `01_geld_regeln.mp4` | 5 Geld-Regeln, die Reiche niemals brechen | Gold |
| `02_arm_vs_reich_mindset.mp4` | Arm vs. Reich: der Unterschied ist im Kopf | Grün |
| `03_ein_prozent_regel.mp4` | Die 1-%-Regel (Gewohnheiten & Zinseszins) | Lila |

Zu jedem Video gibt es dazu:
- `*_cover.png` – Titelbild für TikTok
- `*_caption.txt` – Beschreibung mit Hashtags zum Reinkopieren

## Soundeffekte

Alle Sounds und die Musik werden vom Skript selbst erzeugt, deshalb gibt es **keine Urheberrechtsprobleme**:
Impact/Boom beim Hook, Whoosh bei jedem Szenenwechsel, Pops bei den Wörtern, Ding bei Highlights,
Ticken beim Hochzählen, Ka-Ching-Kassensound, Fehler-Buzz bei „Arm denkt“ und ein ruhiger Beat (Am–F–C–G, 96 BPM), der unter den Effekten automatisch leiser wird.

## Neue Videos erstellen

1. Kopiere ein Skript aus `skripte/` und ändere die Texte.
2. Rendern:
   ```bash
   python3 generator/make_video.py skripte/04_mein_video.json
   ```
   Du brauchst Python 3 mit `numpy` und `Pillow` sowie `ffmpeg`.

**Szenen-Typen:** `hook`, `text`, `counter` (zählt eine Zahl hoch, mit Diagramm), `versus` (Arm vs. Reich), `cta` (Abschluss mit Folgen-Button).
**Farben im Text:** `*wort` = Themenfarbe, `+wort` = Grün, `!wort` = Rot.
**Themes:** `gold`, `green`, `purple`.
Ist das Skript kürzer als 61,5 s, wird die letzte Szene automatisch verlängert.

## Tipps, damit die Videos wirklich Geld bringen

- **Creator Rewards** setzt voraus: 18+, mindestens 10.000 Follower, 100.000 Aufrufe in 30 Tagen, Videos über 1 Minute und **originale Inhalte**.
- Reine Text-Videos stuft TikTok manchmal als „wenig originell“ ein. **Sprich den Text selbst ein** (einfach in TikTok über das Video aufnehmen). Das erhöht die Chance auf Vergütung und die Watchtime deutlich.
- Wichtig ist die Aufrufdauer: Die erste Sekunde (der Hook) entscheidet. Poste regelmäßig, am besten 1–2 Videos am Tag.
- Die Zahlen sind Beispielrechnungen und keine Anlageberatung. Schreib das bei Bedarf in die Beschreibung.

Schrift: Inter (SIL Open Font License, siehe `fonts/LICENSE-Inter.txt`).
