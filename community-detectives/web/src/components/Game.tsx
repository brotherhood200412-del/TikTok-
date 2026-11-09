import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { DiscussionMessage, FeedEntry, PublicCaseView, PublicCharacter, PublicPuzzle, PublicTheory, PublicVote } from '../../../shared/views';
import { CATEGORY_LABEL, MOOD_LABEL, PUZZLE_TYPE_LABEL, ROLE_LABEL, formatDuration } from '../lib/format';
import { useCountdown } from '../lib/live';
import { EVIDENCE_ICON } from './Evidence';
import { Avatar, Empty, Icon } from './ui';

/* ------------------------------ Personen ------------------------------ */
export function CharacterCard({ c, onClick, active }: { c: PublicCharacter; onClick?: () => void; active?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`card group w-full p-3 text-left transition hover:border-ink-500 ${active ? '!border-blood-500 animate-pulse-red' : ''}`}
    >
      <div className="flex gap-3">
        <Avatar name={c.name} color={c.color} size={48} stress={c.stress} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-display text-base font-bold">{c.name}</span>
            <span className={`chip ${c.role === 'suspect' ? 'border-blood-600/60 text-blood-300' : 'border-ink-600 text-ink-300'}`}>{ROLE_LABEL[c.role]}</span>
          </div>
          <div className="text-xs text-ink-300">
            {c.age ? `${c.age} J. · ` : ''}
            {c.occupation}
          </div>
          <div className="mt-1 line-clamp-2 text-sm text-ink-300">{c.relation}</div>
        </div>
      </div>
      {c.stress > 0 && (
        <div className="mt-2 flex items-center gap-2 text-[11px] text-ink-400">
          Anspannung
          <div className="h-1 flex-1 overflow-hidden rounded bg-ink-700">
            <div className={`h-full ${c.stress > 60 ? 'bg-blood-400' : 'bg-brass-400'}`} style={{ width: `${c.stress}%` }} />
          </div>
        </div>
      )}
    </button>
  );
}

export function CharacterDetail({ c, log }: { c: PublicCharacter; log: PublicCaseView['interrogationLog'] }) {
  const mine = log.filter((l) => l.character === c.id);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Avatar name={c.name} color={c.color} size={72} stress={c.stress} />
        <div>
          <div className="font-display text-xl font-bold">{c.name}</div>
          <div className="text-sm text-ink-300">
            {c.age ? `${c.age} Jahre · ` : ''}
            {c.occupation}
          </div>
          <span className={`chip mt-1 ${c.role === 'suspect' ? 'border-blood-600/60 text-blood-300' : 'border-ink-600 text-ink-300'}`}>{ROLE_LABEL[c.role]}</span>
        </div>
      </div>
      <div className="paper space-y-2 px-4 py-3 text-sm">
        <Field label="Profil" value={c.profile} />
        <Field label="Persönlichkeit" value={c.personality} />
        <Field label="Beziehung" value={c.relation} />
        {c.alibi && <Field label="Angegebenes Alibi" value={c.alibi} />}
        {c.motive && <Field label="Mögliches Motiv" value={c.motive} />}
      </div>
      <div>
        <div className="label mb-2">Vernehmungsprotokoll</div>
        {mine.length === 0 ? (
          <div className="text-sm text-ink-400">{c.interrogable ? 'Noch nicht vernommen.' : 'Diese Person wird nicht vernommen.'}</div>
        ) : (
          <div className="space-y-2">
            {mine.map((l) => (
              <QA key={l.topic + l.at} q={l.question} a={l.answer} mood={l.mood} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] font-bold uppercase tracking-wider text-paper-faded">{label}</div>
      <div className="font-typewriter">{value}</div>
    </div>
  );
}

export function QA({ q, a, mood }: { q: string; a: string; mood?: string }) {
  return (
    <div className="card-inset p-3">
      <div className="text-sm font-semibold text-ink-100">„{q}“</div>
      <div className="mt-1 text-sm text-ink-300">
        {mood && <span className="mr-2 text-xs italic text-brass-300">({MOOD_LABEL[mood] ?? mood})</span>}
        {a}
      </div>
    </div>
  );
}

export function InterrogationPanel({ view }: { view: PublicCaseView }) {
  const it = view.interrogation;
  if (!it) return null;
  const c = view.characters.find((x) => x.id === it.character);
  if (!c) return null;
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-3 border-b border-ink-700 bg-gradient-to-r from-blood-800/40 to-transparent p-3">
        <Avatar name={c.name} color={c.color} size={44} stress={c.stress} />
        <div className="min-w-0">
          <div className="label !text-blood-300">Vernehmung läuft</div>
          <div className="font-display text-lg font-bold">{c.name}</div>
        </div>
      </div>
      <div className="space-y-3 p-3">
        {it.intro && <p className="text-sm italic text-ink-400">{it.intro}</p>}
        {it.last ? <QA q={it.last.question} a={it.last.answer} mood={it.last.mood} /> : <div className="text-sm text-ink-400">Die Spielleitung bzw. die Community wählt die erste Frage …</div>}
        <div className="text-xs text-ink-400">
          Mögliche Fragen: {it.topics.filter((t) => !t.asked).length} offen · {it.topics.filter((t) => t.asked).length} gestellt
        </div>
      </div>
    </div>
  );
}

/* ------------------------------ Ermittlungsboard ------------------------------ */
interface BoardItem {
  id: string;
  kind: 'insight' | 'evidence' | 'character';
  title: string;
  sub?: string;
  color?: string;
}

export function Board({
  view,
  onConnect,
  onOpen,
}: {
  view: PublicCaseView;
  onConnect?: (a: string, b: string) => Promise<void>;
  onOpen?: (item: BoardItem) => void;
}) {
  const [sel, setSel] = useState<string[]>([]);
  const [filter, setFilter] = useState<'all' | 'insight' | 'evidence' | 'character'>('all');
  const wrap = useRef<HTMLDivElement>(null);
  const refs = useRef(new Map<string, HTMLElement>());
  const [lines, setLines] = useState<{ x1: number; y1: number; x2: number; y2: number; key: string }[]>([]);

  const items: BoardItem[] = useMemo(
    () => [
      ...view.insights.map((i) => ({ id: i.id, kind: 'insight' as const, title: i.title, sub: CATEGORY_LABEL[i.category] })),
      ...view.evidence.map((e) => ({ id: e.id, kind: 'evidence' as const, title: e.title, sub: e.source })),
      ...view.characters.map((c) => ({ id: c.id, kind: 'character' as const, title: c.name, sub: c.occupation, color: c.color })),
    ],
    [view.insights, view.evidence, view.characters],
  );
  const visible = items.filter((i) => filter === 'all' || i.kind === filter);

  useLayoutEffect(() => {
    const measure = () => {
      const box = wrap.current?.getBoundingClientRect();
      if (!box) return;
      const out: typeof lines = [];
      const link = (a: string, b: string, key: string) => {
        const ea = refs.current.get(a)?.getBoundingClientRect();
        const eb = refs.current.get(b)?.getBoundingClientRect();
        if (!ea || !eb) return;
        out.push({ key, x1: ea.left + ea.width / 2 - box.left, y1: ea.top + 6 - box.top, x2: eb.left + eb.width / 2 - box.left, y2: eb.top + 6 - box.top });
      };
      for (const c of view.connections) {
        link(c.a, c.insight, `${c.a}-${c.insight}`);
        link(c.b, c.insight, `${c.b}-${c.insight}`);
      }
      setLines(out);
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [view.connections, visible.length, filter]);

  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s.slice(-1), id]));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {(['all', 'insight', 'evidence', 'character'] as const).map((f) => (
          <button key={f} className={`btn-sm ${filter === f ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setFilter(f)}>
            {{ all: 'Alles', insight: 'Erkenntnisse', evidence: 'Beweise', character: 'Personen' }[f]}
          </button>
        ))}
      </div>
      {onConnect && (
        <div className="card flex flex-col gap-2 p-3 md:flex-row md:items-center md:justify-between">
          <div className="text-sm text-ink-300">
            <Icon name="link" className="mr-1 inline h-4 w-4 text-blood-400" />
            {sel.length === 0 && 'Wähle zwei Karten, die zusammengehören – passt die Verbindung, entsteht eine neue Erkenntnis.'}
            {sel.length === 1 && <>Ausgewählt: <b>{items.find((i) => i.id === sel[0])?.title}</b> – wähle eine zweite Karte.</>}
            {sel.length === 2 && (
              <>
                <b>{items.find((i) => i.id === sel[0])?.title}</b> ↔ <b>{items.find((i) => i.id === sel[1])?.title}</b>
              </>
            )}
          </div>
          <div className="flex gap-2">
            {sel.length > 0 && (
              <button className="btn-ghost btn-sm" onClick={() => setSel([])}>
                Zurücksetzen
              </button>
            )}
            <button
              className="btn-primary btn-sm"
              disabled={sel.length !== 2}
              onClick={async () => {
                await onConnect(sel[0], sel[1]);
                setSel([]);
              }}
            >
              <Icon name="link" /> Verbindung prüfen
            </button>
          </div>
        </div>
      )}
      <div ref={wrap} className="corkboard relative rounded-xl border border-ink-700 p-4">
        <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
          {lines.map((l) => (
            <line key={l.key} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="#b3262e" strokeWidth="2" strokeOpacity="0.75" />
          ))}
        </svg>
        {visible.length === 0 ? (
          <Empty title="Das Board ist leer">Noch keine Einträge in dieser Kategorie.</Empty>
        ) : (
          <div className="relative grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 lg:grid-cols-4">
            {visible.map((it, idx) => {
              const selected = sel.includes(it.id);
              const rot = ((idx * 37) % 5) - 2;
              return (
                <div
                  key={it.id}
                  ref={(el) => {
                    if (el) refs.current.set(it.id, el);
                    else refs.current.delete(it.id);
                  }}
                  className="relative"
                  style={{ transform: `rotate(${rot * 0.5}deg)` }}
                >
                  <span className="pin" />
                  <button
                    type="button"
                    onClick={() => (onConnect ? toggle(it.id) : onOpen?.(it))}
                    onDoubleClick={() => onOpen?.(it)}
                    className={`w-full rounded-sm px-3 pb-2 pt-3 text-left shadow-lg transition ${
                      it.kind === 'insight' ? 'bg-paper-100 text-paper-ink' : it.kind === 'evidence' ? 'bg-paper-200 text-paper-ink' : 'bg-ink-700 text-ink-100'
                    } ${selected ? 'outline outline-3 outline-blood-500' : 'hover:brightness-105'}`}
                  >
                    <div className={`text-[10px] font-bold uppercase tracking-wider ${it.kind === 'character' ? 'text-ink-300' : 'text-paper-faded'}`}>
                      {it.kind === 'insight' ? `Erkenntnis · ${it.sub}` : it.kind === 'evidence' ? 'Beweis' : 'Person'}
                    </div>
                    <div className={`mt-0.5 text-sm font-bold leading-snug ${it.kind === 'character' ? 'font-display' : ''}`}>{it.title}</div>
                  </button>
                  {onOpen && onConnect && (
                    <button type="button" className="absolute bottom-1 right-1 rounded p-1 text-paper-faded hover:text-blood-500" onClick={() => onOpen(it)} aria-label="Öffnen">
                      <Icon name="eye" className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------ Zeitlinie ------------------------------ */
export function Timeline({ view }: { view: PublicCaseView }) {
  if (view.timeline.length === 0) return <Empty icon="timeline" title="Noch keine Zeitpunkte">Erkenntnisse mit Uhrzeit erscheinen hier automatisch in der richtigen Reihenfolge.</Empty>;
  return (
    <ol className="relative ml-3 border-l-2 border-blood-700/70">
      {view.timeline.map((t) => (
        <li key={t.insight} className="mb-4 ml-5 animate-fade-up">
          <span className="absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full border-2 border-ink-900 bg-blood-500" />
          <div className="font-mono text-sm font-bold text-brass-300">{t.time}</div>
          <div className="text-sm text-ink-200">{t.text}</div>
        </li>
      ))}
    </ol>
  );
}

/* ------------------------------ Rätsel ------------------------------ */
export function PuzzleCard({
  p,
  evidenceTitle,
  onAnswer,
  onHint,
  focused,
}: {
  p: PublicPuzzle;
  evidenceTitle: (id: string) => string;
  onAnswer?: (answer: string | string[]) => Promise<boolean>;
  onHint?: () => void;
  focused?: boolean;
}) {
  const [text, setText] = useState('');
  const [order, setOrder] = useState<string[]>(() => (p.input.kind === 'order' ? p.input.items.map((i) => i.id) : []));
  const [choice, setChoice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (a: string | string[]) => {
    if (!onAnswer) return;
    setBusy(true);
    const ok = await onAnswer(a);
    setBusy(false);
    if (ok) setText('');
  };
  return (
    <div className={`card p-4 ${p.solved ? 'opacity-90' : ''} ${focused ? '!border-brass-400' : ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="label">{PUZZLE_TYPE_LABEL[p.type] ?? p.type}</div>
          <div className="font-display text-lg font-bold">{p.title}</div>
        </div>
        {p.solved ? <span className="stamp animate-stamp text-xs">Gelöst</span> : focused ? <span className="chip border-brass-400 text-brass-300">Im Fokus</span> : null}
      </div>
      <p className="mt-2 text-sm text-ink-200">{p.prompt}</p>
      {p.evidence.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {p.evidence.map((e) => (
            <span key={e} className="chip border-ink-600 text-ink-300">
              <Icon name="doc" className="h-3 w-3" /> {evidenceTitle(e)}
            </span>
          ))}
        </div>
      )}
      {p.hints.length > 0 && (
        <div className="mt-3 space-y-1">
          {p.hints.map((h, i) => (
            <div key={i} className="rounded-md border border-brass-500/40 bg-brass-500/10 px-3 py-2 text-sm text-brass-300">
              <b>Hinweis {i + 1}:</b> {h}
            </div>
          ))}
        </div>
      )}
      {p.solved ? (
        <div className="mt-3 rounded-md border border-ok-600/50 bg-ok-600/10 px-3 py-2 text-sm text-ink-100">
          {p.success}
          {p.solvedBy && <div className="mt-1 text-xs text-ink-400">Gelöst von {p.solvedBy}</div>}
        </div>
      ) : (
        onAnswer && (
          <div className="mt-3 space-y-2">
            {p.input.kind === 'text' && (
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (text.trim()) void submit(text.trim());
                }}
              >
                <input className="input" value={text} maxLength={120} onChange={(e) => setText(e.target.value)} placeholder={p.input.placeholder ?? 'Deine Lösung'} />
                <button className="btn-primary" disabled={busy || !text.trim()}>
                  Prüfen
                </button>
              </form>
            )}
            {p.input.kind === 'choice' && (
              <div className="space-y-1.5">
                {p.input.options.map((o) => (
                  <label key={o.id} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${choice === o.id ? 'border-blood-500 bg-blood-500/10' : 'border-ink-600 hover:bg-ink-750'}`}>
                    <input type="radio" name={p.id} className="accent-blood-500" checked={choice === o.id} onChange={() => setChoice(o.id)} />
                    {o.label}
                  </label>
                ))}
                <button className="btn-primary w-full" disabled={busy || !choice} onClick={() => choice && void submit(choice)}>
                  Antwort prüfen
                </button>
              </div>
            )}
            {p.input.kind === 'order' && (
              <div className="space-y-1.5">
                {order.map((id, i) => {
                  const item = (p.input as { items: { id: string; label: string }[] }).items.find((x) => x.id === id)!;
                  const move = (d: number) =>
                    setOrder((o) => {
                      const n = [...o];
                      const j = i + d;
                      if (j < 0 || j >= n.length) return o;
                      [n[i], n[j]] = [n[j], n[i]];
                      return n;
                    });
                  return (
                    <div key={id} className="flex items-center gap-2 rounded-md border border-ink-600 bg-ink-800 px-2 py-1.5 text-sm">
                      <span className="w-5 text-center font-mono text-xs text-ink-400">{i + 1}</span>
                      <span className="flex-1">{item.label}</span>
                      <button className="btn-ghost btn-sm !px-1.5" onClick={() => move(-1)} disabled={i === 0} aria-label="Nach oben">
                        ▲
                      </button>
                      <button className="btn-ghost btn-sm !px-1.5" onClick={() => move(1)} disabled={i === order.length - 1} aria-label="Nach unten">
                        ▼
                      </button>
                    </div>
                  );
                })}
                <button className="btn-primary w-full" disabled={busy} onClick={() => void submit(order)}>
                  Reihenfolge prüfen
                </button>
              </div>
            )}
            <div className="flex items-center justify-between text-xs text-ink-400">
              <span>
                Hinweise: {p.hints.length}/{p.hintsTotal} · Versuche des Teams: {p.attempts}
              </span>
              {onHint && p.hints.length < p.hintsTotal && (
                <button className="btn-ghost btn-sm" onClick={onHint}>
                  <Icon name="bulb" /> Hinweis anfragen
                </button>
              )}
            </div>
          </div>
        )
      )}
    </div>
  );
}

/* ------------------------------ Abstimmung ------------------------------ */
export function VoteCard({ vote, myVote, onVote, clockOffset, compact = false }: { vote: PublicVote; myVote?: number | null; onVote?: (i: number) => void; clockOffset: number; compact?: boolean }) {
  const left = useCountdown(vote.status === 'open' ? vote.endsAt : undefined, clockOffset);
  const max = Math.max(1, ...vote.counts);
  return (
    <div className={`card overflow-hidden ${vote.status === 'open' ? '!border-blood-500/70' : ''}`}>
      <div className="flex items-center justify-between gap-2 border-b border-ink-700 bg-blood-800/30 px-4 py-2">
        <div className="label flex items-center gap-1.5 !text-blood-300">
          <Icon name="vote" className="h-3.5 w-3.5" /> {vote.status === 'open' ? 'Abstimmung läuft' : 'Ergebnis'}
        </div>
        {vote.status === 'open' && <div className="font-mono text-sm font-bold text-white">{left}s</div>}
      </div>
      <div className="p-4">
        <div className="mb-3 font-display text-base font-bold">{vote.question}</div>
        <div className="space-y-1.5">
          {vote.options.map((o, i) => {
            const pct = vote.total ? Math.round((vote.counts[i] / vote.total) * 100) : 0;
            const win = vote.winner === i;
            return (
              <button
                key={i}
                type="button"
                disabled={!onVote || vote.status !== 'open'}
                onClick={() => onVote?.(i)}
                className={`relative w-full overflow-hidden rounded-md border px-3 py-2 text-left text-sm transition ${
                  myVote === i ? 'border-blood-400' : win ? 'border-brass-400' : 'border-ink-600'
                } ${onVote && vote.status === 'open' ? 'hover:border-ink-400' : ''}`}
              >
                <span className={`absolute inset-y-0 left-0 ${win ? 'bg-brass-500/25' : 'bg-blood-600/25'} transition-all duration-500`} style={{ width: `${(vote.counts[i] / max) * 100}%` }} />
                <span className="relative flex items-center justify-between gap-2">
                  <span>
                    <span className="mr-2 font-mono text-xs text-ink-400">{i + 1}</span>
                    {o.label}
                    {myVote === i && <span className="ml-2 text-xs text-blood-300">(deine Stimme)</span>}
                  </span>
                  {!compact && <span className="font-mono text-xs text-ink-300">{pct}%</span>}
                </span>
              </button>
            );
          })}
        </div>
        <div className="mt-2 text-xs text-ink-400">
          {vote.total} Stimmen{vote.status === 'open' && ' · Chat: !a <Nummer>'}
          {vote.tie && ' · Gleichstand – die Spielleitung entscheidet.'}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------ Theorien ------------------------------ */
export function TheoryList({
  view,
  upvoted,
  onUpvote,
  myId,
  onModerate,
}: {
  view: PublicCaseView;
  upvoted?: string[];
  onUpvote?: (id: string) => void;
  myId?: string;
  onModerate?: (id: string, status: PublicTheory['status']) => void;
}) {
  const name = (id: string) => view.characters.find((c) => c.id === id)?.name ?? id;
  const evTitle = (id: string) => view.evidence.find((e) => e.id === id)?.title ?? view.insights.find((i) => i.id === id)?.title ?? id;
  if (view.theories.length === 0) return <Empty icon="bulb" title="Noch keine Theorien">Wer hat einen Verdacht? Theorien mit guter Begründung bringen Punkte – besonders, wenn andere sie unterstützen.</Empty>;
  return (
    <div className="space-y-2">
      {view.theories.map((t) => (
        <div key={t.id} className={`card p-3 ${t.status === 'featured' ? '!border-brass-400' : ''} ${t.status === 'hidden' ? 'opacity-50' : ''}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-xs text-ink-400">
                {t.author} verdächtigt <b className="text-blood-300">{name(t.suspectId)}</b>
                {t.status === 'featured' && <span className="ml-2 text-brass-300">★ hervorgehoben</span>}
              </div>
              <p className="mt-1 text-sm text-ink-100">{t.text}</p>
              {t.evidenceIds.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {t.evidenceIds.map((e) => (
                    <span key={e} className="chip border-ink-600 text-ink-300">
                      {evTitle(e)}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <button
              className={`btn-sm shrink-0 ${upvoted?.includes(t.id) ? 'btn-primary' : 'btn-secondary'}`}
              disabled={!onUpvote || t.authorId === myId}
              onClick={() => onUpvote?.(t.id)}
              title="Theorie unterstützen"
            >
              ▲ {t.upvotes}
            </button>
          </div>
          {onModerate && (
            <div className="mt-2 flex gap-1 border-t border-ink-700 pt-2">
              <button className="btn-ghost btn-sm" onClick={() => onModerate(t.id, t.status === 'featured' ? 'visible' : 'featured')}>
                <Icon name="star" /> {t.status === 'featured' ? 'Nicht mehr hervorheben' : 'Im Overlay zeigen'}
              </button>
              <button className="btn-ghost btn-sm" onClick={() => onModerate(t.id, t.status === 'hidden' ? 'visible' : 'hidden')}>
                <Icon name={t.status === 'hidden' ? 'eye' : 'eyeoff'} /> {t.status === 'hidden' ? 'Einblenden' : 'Ausblenden'}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function TheoryForm({ view, onSubmit }: { view: PublicCaseView; onSubmit: (suspect: string, text: string, evidence: string[]) => Promise<boolean> }) {
  const suspects = view.characters.filter((c) => c.role === 'suspect');
  const [suspect, setSuspect] = useState('');
  const [text, setText] = useState('');
  const [ev, setEv] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const options = [...view.insights.map((i) => ({ id: i.id, title: i.title })), ...view.evidence.map((e) => ({ id: e.id, title: e.title }))];
  return (
    <form
      className="card space-y-3 p-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        const ok = await onSubmit(suspect, text, ev);
        setBusy(false);
        if (ok) {
          setText('');
          setEv([]);
        }
      }}
    >
      <div className="font-display text-base font-bold">Eigene Theorie einreichen</div>
      <select className="input" value={suspect} onChange={(e) => setSuspect(e.target.value)} required>
        <option value="">Wen verdächtigst du?</option>
        {suspects.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
      <textarea className="input min-h-20" maxLength={400} value={text} onChange={(e) => setText(e.target.value)} placeholder="Begründung: Welche Beweise sprechen dafür? (min. 10 Zeichen)" required minLength={10} />
      <div>
        <div className="label mb-1">Belege (optional, max. 5)</div>
        <div className="flex max-h-28 flex-wrap gap-1 overflow-y-auto scroll-thin">
          {options.map((o) => (
            <button
              type="button"
              key={o.id}
              onClick={() => setEv((l) => (l.includes(o.id) ? l.filter((x) => x !== o.id) : l.length < 5 ? [...l, o.id] : l))}
              className={`chip ${ev.includes(o.id) ? 'border-blood-500 bg-blood-500/15 text-white' : 'border-ink-600 text-ink-300'}`}
            >
              {o.title}
            </button>
          ))}
        </div>
      </div>
      <button className="btn-primary w-full" disabled={busy || !suspect || text.trim().length < 10}>
        Theorie einreichen
      </button>
    </form>
  );
}

/* ------------------------------ Diskussion ------------------------------ */
export function Discussion({ messages, onSend, onHide, enabled }: { messages: DiscussionMessage[]; onSend?: (t: string) => Promise<boolean>; onHide?: (id: string) => void; enabled: boolean }) {
  const [text, setText] = useState('');
  const end = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => end.current?.scrollIntoView({ block: 'nearest' }), [messages.length]);
  return (
    <div className="card flex h-[420px] flex-col">
      <div className="scroll-thin flex-1 space-y-2 overflow-y-auto p-3">
        {messages.length === 0 && <div className="py-8 text-center text-sm text-ink-400">Noch keine Beiträge. Teile deine Beobachtungen mit dem Team!</div>}
        {messages.map((m) => (
          <div key={m.id} className={`group text-sm ${m.hidden ? 'opacity-40' : ''}`}>
            <span className="font-semibold text-brass-300">{m.author}</span> <span className="text-ink-200">{m.text}</span>
            {onHide && !m.hidden && (
              <button className="ml-2 hidden text-xs text-blood-300 group-hover:inline" onClick={() => onHide(m.id)}>
                ausblenden
              </button>
            )}
          </div>
        ))}
        <div ref={end} />
      </div>
      {onSend && (
        <form
          className="flex gap-2 border-t border-ink-700 p-2"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!text.trim()) return;
            if (await onSend(text.trim())) setText('');
          }}
        >
          <input className="input" value={text} maxLength={280} onChange={(e) => setText(e.target.value)} placeholder={enabled ? 'Beobachtung teilen …' : 'Diskussion deaktiviert'} disabled={!enabled} />
          <button className="btn-secondary" disabled={!enabled || !text.trim()}>
            Senden
          </button>
        </form>
      )}
    </div>
  );
}

/* ------------------------------ Feed ------------------------------ */
const FEED_ICON: Record<string, string> = {
  insight: 'bulb',
  evidence: 'doc',
  character: 'user',
  event: 'alert',
  puzzle: 'puzzle',
  hint: 'bulb',
  interrogation: 'mic',
  answer: 'chat',
  phase: 'folder',
  accusation: 'scale',
  reveal: 'star',
  vote: 'vote',
  theory: 'pin',
  system: 'clock',
};
export function Feed({ feed, limit = 30 }: { feed: FeedEntry[]; limit?: number }) {
  const items = feed.slice(-limit).reverse();
  return (
    <ul className="space-y-2">
      {items.map((f) => (
        <li key={f.id} className="flex gap-2 text-sm">
          <Icon name={FEED_ICON[f.type] ?? 'clock'} className={`mt-0.5 h-4 w-4 shrink-0 ${f.type === 'insight' || f.type === 'event' ? 'text-blood-400' : 'text-ink-400'}`} />
          <div className="min-w-0">
            <span className="mr-1 font-mono text-[11px] text-ink-500">{formatDuration(f.at)}</span>
            <span className="text-ink-200">{feedText(f)}</span>
            {f.by && <span className="text-ink-400"> · {f.by}</span>}
            {f.detail && (f.type === 'event' || f.type === 'hint' || f.type === 'answer') && <div className="mt-0.5 text-xs text-ink-400">{f.detail}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
}
export function feedText(f: FeedEntry) {
  switch (f.type) {
    case 'insight':
      return `Erkenntnis: ${f.text}`;
    case 'evidence':
      return `Neues Beweismittel: ${f.text}`;
    case 'character':
      return `Neue Person: ${f.text}`;
    case 'event':
      return `Ereignis: ${f.text}`;
    case 'puzzle':
      return `Rätsel gelöst: ${f.text}`;
    case 'phase':
      return `Phase: ${f.text}`;
    case 'vote':
      return `Abstimmung: ${f.text}`;
    default:
      return f.text;
  }
}

/* ------------------------------ Auflösung ------------------------------ */
export function SolutionView({ view }: { view: PublicCaseView }) {
  const s = view.solution;
  if (!s) return null;
  const name = (id: string) => view.characters.find((c) => c.id === id)?.name ?? id;
  const found = s.chain.filter((c) => c.found).length;
  const lastAcc = view.accusation.attempts.at(-1);
  return (
    <div className="space-y-5">
      <div className="paper relative overflow-hidden px-5 py-6 md:px-8">
        <span className="stamp animate-stamp mb-3 md:absolute md:right-4 md:top-4 md:mb-0">Fall gelöst</span>
        <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-paper-faded">Abschlussbericht</div>
        <h2 className="mt-1 font-display md:max-w-[78%] text-2xl font-bold md:text-3xl">{s.headline}</h2>
        <p className="mt-3 font-typewriter text-[15px] leading-7">{s.summary}</p>
        {lastAcc && (
          <div className={`mt-3 inline-block rounded px-2 py-1 text-sm font-bold ${lastAcc.correct ? 'bg-ok-600/20 text-ok-600' : 'bg-blood-500/15 text-blood-700'}`}>
            {lastAcc.correct ? `Die Community hat ${name(lastAcc.suspect)} richtig überführt!` : `Die Community lag zuletzt bei ${name(lastAcc.suspect)} falsch.`}
          </div>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card p-4">
          <div className="label mb-1">Motiv</div>
          <p className="text-sm text-ink-200">{s.motive}</p>
        </div>
        <div className="card p-4">
          <div className="label mb-1">Tathergang</div>
          <p className="text-sm text-ink-200">{s.method}</p>
        </div>
      </div>
      <div className="card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="font-display text-lg font-bold">Die Beweiskette</div>
          <div className="text-xs text-ink-400">
            {found}/{s.chain.length} Glieder von der Community gefunden
          </div>
        </div>
        <ol className="space-y-2">
          {s.chain.map((c, i) => (
            <li key={c.insight} className={`flex gap-3 rounded-md border p-3 ${c.found ? 'border-ok-600/50 bg-ok-600/5' : 'border-blood-600/40 bg-blood-500/5'}`}>
              <span className="font-mono text-sm font-bold text-ink-400">{i + 1}</span>
              <div>
                <div className="text-sm font-semibold">
                  {c.title} {c.found ? <span className="text-xs text-ok-400">✓ gefunden</span> : <span className="text-xs text-blood-300">– „Der Hinweis war die ganze Zeit da!“</span>}
                </div>
                <div className="text-sm text-ink-300">{c.explanation}</div>
              </div>
            </li>
          ))}
        </ol>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card p-4">
          <div className="mb-2 font-display text-lg font-bold">Was wirklich geschah</div>
          <ol className="relative ml-2 border-l-2 border-blood-700/70">
            {s.truthTimeline.map((t, i) => (
              <li key={i} className="mb-3 ml-4">
                <span className="absolute -left-[6px] mt-1.5 h-2.5 w-2.5 rounded-full bg-blood-500" />
                <span className="font-mono text-xs font-bold text-brass-300">{t.time}</span>
                <div className="text-sm text-ink-200">{t.text}</div>
              </li>
            ))}
          </ol>
        </div>
        <div className="card p-4">
          <div className="mb-2 font-display text-lg font-bold">Falsche Fährten</div>
          <ul className="space-y-2">
            {s.redHerrings.map((r, i) => (
              <li key={i} className="text-sm">
                <div className="font-semibold text-ink-100">
                  {r.character ? `${name(r.character)}: ` : ''}
                  {r.clue}
                </div>
                <div className="text-ink-300">{r.explanation}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="card p-4">
        <div className="label mb-1">Epilog</div>
        <p className="font-display text-base italic text-ink-200">{s.epilogue}</p>
      </div>
    </div>
  );
}

export function evidenceIcon(kind: string) {
  return EVIDENCE_ICON[kind] ?? 'doc';
}
