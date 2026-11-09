/**
 * Datenmodell eines Falls (Content-Format).
 *
 * Fälle werden als YAML-Dateien in `content/cases/` geschrieben, mit diesem
 * Schema geprüft, logisch validiert (siehe validator.ts) und anschließend in
 * die Datenbank importiert. Felder, die die Wahrheit des Falls verraten
 * (solution, hotspots, connections, Rätsel-Antworten, secret-Notizen),
 * verlassen den Server niemals in der Spieler-Projektion.
 */
import { z } from 'zod';

export const GENRES = {
  mord: 'Mordfall',
  vermisst: 'Vermisstenfall',
  raub: 'Raubüberfall',
  kunstdiebstahl: 'Kunstdiebstahl',
  entfuehrung: 'Entführungsfall',
  coldcase: 'Cold Case',
  wirtschaft: 'Wirtschaftskriminalität',
  mysterioes: 'Mysteriöser Todesfall',
  betrug: 'Betrugsfall',
  verschwunden: 'Verschwundener Gegenstand',
  vorfall: 'Geheimnisvoller Vorfall',
  verschwoerung: 'Komplexe Verschwörung',
} as const;
export type Genre = keyof typeof GENRES;

export const DIFFICULTIES = {
  einsteiger: 'Einsteiger',
  fortgeschritten: 'Fortgeschritten',
  experte: 'Experte',
  meisterdetektiv: 'Meisterdetektiv',
} as const;
export type Difficulty = keyof typeof DIFFICULTIES;

export const TIERS = ['free', 'creator', 'premium'] as const;
export type Tier = (typeof TIERS)[number];

const id = z
  .string()
  .regex(/^[a-z0-9][a-z0-9_-]*$/, 'IDs bestehen aus Kleinbuchstaben, Ziffern, - und _');

/** Freischaltbedingungen – eine kleine, deterministische Bedingungssprache. */
export type Condition =
  | { insight: string }
  | { evidence: string }
  | { puzzle: string }
  | { event: string }
  | { phase: string }
  | { topic: string }
  | { minutes: number }
  | { wrongAccusations: number }
  | { all: Condition[] }
  | { any: Condition[] }
  | { not: Condition };

export const conditionSchema: z.ZodType<Condition> = z.lazy(() =>
  z.union([
    z.strictObject({ insight: id }),
    z.strictObject({ evidence: id }),
    z.strictObject({ puzzle: id }),
    z.strictObject({ event: id }),
    z.strictObject({ phase: id }),
    z.strictObject({ topic: z.string().regex(/^[a-z0-9_-]+\.[a-z0-9_-]+$/, 'topic: "<charakter>.<thema>"') }),
    z.strictObject({ minutes: z.number().int().min(0) }),
    z.strictObject({ wrongAccusations: z.number().int().min(1) }),
    z.strictObject({ all: z.array(conditionSchema).min(1) }),
    z.strictObject({ any: z.array(conditionSchema).min(1) }),
    z.strictObject({ not: conditionSchema }),
  ]),
);

const text = z.string().min(1);
const time = z.string().min(1); // frei formatiert, z. B. "21:47" oder "14.03.1987, 22:10"

/* ------------------------------------------------------------------ */
/* Beweismittel-Inhalte. Jedes markierbare Element besitzt eine ID.     */
/* ------------------------------------------------------------------ */

const lineSchema = z.strictObject({ id, text: z.string() });

const documentContent = z.strictObject({
  kind: z.literal('document'),
  docType: z.enum(['letter', 'report', 'receipt', 'log', 'email', 'note', 'newspaper', 'statement', 'form', 'diary']),
  heading: z.string().optional(),
  meta: z.array(z.strictObject({ label: z.string(), value: z.string() })).default([]),
  lines: z.array(lineSchema).min(1),
  footer: z.string().optional(),
});

const sceneElement = z.strictObject({
  id,
  label: text,
  detail: text,
  x: z.number().min(0).max(100),
  y: z.number().min(0).max(100),
  w: z.number().min(2).max(100),
  h: z.number().min(2).max(100),
  shape: z.enum(['rect', 'round', 'person', 'door', 'window', 'table', 'clock', 'paper', 'bag', 'car', 'plant', 'shelf', 'frame', 'lamp', 'screen', 'bottle', 'box']).default('rect'),
});

const photoContent = z.strictObject({
  kind: z.literal('photo'),
  scene: z.enum(['interior', 'street', 'platform', 'office', 'garden', 'gallery', 'archive', 'night']),
  caption: text,
  timestamp: z.string().optional(),
  elements: z.array(sceneElement).min(2),
});

const audioContent = z.strictObject({
  kind: z.literal('audio'),
  duration: z.string(),
  recordedAt: z.string().optional(),
  lines: z.array(z.strictObject({ id, t: z.string(), speaker: z.string(), text: z.string() })).min(1),
});

const mapContent = z.strictObject({
  kind: z.literal('map'),
  title: z.string(),
  places: z.array(z.strictObject({ id, label: text, detail: text, x: z.number().min(0).max(100), y: z.number().min(0).max(100) })).min(2),
  routes: z
    .array(z.strictObject({ id, from: id, to: id, label: text, detail: z.string().default('') }))
    .default([]),
});

const messagesContent = z.strictObject({
  kind: z.literal('messages'),
  app: z.string(),
  owner: z.string(),
  messages: z.array(z.strictObject({ id, from: z.string(), time: z.string(), text: z.string() })).min(1),
});

const tableContent = z.strictObject({
  kind: z.literal('table'),
  heading: z.string(),
  columns: z.array(z.string()).min(1),
  rows: z.array(z.strictObject({ id, cells: z.array(z.string()) })).min(1),
  note: z.string().optional(),
});

const objectContent = z.strictObject({
  kind: z.literal('object'),
  description: text,
  details: z.array(lineSchema).min(1),
});

export const evidenceContentSchema = z.discriminatedUnion('kind', [
  documentContent,
  photoContent,
  audioContent,
  mapContent,
  messagesContent,
  tableContent,
  objectContent,
]);
export type EvidenceContent = z.infer<typeof evidenceContentSchema>;

export const evidenceSchema = z.strictObject({
  id,
  title: text,
  summary: text,
  source: z.string().default('Spurensicherung'),
  unlock: conditionSchema.optional(),
  content: evidenceContentSchema,
  /** GEHEIM: Welche markierbaren Elemente führen zu welcher Erkenntnis. */
  hotspots: z.array(z.strictObject({ item: id, insight: id, feedback: z.string().optional() })).default([]),
});
export type Evidence = z.infer<typeof evidenceSchema>;

export const characterSchema = z.strictObject({
  id,
  name: text,
  role: z.enum(['suspect', 'witness', 'victim', 'other']),
  age: z.number().int().optional(),
  occupation: text,
  color: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
  profile: text,
  personality: text,
  relation: text,
  alibi: z.string().optional(),
  motive: z.string().optional(),
  unlock: conditionSchema.optional(),
  /** GEHEIM (Spielleiter): Was diese Figur verbirgt. */
  secret: text,
});
export type Character = z.infer<typeof characterSchema>;

export const insightSchema = z.strictObject({
  id,
  title: text,
  text: text,
  category: z.enum(['spur', 'alibi', 'motiv', 'zeitlinie', 'widerspruch', 'wendung', 'entlastung', 'identitaet']),
  characters: z.array(id).default([]),
  timeline: z.strictObject({ time, sort: z.number(), text }).optional(),
});
export type Insight = z.infer<typeof insightSchema>;

export const responseSchema = z.strictObject({
  when: conditionSchema.optional(),
  mood: z.enum(['ruhig', 'kooperativ', 'nervoes', 'ausweichend', 'wuetend', 'verzweifelt', 'gebrochen', 'arrogant']).default('ruhig'),
  text: text,
  reveals: id.optional(),
  stress: z.number().int().min(0).max(100).default(0),
});

export const interrogationSchema = z.strictObject({
  character: id,
  intro: z.string().optional(),
  topics: z
    .array(
      z.strictObject({
        id,
        question: text,
        unlock: conditionSchema.optional(),
        responses: z.array(responseSchema).min(1),
      }),
    )
    .min(1),
});
export type Interrogation = z.infer<typeof interrogationSchema>;

const puzzleInput = z.discriminatedUnion('kind', [
  z.strictObject({ kind: z.literal('text'), placeholder: z.string().optional() }),
  z.strictObject({ kind: z.literal('choice'), options: z.array(z.strictObject({ id, label: text })).min(2) }),
  z.strictObject({ kind: z.literal('order'), items: z.array(z.strictObject({ id, label: text })).min(3) }),
]);

export const puzzleSchema = z.strictObject({
  id,
  title: text,
  type: z.enum(['code', 'cipher', 'logic', 'time', 'compare', 'image', 'audio', 'map', 'order', 'contradiction', 'combine']),
  prompt: text,
  evidence: z.array(id).default([]),
  unlock: conditionSchema.optional(),
  input: puzzleInput,
  /** GEHEIM: akzeptierte Antworten. */
  answer: z.union([
    z.strictObject({ accept: z.array(text).min(1) }),
    z.strictObject({ choice: id }),
    z.strictObject({ order: z.array(id).min(3) }),
  ]),
  hints: z.array(text).min(1),
  reveals: z.array(id).min(1),
  success: text,
});
export type Puzzle = z.infer<typeof puzzleSchema>;

export const connectionSchema = z.strictObject({
  id,
  a: id,
  b: id,
  insight: id,
});
export type Connection = z.infer<typeof connectionSchema>;

export const eventSchema = z.strictObject({
  id,
  title: text,
  source: z.string().default('Ermittlungsleitung'),
  text: text,
  trigger: z.strictObject({
    minutes: z.number().int().min(1).optional(),
    when: conditionSchema.optional(),
  }),
  reveals: z.array(id).default([]),
});
export type CaseEvent = z.infer<typeof eventSchema>;

export const solutionSchema = z.strictObject({
  culprit: id,
  accomplices: z.array(id).default([]),
  headline: text,
  motive: text,
  method: text,
  summary: text,
  keyInsights: z.array(id).min(2),
  chain: z.array(z.strictObject({ insight: id, explanation: text })).min(2),
  truthTimeline: z.array(z.strictObject({ time, text })).min(3),
  redHerrings: z.array(z.strictObject({ character: id.optional(), clue: z.string(), debunkedBy: id, explanation: text })).default([]),
  epilogue: text,
});
export type Solution = z.infer<typeof solutionSchema>;

export const caseSchema = z.strictObject({
  id,
  version: z.number().int().min(1),
  language: z.literal('de').default('de'),
  title: text,
  tagline: text,
  genre: z.enum(Object.keys(GENRES) as [Genre, ...Genre[]]),
  difficulty: z.enum(Object.keys(DIFFICULTIES) as [Difficulty, ...Difficulty[]]),
  tier: z.enum(TIERS).default('free'),
  published: z.boolean().default(true),
  estimatedMinutes: z.number().int().min(15),
  exclusive: z.strictObject({ eventTag: id, note: z.string().optional() }).optional(),
  series: z.strictObject({ id, title: text, part: z.number().int().min(1), teaser: z.string().optional() }).optional(),
  accent: z.string().regex(/^#[0-9a-fA-F]{6}$/).default('#b3262e'),
  briefing: z.strictObject({
    location: text,
    date: text,
    intro: text,
    objective: text,
    question: text,
  }),
  phases: z.array(z.strictObject({ id, title: text, goal: text })).min(2),
  characters: z.array(characterSchema).min(3),
  insights: z.array(insightSchema).min(3),
  evidence: z.array(evidenceSchema).min(5),
  connections: z.array(connectionSchema).default([]),
  interrogations: z.array(interrogationSchema).default([]),
  puzzles: z.array(puzzleSchema).default([]),
  events: z.array(eventSchema).default([]),
  accusation: z.strictObject({
    question: text,
    proof: z
      .strictObject({
        question: text,
        options: z.array(z.strictObject({ id, label: text, correct: z.boolean().default(false) })).min(3),
      })
      .optional(),
  }),
  /** GEHEIM: Tipps für Spielleitung und Moderation. */
  gmNotes: z.array(z.strictObject({ phase: id.optional(), text })).default([]),
  /** GEHEIM: die Wahrheit. */
  solution: solutionSchema,
});

export type CaseDefinition = z.infer<typeof caseSchema>;
export type CaseInput = z.input<typeof caseSchema>;
