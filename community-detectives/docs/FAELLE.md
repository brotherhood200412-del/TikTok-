# Fälle schreiben

Ein Fall ist eine YAML-Datei in `content/cases/`. Nach dem Speichern:

```bash
npm run cases:validate content/cases/mein-fall.yaml   # prüfen
npm run cases:import                                  # in die Datenbank übernehmen
```

Nur Fälle **ohne Fehler** werden veröffentlicht. Hinweise (⚠) sind Empfehlungen. Die Fallverwaltung (`/admin`) zeigt dieselben Berichte und erlaubt Veröffentlichen/Zurückziehen sowie Exklusiv-Reservierungen.

> Tipp: Werte mit Doppelpunkt + Leerzeichen müssen in YAML in Anführungszeichen stehen. `python3 scripts/yaml-quote-fix.py content/cases/mein-fall.yaml` erledigt das automatisch.

## Grundprinzip

1. **Erst die Wahrheit**, dann die Spuren. Schreibe die `solution.truthTimeline` zuerst. Jede Spur muss aus dieser Wahrheit folgen.
2. **Erkenntnisse (`insights`) sind die Bausteine.** Alles, was die Community herausfindet, ist eine Erkenntnis. Erkenntnisse entstehen durch:
   - **Hotspots**: ein markierbares Detail in einem Beweis (`evidence[].hotspots`)
   - **Verbindungen**: zwei Elemente (Beweis, Erkenntnis oder Person) gehören zusammen (`connections`)
   - **Rätsel** (`puzzles[].reveals`)
   - **Vernehmungsantworten** (`responses[].reveals`)
   - **Ereignisse** (`events[].reveals`)
3. **Freischaltungen** (`unlock`) steuern Dramaturgie: Beweise, Personen, Rätsel und Fragen erscheinen erst, wenn die Bedingung erfüllt ist.
4. **Die Lösungskette** (`solution.keyInsights`, `solution.chain`) muss **ohne falsche Anschuldigung** erreichbar sein und den Täter belasten (`characters` der Erkenntnis).
5. **Falsche Fährten** (`solution.redHerrings`) brauchen eine Erkenntnis, die sie fair auflöst (`debunkedBy`).

## Aufbau (Kurzreferenz)

```yaml
id: mein-fall                 # eindeutig, Kleinbuchstaben
version: 1
title: …
tagline: …
genre: mord                   # mord|vermisst|raub|kunstdiebstahl|entfuehrung|coldcase|wirtschaft|mysterioes|betrug|verschwunden|vorfall|verschwoerung
difficulty: experte           # einsteiger|fortgeschritten|experte|meisterdetektiv
tier: free                    # free|creator|premium
estimatedMinutes: 90
accent: "#6b4f8a"
exclusive: { eventTag: halloween-2026 }          # optional: nur für reservierte Streamer
series: { id: schattenkreis, title: Der Schattenkreis, part: 1, teaser: … }   # optional

briefing: { location, date, intro, objective, question }
phases: [ { id, title, goal } ]                  # die Spielleitung wechselt Phasen manuell
characters: [ { id, name, role: suspect|witness|victim|other, age, occupation, profile, personality, relation, alibi, motive, unlock?, secret } ]
insights: [ { id, title, text, category, characters: [ids], timeline?: { time, sort, text } } ]
evidence: [ { id, title, summary, source, unlock?, content: {…}, hotspots: [ { item, insight, feedback? } ] } ]
connections: [ { id, a, b, insight } ]
interrogations: [ { character, intro, topics: [ { id, question, unlock?, responses: [ { when?, mood, stress, reveals?, text } ] } ] } ]
puzzles: [ { id, title, type, prompt, evidence: [ids], unlock?, input, answer, hints: […], reveals: [ids], success } ]
events: [ { id, title, source, text, trigger: { minutes?, when? }, reveals: [ids] } ]
accusation: { question, proof?: { question, options: [ { id, label, correct } ] } }
gmNotes: [ { phase?, text } ]
solution: { culprit, accomplices, headline, motive, method, summary, keyInsights, chain, truthTimeline, redHerrings, epilogue }
```

### Beweisarten (`content.kind`)

| Art | Felder | Markierbare Elemente |
|---|---|---|
| `document` | `docType` (letter, report, receipt, log, email, note, newspaper, statement, form, diary), `heading`, `meta`, `lines`, `footer` | jede Zeile |
| `photo` | `scene` (interior, street, platform, office, garden, gallery, archive, night), `caption`, `timestamp`, `elements` (x/y/w/h in %, `shape`) | jedes Element |
| `audio` | `duration`, `recordedAt`, `lines` (t, speaker, text) | jede Transkriptzeile |
| `map` | `title`, `places` (x/y in %), `routes` | Orte und Routen |
| `messages` | `app`, `owner`, `messages` | jede Nachricht |
| `table` | `heading`, `columns`, `rows`, `note` | jede Zeile |
| `object` | `description`, `details` | jedes Detail |

Wichtig für Fairness: Die **Details sind für alle sichtbar** (z. B. `detail` eines Fotoelements). Welche davon Hotspots sind, bleibt geheim. Wer genau liest, kann jede Schlussfolgerung selbst ziehen – das Markieren sichert sie für das Team.

### Bedingungen

```yaml
unlock: { insight: in_x }                    # Erkenntnis gefunden
unlock: { evidence: ev_y }                   # Beweis verfügbar
unlock: { puzzle: p_z }                      # Rätsel gelöst
unlock: { event: ev_e }                      # Ereignis ausgelöst
unlock: { topic: person.frage }              # Frage gestellt
unlock: { phase: phase_id }                  # Phase erreicht (oder später)
unlock: { minutes: 20 }                      # Spielminuten (pausenbewusst)
unlock: { wrongAccusations: 1 }              # nach falscher Anklage
unlock: { all: [ …, … ] }                    # und
unlock: { any: [ …, … ] }                    # oder
unlock: { not: … }                           # nicht (Vorsicht: Sackgassengefahr)
```

### Vernehmungen

Antworten werden **von oben nach unten** geprüft, die erste mit erfüllter `when`-Bedingung gilt. Die **letzte Antwort muss eine Standardantwort ohne `when`** sein. So reagiert eine Figur auf neue Beweise:

```yaml
- id: abend
  question: Wo waren Sie um 21 Uhr?
  responses:
    - when: { insight: in_alibi_falsch }
      mood: nervoes          # ruhig|kooperativ|nervoes|ausweichend|wuetend|verzweifelt|gebrochen|arrogant
      stress: 70             # 0–100, wird im Overlay als Anspannung gezeigt
      text: "… Gut. Ich war noch im Büro."
    - mood: ruhig
      text: "Zu Hause."
```

### Rätsel

```yaml
input: { kind: text, placeholder: "HH:MM" }
answer: { accept: ["23:40", "2340"] }        # Vergleich ohne Groß-/Kleinschreibung, Leer- und Satzzeichen; ä→ae usw.

input: { kind: choice, options: [ { id: a, label: … }, … ] }
answer: { choice: a }

input: { kind: order, items: [ { id: x, label: … }, … ] }
answer: { order: [x, y, z] }
```

Mindestens zwei Hilfestufen (`hints`) – die letzte darf fast die Lösung verraten.

### Ereignisse

- `trigger: { minutes: 20 }` – nach 20 Spielminuten (abschaltbar: dann löst die Spielleitung manuell aus)
- `trigger: { when: { insight: … } }` – sobald die Bedingung erfüllt ist
- `trigger: { minutes: 30, when: { phase: … } }` – beides
- `trigger: { when: { wrongAccusations: 1 } }` – Reaktion auf falsche Anklage (gut, um festgefahrene Communities zurück auf die Spur zu bringen)

## Was der Validator prüft

- Schema (Pflichtfelder, Typen, ID-Format), eindeutige IDs über den ganzen Fall
- alle Verweise (Hotspots, Verbindungen, Bedingungen, Lösung, Fragen) zeigen auf existierende Elemente
- jede Erkenntnis hat mindestens eine Quelle; mehrere Hotspots auf demselben Element werden erkannt
- jede Frage endet mit einer Standardantwort; Antworten-/Optionslisten passen zu den Eingabearten
- **Simulation eines perfekten Teams**: alle Erkenntnisse, Beweise, Rätsel, Fragen, Personen und Ereignisse sind erreichbar
- **Fairness**: Schlüssel-Erkenntnisse ohne falsche Anklage erreichbar; der Täter wird durch Schlüssel-Erkenntnisse belastet; jede falsche Fährte ist auflösbar
- Zeitlinie: doppelte Sortierwerte, Uhrzeiten in falscher Reihenfolge
- Umfang je Schwierigkeitsgrad (Hinweis)
