export const GENRE_LABEL: Record<string, string> = {
  mord: 'Mordfall',
  vermisst: 'Vermisstenfall',
  raub: 'Raubüberfall',
  kunstdiebstahl: 'Kunstdiebstahl',
  entfuehrung: 'Entführung',
  coldcase: 'Cold Case',
  wirtschaft: 'Wirtschaftskriminalität',
  mysterioes: 'Mysteriöser Todesfall',
  betrug: 'Betrug',
  verschwunden: 'Verschwundener Gegenstand',
  vorfall: 'Geheimnisvoller Vorfall',
  verschwoerung: 'Verschwörung',
};

export const DIFFICULTY_LABEL: Record<string, string> = {
  einsteiger: 'Einsteiger',
  fortgeschritten: 'Fortgeschritten',
  experte: 'Experte',
  meisterdetektiv: 'Meisterdetektiv',
};
export const DIFFICULTY_LEVEL: Record<string, number> = { einsteiger: 1, fortgeschritten: 2, experte: 3, meisterdetektiv: 4 };

export const STATUS_LABEL: Record<string, string> = {
  lobby: 'Vorbereitung',
  active: 'Ermittlung läuft',
  paused: 'Pausiert',
  finale: 'Finale',
  solved: 'Täter überführt',
  revealed: 'Aufgelöst',
  ended: 'Beendet',
};

export const MOOD_LABEL: Record<string, string> = {
  ruhig: 'ruhig',
  kooperativ: 'kooperativ',
  nervoes: 'nervös',
  ausweichend: 'ausweichend',
  wuetend: 'wütend',
  verzweifelt: 'verzweifelt',
  gebrochen: 'gebrochen',
  arrogant: 'arrogant',
};

export const CATEGORY_LABEL: Record<string, string> = {
  spur: 'Spur',
  alibi: 'Alibi',
  motiv: 'Motiv',
  zeitlinie: 'Zeitlinie',
  widerspruch: 'Widerspruch',
  wendung: 'Wendung',
  entlastung: 'Entlastung',
  identitaet: 'Identität',
};

export const ROLE_LABEL: Record<string, string> = { suspect: 'Verdächtig', witness: 'Zeuge/Zeugin', victim: 'Opfer', other: 'Beteiligt' };

export const PUZZLE_TYPE_LABEL: Record<string, string> = {
  code: 'Zahlencode',
  cipher: 'Verschlüsselung',
  logic: 'Logik',
  time: 'Zeitrechnung',
  compare: 'Dokumentenvergleich',
  image: 'Bildanalyse',
  audio: 'Audiohinweis',
  map: 'Karte',
  order: 'Reihenfolge',
  contradiction: 'Widerspruch',
  combine: 'Kombination',
};

export function formatDuration(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

export function initials(name: string) {
  return name
    .replace(/^Dr\.\s*/, '')
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
}
