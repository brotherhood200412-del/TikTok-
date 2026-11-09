/**
 * Projektionen: Aus der vollständigen Falldefinition und dem Spielstand wird
 * für jede Rolle genau die erlaubte Sicht erzeugt. Hier entscheidet sich der
 * Spoiler-Schutz – Clients erhalten nie die Rohdaten eines Falls.
 */
import type { CaseDefinition } from '../../shared/case/schema.js';
import type { Mood, PublicCaseView, PublicSolution, StreamerSecrets } from '../../shared/views.js';
import { describe } from './conditions.js';
import { computeAvailability, type GameState } from './engine.js';

const DEFAULT_COLORS = ['#8c6d5a', '#5a6f8c', '#7a5a8c', '#5a8c74', '#8c5a5a', '#8c845a', '#5a828c', '#6d5a8c', '#8c5a7d', '#6b8c5a'];

export type CaseGameView = Omit<
  PublicCaseView,
  'sessionId' | 'joinCode' | 'streamer' | 'vote' | 'theories' | 'leaderboard' | 'teams' | 'participants' | 'settings' | 'serverNow'
>;

export function buildSolution(def: CaseDefinition, state: GameState): PublicSolution {
  const ins = new Map(def.insights.map((i) => [i.id, i]));
  return {
    culprit: def.solution.culprit,
    accomplices: def.solution.accomplices,
    headline: def.solution.headline,
    motive: def.solution.motive,
    method: def.solution.method,
    summary: def.solution.summary,
    chain: def.solution.chain.map((c) => ({
      insight: c.insight,
      title: ins.get(c.insight)?.title ?? c.insight,
      explanation: c.explanation,
      found: !!state.insights[c.insight],
    })),
    truthTimeline: def.solution.truthTimeline,
    redHerrings: def.solution.redHerrings.map((r) => ({ character: r.character, clue: r.clue, explanation: r.explanation })),
    epilogue: def.solution.epilogue,
  };
}

export function buildGameView(def: CaseDefinition, state: GameState, now: number): CaseGameView {
  const avail = computeAvailability(def, state, now);
  const revealed = state.status === 'revealed' || state.status === 'ended';
  const interrogable = new Set(def.interrogations.map((i) => i.character));
  const insightTitle = new Map(def.insights.map((i) => [i.id, i.title]));

  const characters = def.characters
    .filter((c) => avail.characters.has(c.id))
    .map((c, i) => ({
      id: c.id,
      name: c.name,
      role: c.role,
      age: c.age,
      occupation: c.occupation,
      color: c.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length],
      profile: c.profile,
      personality: c.personality,
      relation: c.relation,
      alibi: c.alibi,
      motive: c.motive,
      stress: state.stress[c.id] ?? 0,
      interrogable: interrogable.has(c.id),
    }));

  const evidence = def.evidence
    .filter((e) => avail.evidence.has(e.id))
    .map((e) => {
      const found: Record<string, string> = {};
      for (const h of e.hotspots) if (state.marks[`${e.id}:${h.item}`]) found[h.item] = h.insight;
      return {
        id: e.id,
        title: e.title,
        summary: e.summary,
        source: e.source,
        content: e.content,
        found,
        unlockedAt: state.announcedEvidence.indexOf(e.id),
      };
    });

  const insights = def.insights
    .filter((i) => state.insights[i.id])
    .map((i) => ({
      id: i.id,
      title: i.title,
      text: i.text,
      category: i.category,
      characters: i.characters,
      timeline: i.timeline,
      by: state.insights[i.id].by,
      via: state.insights[i.id].via,
      at: state.insights[i.id].at,
    }))
    .sort((a, b) => a.at - b.at);

  const connections = def.connections
    .filter((c) => state.connections[c.id])
    .map((c) => ({ a: c.a, b: c.b, insight: c.insight, by: state.connections[c.id].by }));

  const puzzles = def.puzzles
    .filter((p) => avail.puzzles.has(p.id))
    .map((p) => {
      const ps = state.puzzles[p.id];
      const solved = ps?.solvedAt !== undefined;
      return {
        id: p.id,
        title: p.title,
        type: p.type,
        prompt: p.prompt,
        evidence: p.evidence.filter((e) => avail.evidence.has(e)),
        input: p.input,
        hints: p.hints.slice(0, ps?.hints ?? 0),
        hintsTotal: p.hints.length,
        solved,
        solvedBy: solved ? ps?.by : undefined,
        success: solved ? p.success : undefined,
        attempts: ps?.attempts ?? 0,
      };
    });

  const interrogationLog = Object.entries(state.topics)
    .map(([key, v]) => {
      const [charId, topicId] = key.split('.');
      const it = def.interrogations.find((x) => x.character === charId);
      const t = it?.topics.find((x) => x.id === topicId);
      const r = t?.responses[v.response];
      if (!t || !r) return null;
      return { character: charId, topic: topicId, question: t.question, answer: r.text, mood: r.mood as Mood, at: v.at };
    })
    .filter((x): x is NonNullable<typeof x> => !!x)
    .sort((a, b) => a.at - b.at);

  let interrogation: PublicCaseView['interrogation'] = null;
  if (state.interrogation) {
    const it = def.interrogations.find((x) => x.character === state.interrogation!.character);
    if (it) {
      const open = avail.topics.get(it.character) ?? [];
      const topics = it.topics
        .filter((t) => open.includes(t.id) || state.topics[`${it.character}.${t.id}`])
        .map((t) => {
          const asked = state.topics[`${it.character}.${t.id}`];
          const r = asked ? t.responses[asked.response] : undefined;
          return { id: t.id, question: t.question, asked: !!asked, answer: r?.text, mood: r?.mood as Mood | undefined };
        });
      const last = state.interrogation.last;
      const lt = last ? it.topics.find((t) => t.id === last.topic) : undefined;
      const lr = lt && last ? lt.responses[last.response] : undefined;
      interrogation = {
        character: it.character,
        intro: it.intro,
        topics,
        last: lt && lr ? { topic: lt.id, question: lt.question, answer: lr.text, mood: lr.mood as Mood } : undefined,
      };
    }
  }

  const events = def.events
    .filter((e) => state.events[e.id])
    .map((e) => ({ id: e.id, title: e.title, source: e.source, text: e.text, at: state.events[e.id].at }))
    .sort((a, b) => a.at - b.at);

  const timeline = insights
    .filter((i) => i.timeline)
    .map((i) => ({ ...i.timeline!, insight: i.id }))
    .sort((a, b) => a.sort - b.sort);

  const view: CaseGameView = {
    status: state.status,
    elapsedMs: state.elapsedMs,
    runningSince: state.runningSince,
    case: {
      id: def.id,
      title: def.title,
      tagline: def.tagline,
      genre: def.genre,
      difficulty: def.difficulty,
      accent: def.accent,
      briefing: def.briefing,
      series: def.series,
    },
    phases: def.phases,
    phaseIndex: state.phaseIndex,
    task: state.task,
    spotlight: state.spotlight,
    characters,
    evidence,
    insights,
    connections,
    puzzles,
    interrogation,
    interrogationLog,
    events,
    timeline,
    feed: state.feed.slice(-40),
    progress: {
      insights: insights.length,
      insightsTotal: def.insights.length,
      evidence: evidence.length,
      puzzlesSolved: puzzles.filter((p) => p.solved).length,
      puzzlesTotal: def.puzzles.length,
    },
    accusation: {
      question: def.accusation.question,
      proof: def.accusation.proof
        ? { question: def.accusation.proof.question, options: def.accusation.proof.options.map((o) => ({ id: o.id, label: o.label })) }
        : undefined,
      attempts: state.accusations.map((a) => ({ suspect: a.suspect, correct: a.correct, at: a.at })),
    },
  };
  if (revealed) {
    view.solution = buildSolution(def, state);
    // Nach der Auflösung dürfen alle Personen gezeigt werden.
    void insightTitle;
  }
  return view;
}

export function buildStreamerSecrets(def: CaseDefinition, state: GameState, now: number): StreamerSecrets {
  const avail = computeAvailability(def, state, now);
  const titles = new Map<string, string>();
  for (const i of def.insights) titles.set(`insight:${i.id}`, i.title);
  for (const e of def.evidence) titles.set(`evidence:${e.id}`, e.title);
  for (const p of def.puzzles) titles.set(`puzzle:${p.id}`, p.title);
  for (const e of def.events) titles.set(`event:${e.id}`, e.title);
  for (const p of def.phases) titles.set(`phase:${p.id}`, p.title);
  for (const it of def.interrogations) for (const t of it.topics) titles.set(`topic:${it.character}.${t.id}`, t.question);
  const names = (kind: string, id: string) => titles.get(`${kind}:${id}`) ?? id;
  const anyTitle = (id: string) =>
    titles.get(`evidence:${id}`) ?? titles.get(`insight:${id}`) ?? def.characters.find((c) => c.id === id)?.name ?? id;
  const key = new Set(def.solution.keyInsights);
  const culprit = def.characters.find((c) => c.id === def.solution.culprit);

  return {
    solution: { ...buildSolution(def, state), keyInsights: def.solution.keyInsights },
    gmNotes: def.gmNotes,
    characterSecrets: Object.fromEntries(def.characters.map((c) => [c.id, c.secret])),
    hotspots: def.evidence.flatMap((e) =>
      e.hotspots.map((h) => ({
        evidence: e.id,
        evidenceTitle: e.title,
        item: h.item,
        insight: h.insight,
        insightTitle: names('insight', h.insight),
        found: !!state.marks[`${e.id}:${h.item}`],
      })),
    ),
    connections: def.connections.map((c) => ({
      id: c.id,
      a: c.a,
      b: c.b,
      aTitle: anyTitle(c.a),
      bTitle: anyTitle(c.b),
      insight: c.insight,
      found: !!state.connections[c.id],
    })),
    puzzles: def.puzzles.map((p) => ({
      id: p.id,
      title: p.title,
      answer:
        'accept' in p.answer
          ? p.answer.accept.join(' / ')
          : 'choice' in p.answer
            ? (p.input.kind === 'choice' ? p.input.options.find((o) => o.id === (p.answer as { choice: string }).choice)?.label : undefined) ?? p.answer.choice
            : p.answer.order.map((id) => (p.input.kind === 'order' ? p.input.items.find((i) => i.id === id)?.label : id)).join(' → '),
      hints: p.hints,
      available: avail.puzzles.has(p.id),
      solved: state.puzzles[p.id]?.solvedAt !== undefined,
      unlock: describe(p.unlock, names),
    })),
    lockedEvidence: def.evidence.filter((e) => !avail.evidence.has(e.id)).map((e) => ({ id: e.id, title: e.title, unlock: describe(e.unlock, names) })),
    events: def.events.map((e) => ({
      id: e.id,
      title: e.title,
      text: e.text,
      fired: !!state.events[e.id],
      available: avail.events.has(e.id),
      trigger: [e.trigger.minutes ? `nach ${e.trigger.minutes} Min.` : null, e.trigger.when ? describe(e.trigger.when, names) : null, !e.trigger.minutes && !e.trigger.when ? 'manuell' : null]
        .filter(Boolean)
        .join(' · '),
    })),
    interrogations: def.interrogations.map((it) => ({
      character: it.character,
      name: def.characters.find((c) => c.id === it.character)?.name ?? it.character,
      topics: it.topics.map((t) => ({
        id: t.id,
        question: t.question,
        available: avail.topics.get(it.character)?.includes(t.id) ?? false,
        asked: !!state.topics[`${it.character}.${t.id}`],
        unlock: describe(t.unlock, names),
        responses: t.responses.map((r) => ({ when: r.when ? describe(r.when, names) : 'Standard', text: r.text, reveals: r.reveals, mood: r.mood })),
      })),
    })),
    insightsAll: def.insights.map((i) => ({ id: i.id, title: i.title, found: !!state.insights[i.id], key: key.has(i.id) })),
    proofCorrect: def.accusation.proof?.options.find((o) => o.correct)?.id,
    culpritName: culprit?.name ?? def.solution.culprit,
  };
}
