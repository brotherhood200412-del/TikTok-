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

## NEU: „Zwei Zimmer“ (ohne Sprecher, ohne Musik)

Zwei gleiche Wohnungen nebeneinander: links ohne Mindset, rechts mit Mindset. Beide bekommen dasselbe Gehalt.
Oben läuft ein Abreißkalender durchs Jahr, unten zählt „SAVED“ mit. Texte auf Englisch.
**Keine Musik**, nur leise Soundeffekte. Den Sound legst du in TikTok beim Hochladen drauf.

| Datei | Inhalt |
|---|---|
| `videos/07_one_year_salary.mp4` | Ein Jahr, gleiches Gehalt: links ist das Geld jeden Monat weg, rechts füllt sich das Glas. Schluss: „He didn't earn more. He kept more.“ (63,5 s) |
| `videos/08_alarm_6am.mp4` | Alarm 6:00: Beide starten mit 110 kg. Links Snooze, Snacks und Handy (114 kg), rechts Training und gesundes Essen (82 kg). Schluss: „Same 24 hours. Different choices.“ (65 s) |
| `videos/09_cigarettes_vs_running.mp4` | Cigarettes vs. Running: Gleiche 10 $ am Tag über 10 Jahre. Links Zigaretten (SPENT $36,500), rechts Laufband und Sparen (SAVED $52,647). Schluss: „He didn't just save money. He saved his health.“ (65 s) |
| `videos/10_scroll_vs_post.mp4` | Scroll vs. Post: Gleiches Handy, 2 Stunden am Tag, 365 Tage. Links scrollt er im Bett (SCROLLED 730 h) und liked dabei die Videos des Rechten. Rechts nimmt er jeden Tag ein Video auf und postet es (FOLLOWERS 10,000). Schluss: „One watched. One built.“ (65 s) |
| `videos/11_car_on_credit.mp4` | Car on Credit: Gleiche 600 $ im Monat, 6 Jahre. Links neues Auto auf Raten (LOAN PAID $43,200, Wert fällt von $36,000 auf $12,779), rechts Gebrauchtwagen bar und investiert (PORTFOLIO $53,497). Schluss: „One lost value. One built it.“ (64 s) |
| `videos/12_penny_doubling.mp4` | Penny Doubling: $1,000,000 sofort oder 1 Cent, der sich 30 Tage verdoppelt. An Tag 28 überholt der Cent, an Tag 30 sind es $5,368,709.12. Schluss: „1 cent beat 1 million. Never underestimate doubling.“ (65 s) |
| `videos/13_same_job_5_years.mp4` | Same Job, 5 Years: Gleicher Job, gleiches Startgehalt von $30K. Links nach Feierabend Sofa, TV und Chips ($33,100/yr). Rechts lernt er abends Programmieren, sammelt Zertifikate und wird befördert ($90,000/yr). Schluss: „Same job. Same start. Your skills are your salary.“ (65 s) |
| `videos/14_food_delivery.mp4` | Food Delivery vs. Cooking: 25 $ Lieferung gegen 8 $ selbst kochen, 10 Jahre. SPENT $91,250 gegen INVESTED $89,499. Schluss: „Convenience is expensive. $89,500 expensive.“ (65 s) |
| `videos/15_the_wedding.mp4` | The Wedding: $30,000 Traumhochzeit gegen $5,000 Hochzeit + $25,000 investiert. Nach 30 Jahren $0 gegen $190,306. Schluss: „Same love. Different future.“ (65 s) |
| `videos/16_sports_betting.mp4` | Sports Betting vs. Investing: Gleiches Spiel, 50 $ pro Woche. SPENT ON BETS $26,000 gegen INVESTED $37,502. Schluss: „The house always wins. Be the house.“ (65 s) |
| `videos/17_party_vs_build.mp4` | Your 20s: Party vs. Build: 100 $ jedes Wochenende von 20 bis 30 feiern oder investieren. SPENT $52,000 gegen $75,003, und 30 Jahre später $570,945. Schluss: „YOLO cost him $570,945.“ (65 s) |
| `videos/18_gaming_skins.mp4` | Gaming Skins: 40 $ im Monat von 12 bis 32 für Skins oder investiert. Am Ende SERVER SHUTDOWN. SPENT $9,600 gegen INVESTED $20,837. Schluss: „Skins don't appreciate. Investments do.“ (65 s) |
| `videos/19_black_friday.mp4` | Black Friday: Countdown-Schild statt Kalender, 7 Deals. Links kauft er alles („SAVED“ $500, SPENT $2,000), rechts wischt er alles weg (STILL HAS $2,000). Schluss: „You didn't save $500. You spent $2,000.“ (65 s) |
| `videos/20_one_dollar_from_birth.mp4` | $1 a Day From Birth: AGE 1 bis 65. Links wird 1 $ täglich ausgegeben (SPENT $23,725), rechts investiert (INVESTED $481,746). Schluss: „Same $1 a day. $481,746.“ (65 s) |

```bash
python3 generator/zimmer_video.py skripte/zimmer/07_one_year_salary.json
python3 generator/wecker_video.py skripte/zimmer/08_alarm_6am.json
python3 generator/rauchen_video.py skripte/zimmer/09_cigarettes_vs_running.json
python3 generator/scroll_video.py skripte/zimmer/10_scroll_vs_post.json
python3 generator/auto_video.py skripte/zimmer/11_car_on_credit.json
python3 generator/penny_video.py skripte/zimmer/12_penny_doubling.json
python3 generator/job_video.py skripte/zimmer/13_same_job_5_years.json
python3 generator/food_video.py skripte/zimmer/14_food_delivery.json
python3 generator/wedding_video.py skripte/zimmer/15_the_wedding.json
python3 generator/betting_video.py skripte/zimmer/16_sports_betting.json
python3 generator/party_video.py skripte/zimmer/17_party_vs_build.json
python3 generator/skins_video.py skripte/zimmer/18_gaming_skins.json
python3 generator/blackfriday_video.py skripte/zimmer/19_black_friday.json
python3 generator/birth_video.py skripte/zimmer/20_one_dollar_from_birth.json
```
Wasserzeichen: In der JSON-Datei bei `"watermark"` deinen TikTok-Namen eintragen (z. B. `"@deinname"`).

## NEU: Figuren-Stil (schwarz, leuchtende Figuren)

Im Stil deines Vorbild-Videos: schwarzer Sternenhimmel, leuchtende weiße Figuren und eine Metapher pro Szene, dazu farbige Akzente (Gold = Erfolg/Geld, Rot = Komfort/Ausreden, Grün = Wachstum).

| Datei | Thema |
|---|---|
| `videos/04_traeume_vs_komfort.mp4` | Träume vs. Komfort (Mindset) |
| `videos/05_geld_falle.mp4` | Die Geld-Falle: Ausgaben, Schulden, Zinseszins |
| `videos/06_disziplin.mp4` | Disziplin schlägt Motivation |

**Szenen-Typen:** `hook` (Figur im Spotlight), `tug` (Tauziehen), `fork` (Weggabelung), `load` (Last fallen lassen),
`wall` (Mauer durchbrechen), `stairs` (Treppe), `tree` (Baum mit Münzen), `crowd` (du vs. alle), `seesaw` (Waage),
`coins` (Münzstapel/Zinseszins), `cta` (Abschluss mit Folgen-Button).

```bash
python3 generator/figuren_video.py skripte/figuren/04_traeume_vs_komfort.json
```

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
