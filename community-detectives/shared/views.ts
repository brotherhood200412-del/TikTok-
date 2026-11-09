/**
 * Datenstrukturen, die an Clients gesendet werden.
 * PublicCaseView enthält ausschließlich spielerseitige Informationen.
 * Geheime Daten existieren nur in StreamerSecrets (nur Rolle "owner").
 */
import type { EvidenceContent } from './case/schema.js';

export type SessionStatus = 'lobby' | 'active' | 'paused' | 'finale' | 'solved' | 'revealed' | 'ended';
export type Mood = 'ruhig' | 'kooperativ' | 'nervoes' | 'ausweichend' | 'wuetend' | 'verzweifelt' | 'gebrochen' | 'arrogant';
export type Role = 'owner' | 'moderator' | 'viewer' | 'overlay';

export interface FeedEntry {
  id: number;
  at: number;
  type: 'system' | 'insight' | 'evidence' | 'character' | 'event' | 'puzzle' | 'hint' | 'interrogation' | 'answer' | 'phase' | 'accusation' | 'reveal' | 'vote' | 'theory';
  text: string;
  by?: string;
  ref?: string;
  detail?: string;
  mood?: Mood;
}

export interface PublicCharacter {
  id: string;
  name: string;
  role: 'suspect' | 'witness' | 'victim' | 'other';
  age?: number;
  occupation: string;
  color: string;
  profile: string;
  personality: string;
  relation: string;
  alibi?: string;
  motive?: string;
  stress: number;
  interrogable: boolean;
}

export interface PublicEvidence {
  id: string;
  title: string;
  summary: string;
  source: string;
  content: EvidenceContent;
  /** Bereits vom Team gesicherte Details: itemId -> Erkenntnis-ID */
  found: Record<string, string>;
  unlockedAt: number;
}

export interface PublicInsight {
  id: string;
  title: string;
  text: string;
  category: string;
  characters: string[];
  timeline?: { time: string; sort: number; text: string };
  by?: string;
  via: string;
  at: number;
}

export interface PublicPuzzle {
  id: string;
  title: string;
  type: string;
  prompt: string;
  evidence: string[];
  input:
    | { kind: 'text'; placeholder?: string }
    | { kind: 'choice'; options: { id: string; label: string }[] }
    | { kind: 'order'; items: { id: string; label: string }[] };
  hints: string[];
  hintsTotal: number;
  solved: boolean;
  solvedBy?: string;
  success?: string;
  attempts: number;
}

export interface PublicTopic {
  id: string;
  question: string;
  asked: boolean;
  answer?: string;
  mood?: Mood;
}

export interface PublicInterrogation {
  character: string;
  intro?: string;
  topics: PublicTopic[];
  last?: { topic: string; question: string; answer: string; mood: Mood };
}

export interface PublicVote {
  id: string;
  kind: string;
  question: string;
  options: { label: string; ref?: string }[];
  counts: number[];
  total: number;
  endsAt: number;
  status: 'open' | 'closed' | 'cancelled';
  winner?: number;
  tie?: number[];
}

export interface PublicTheory {
  id: string;
  author: string;
  authorId: string;
  suspectId: string;
  text: string;
  evidenceIds: string[];
  upvotes: number;
  status: 'visible' | 'hidden' | 'featured';
  createdAt: number;
}

export interface LeaderboardEntry {
  id: string;
  name: string;
  points: number;
  team?: string | null;
}

export interface PublicSolution {
  culprit: string;
  accomplices: string[];
  headline: string;
  motive: string;
  method: string;
  summary: string;
  chain: { insight: string; title: string; explanation: string; found: boolean }[];
  truthTimeline: { time: string; text: string }[];
  redHerrings: { character?: string; clue: string; explanation: string }[];
  epilogue: string;
}

export interface PublicCaseView {
  sessionId: string;
  joinCode: string;
  streamer: { login: string; displayName: string };
  status: SessionStatus;
  elapsedMs: number;
  runningSince: number | null;
  serverNow: number;
  case: {
    id: string;
    title: string;
    tagline: string;
    genre: string;
    difficulty: string;
    accent: string;
    briefing: { location: string; date: string; intro: string; objective: string; question: string };
    series?: { id: string; title: string; part: number; teaser?: string };
  };
  phases: { id: string; title: string; goal: string }[];
  phaseIndex: number;
  task: string | null;
  spotlight: { type: string; id: string } | null;
  characters: PublicCharacter[];
  evidence: PublicEvidence[];
  insights: PublicInsight[];
  connections: { a: string; b: string; insight: string; by?: string }[];
  puzzles: PublicPuzzle[];
  interrogation: PublicInterrogation | null;
  interrogationLog: { character: string; topic: string; question: string; answer: string; mood: Mood; at: number }[];
  events: { id: string; title: string; source: string; text: string; at: number }[];
  timeline: { time: string; sort: number; text: string; insight: string }[];
  feed: FeedEntry[];
  progress: { insights: number; insightsTotal: number; evidence: number; puzzlesSolved: number; puzzlesTotal: number };
  accusation: {
    question: string;
    proof?: { question: string; options: { id: string; label: string }[] };
    attempts: { suspect: string; correct: boolean; at: number }[];
  };
  vote: PublicVote | null;
  theories: PublicTheory[];
  leaderboard: LeaderboardEntry[];
  teams: { id: string; label: string; points: number; members: number }[];
  participants: number;
  settings: { allowGuests: boolean; discussion: boolean; theories: boolean };
  solution?: PublicSolution;
}

export interface DiscussionMessage {
  id: string;
  author: string;
  authorId: string;
  text: string;
  at: number;
  hidden?: boolean;
}

/** Nur für Streamer (owner): vollständige Spielleiter-Sicht. */
export interface StreamerSecrets {
  solution: PublicSolution & { keyInsights: string[] };
  gmNotes: { phase?: string; text: string }[];
  characterSecrets: Record<string, string>;
  hotspots: { evidence: string; evidenceTitle: string; item: string; insight: string; insightTitle: string; found: boolean }[];
  connections: { id: string; a: string; b: string; aTitle: string; bTitle: string; insight: string; found: boolean }[];
  puzzles: { id: string; title: string; answer: string; hints: string[]; available: boolean; solved: boolean; unlock: string }[];
  lockedEvidence: { id: string; title: string; unlock: string }[];
  events: { id: string; title: string; text: string; fired: boolean; available: boolean; trigger: string }[];
  interrogations: {
    character: string;
    name: string;
    topics: { id: string; question: string; available: boolean; asked: boolean; unlock: string; responses: { when: string; text: string; reveals?: string; mood: string }[] }[];
  }[];
  insightsAll: { id: string; title: string; found: boolean; key: boolean }[];
  proofCorrect?: string;
  culpritName: string;
}

export interface PersonalState {
  participantId: string;
  displayName: string;
  points: number;
  team: string | null;
  rank: number | null;
  verified: boolean;
  moderator: boolean;
  myVote: number | null;
  upvoted: string[];
}

export interface OverlayView {
  status: SessionStatus;
  title: string;
  tagline: string;
  accent: string;
  joinCode: string;
  joinUrl: string;
  phase: string;
  phaseIndex: number;
  phasesTotal: number;
  task: string | null;
  elapsedMs: number;
  runningSince: number | null;
  serverNow: number;
  spotlight:
    | { type: 'evidence'; title: string; summary: string }
    | { type: 'character'; name: string; occupation: string; color: string; stress: number; last?: { question: string; answer: string; mood: Mood } }
    | { type: 'insight'; title: string; text: string }
    | { type: 'puzzle'; title: string; prompt: string; solved: boolean }
    | null;
  vote: PublicVote | null;
  feed: FeedEntry[];
  progress: PublicCaseView['progress'];
  leaderboard: LeaderboardEntry[];
  teams: PublicCaseView['teams'];
  featuredTheory: PublicTheory | null;
  participants: number;
  solution?: { culpritName: string; headline: string; summary: string; correct: boolean | null };
  display: OverlaySettings;
}

export interface OverlaySettings {
  position: 'left' | 'right';
  showLeaderboard: boolean;
  showFeed: boolean;
  showJoin: boolean;
  scale: number;
}

export const TEAMS = [
  { id: 'spurensicherung', label: 'Spurensicherung', focus: 'Fotos & Gegenstände' },
  { id: 'analyse', label: 'Analyse', focus: 'Dokumente, Tabellen & Rätsel' },
  { id: 'verhoer', label: 'Verhörteam', focus: 'Aussagen & Widersprüche' },
  { id: 'archiv', label: 'Archiv', focus: 'Zeitlinie & Verbindungen' },
] as const;
export type TeamId = (typeof TEAMS)[number]['id'];
