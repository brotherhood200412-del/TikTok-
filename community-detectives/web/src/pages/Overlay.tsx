import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import type { FeedEntry, OverlayView } from '../../../shared/views';
import { feedText } from '../components/Game';
import { Avatar } from '../components/ui';
import { MOOD_LABEL, formatDuration } from '../lib/format';
import { useCountdown, useGameClock, useLive } from '../lib/live';

/** OBS-Browserquelle: 1920×1080, transparenter Hintergrund. */
export default function Overlay() {
  const { token = '' } = useParams();
  const hs = useMemo(() => ({ mode: 'overlay' as const, overlayToken: token }), [token]);
  const live = useLive(hs);
  useEffect(() => {
    document.body.classList.add('overlay-mode');
    return () => document.body.classList.remove('overlay-mode');
  }, []);
  const o = live.overlay;
  if (live.status === 'fatal') return <div className="p-6 font-sans text-xl text-white">Overlay: {live.error?.message}</div>;
  if (!o) return null;
  return <OverlayScene o={o} clockOffset={live.clockOffset} online={live.status === 'online'} />;
}

function OverlayScene({ o, clockOffset, online }: { o: OverlayView; clockOffset: number; online: boolean }) {
  const elapsed = useGameClock(o.elapsedMs, o.runningSince, clockOffset);
  const left = o.display.position === 'left';
  const toasts = useFeedToasts(o.feed);
  if (o.solution) return <RevealScreen o={o} />;
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden font-sans text-ink-100" style={{ fontSize: `${16 * o.display.scale}px` }}>
      <div className={`absolute top-[2.2em] flex w-[24em] flex-col gap-[0.8em] ${left ? 'left-[2.2em]' : 'right-[2.2em]'}`}>
        {/* Fallkopf */}
        <div className="overflow-hidden rounded-[0.8em] border border-white/10 bg-ink-950/85 shadow-2xl backdrop-blur">
          <div className="h-[0.25em]" style={{ background: `linear-gradient(90deg, ${o.accent}, #b3262e)` }} />
          <div className="px-[1.1em] py-[0.9em]">
            <div className="flex items-center justify-between text-[0.7em] font-semibold uppercase tracking-[0.18em] text-ink-300">
              <span>Community Detectives</span>
              <span className="flex items-center gap-[0.4em]">
                <span className={`h-[0.55em] w-[0.55em] rounded-full ${o.status === 'active' ? 'animate-pulse bg-blood-400' : 'bg-brass-400'}`} />
                {o.status === 'paused' ? 'Pause' : o.status === 'lobby' ? 'Gleich geht’s los' : o.status === 'finale' ? 'Finale' : 'Live-Ermittlung'}
                {!online && ' · offline'}
              </span>
            </div>
            <div className="mt-[0.2em] font-display text-[1.55em] font-bold leading-tight">{o.title}</div>
            <div className="mt-[0.5em] flex items-center justify-between text-[0.8em]">
              <span className="text-brass-300">
                {o.phase} {o.status !== 'finale' && `· ${o.phaseIndex + 1}/${o.phasesTotal}`}
              </span>
              <span className="font-mono">{formatDuration(elapsed)}</span>
            </div>
            <div className="mt-[0.5em] h-[0.3em] overflow-hidden rounded bg-white/10">
              <div className="h-full bg-gradient-to-r from-blood-600 to-blood-400 transition-all duration-1000" style={{ width: `${(o.progress.insights / Math.max(1, o.progress.insightsTotal)) * 100}%` }} />
            </div>
            {o.task && <div className="mt-[0.7em] border-l-[0.2em] border-blood-500 pl-[0.6em] text-[0.95em] leading-snug">{o.task}</div>}
          </div>
        </div>

        {o.vote && <OverlayVote o={o} clockOffset={clockOffset} />}
        {o.spotlight && <Spotlight o={o} />}
        {o.featuredTheory && !o.vote && (
          <div className="rounded-[0.8em] border border-brass-400/50 bg-ink-950/85 px-[1.1em] py-[0.8em] shadow-2xl">
            <div className="text-[0.65em] font-semibold uppercase tracking-[0.18em] text-brass-300">Theorie der Community · {o.featuredTheory.author}</div>
            <div className="mt-[0.3em] text-[0.95em]">{o.featuredTheory.text}</div>
            <div className="mt-[0.3em] text-[0.75em] text-ink-400">▲ {o.featuredTheory.upvotes} Unterstützer</div>
          </div>
        )}
        {o.display.showLeaderboard && o.leaderboard.length > 0 && !o.vote && (
          <div className="rounded-[0.8em] border border-white/10 bg-ink-950/80 px-[1.1em] py-[0.7em]">
            <div className="text-[0.65em] font-semibold uppercase tracking-[0.18em] text-ink-300">Top-Ermittler</div>
            {o.leaderboard.slice(0, 5).map((l, i) => (
              <div key={l.id} className="mt-[0.25em] flex justify-between text-[0.85em]">
                <span>
                  <span className="mr-[0.5em] font-mono text-ink-400">{i + 1}</span>
                  {l.name}
                </span>
                <span className="font-mono text-brass-300">{l.points}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {o.display.showJoin && (
        <div className={`absolute bottom-[2.2em] ${left ? 'left-[2.2em]' : 'right-[2.2em]'} flex items-center gap-[0.8em] rounded-[0.8em] border border-white/10 bg-ink-950/85 px-[1em] py-[0.6em] shadow-2xl`}>
          <div className="text-[0.75em] leading-tight text-ink-300">
            Mitermitteln: <b className="text-ink-100">{o.joinUrl.replace(/^https?:\/\//, '')}</b>
            <br />
            oder im Chat <b className="text-ink-100">!ermitteln</b> · {o.participants} dabei
          </div>
          <div className="rounded-[0.4em] bg-paper-100 px-[0.6em] py-[0.2em] font-mono text-[1.3em] font-bold tracking-[0.2em] text-paper-ink">{o.joinCode}</div>
        </div>
      )}

      {o.display.showFeed && (
        <div className={`absolute bottom-[2.2em] flex w-[26em] flex-col gap-[0.5em] ${left ? 'right-[2.2em] items-end' : 'left-[2.2em] items-start'}`}>
          {toasts.map((t) => (
            <div key={t.id} className="animate-fade-up rounded-[0.6em] border border-brass-400/40 bg-ink-950/90 px-[1em] py-[0.6em] shadow-2xl">
              <div className="text-[0.62em] font-semibold uppercase tracking-[0.18em] text-brass-300">{t.by ? `Entdeckt von ${t.by}` : 'Neu in der Akte'}</div>
              <div className="text-[0.95em] font-semibold">{feedText(t)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function useFeedToasts(feed: FeedEntry[]) {
  const [shown, setShown] = useState<FeedEntry[]>([]);
  const last = useRef<number | null>(null);
  useEffect(() => {
    const max = feed.at(-1)?.id ?? 0;
    if (last.current !== null) {
      const fresh = feed.filter((f) => f.id > last.current!);
      if (fresh.length) {
        setShown((s) => [...s, ...fresh].slice(-3));
        for (const f of fresh) setTimeout(() => setShown((s) => s.filter((x) => x.id !== f.id)), 9000);
      }
    }
    last.current = max;
  }, [feed]);
  return shown;
}

function OverlayVote({ o, clockOffset }: { o: OverlayView; clockOffset: number }) {
  const v = o.vote!;
  const left = useCountdown(v.status === 'open' ? v.endsAt : undefined, clockOffset);
  const max = Math.max(1, ...v.counts);
  return (
    <div className="rounded-[0.8em] border border-blood-500/70 bg-ink-950/90 px-[1.1em] py-[0.9em] shadow-2xl">
      <div className="flex items-center justify-between text-[0.65em] font-semibold uppercase tracking-[0.18em] text-blood-300">
        <span>{v.status === 'open' ? 'Abstimmung · !a <Nr>' : 'Ergebnis'}</span>
        {v.status === 'open' && <span className="font-mono text-[1.4em] text-white">{left}s</span>}
      </div>
      <div className="mt-[0.3em] font-display text-[1.1em] font-bold leading-snug">{v.question}</div>
      <div className="mt-[0.6em] space-y-[0.35em]">
        {v.options.map((opt, i) => (
          <div key={i} className={`relative overflow-hidden rounded-[0.4em] border px-[0.7em] py-[0.35em] text-[0.88em] ${v.winner === i ? 'border-brass-400' : 'border-white/10'}`}>
            <div className={`absolute inset-y-0 left-0 transition-all duration-500 ${v.winner === i ? 'bg-brass-500/35' : 'bg-blood-600/40'}`} style={{ width: `${(v.counts[i] / max) * 100}%` }} />
            <div className="relative flex justify-between">
              <span>
                <b className="mr-[0.5em] font-mono">{i + 1}</b>
                {opt.label}
              </span>
              <span className="font-mono">{v.counts[i]}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-[0.4em] text-[0.7em] text-ink-400">{v.total} Stimmen</div>
    </div>
  );
}

function Spotlight({ o }: { o: OverlayView }) {
  const s = o.spotlight!;
  return (
    <div className="animate-fade-up overflow-hidden rounded-[0.8em] border border-white/10 bg-ink-950/90 shadow-2xl">
      {s.type === 'character' ? (
        <div className="px-[1.1em] py-[0.9em]">
          <div className="flex items-center gap-[0.8em]">
            <Avatar name={s.name} color={s.color} size={52 * o.display.scale} stress={s.stress} />
            <div>
              <div className="text-[0.65em] font-semibold uppercase tracking-[0.18em] text-blood-300">Vernehmung</div>
              <div className="font-display text-[1.25em] font-bold">{s.name}</div>
              <div className="text-[0.75em] text-ink-400">{s.occupation}</div>
            </div>
          </div>
          {s.last && (
            <div className="mt-[0.7em]">
              <div className="text-[0.85em] font-semibold">„{s.last.question}“</div>
              <div className="mt-[0.3em] text-[0.88em] leading-snug text-ink-200">
                <span className="italic text-brass-300">({MOOD_LABEL[s.last.mood]})</span> {s.last.answer}
              </div>
            </div>
          )}
          <div className="mt-[0.6em] flex items-center gap-[0.5em] text-[0.65em] text-ink-400">
            Anspannung
            <div className="h-[0.35em] flex-1 overflow-hidden rounded bg-white/10">
              <div className={`h-full ${s.stress > 60 ? 'bg-blood-400' : 'bg-brass-400'}`} style={{ width: `${s.stress}%` }} />
            </div>
          </div>
        </div>
      ) : (
        <div className="paper m-[0.5em] px-[1em] py-[0.8em]">
          <div className="text-[0.62em] font-bold uppercase tracking-[0.2em] text-paper-faded">{s.type === 'evidence' ? 'Beweismittel im Fokus' : s.type === 'insight' ? 'Erkenntnis' : s.solved ? 'Rätsel – gelöst' : 'Rätsel im Fokus'}</div>
          <div className="font-display text-[1.2em] font-bold">{s.title}</div>
          <div className="mt-[0.2em] font-typewriter text-[0.88em] leading-snug">{s.type === 'evidence' ? s.summary : s.type === 'insight' ? s.text : s.prompt}</div>
        </div>
      )}
    </div>
  );
}

function RevealScreen({ o }: { o: OverlayView }) {
  const s = o.solution!;
  return (
    <div className="pointer-events-none fixed inset-0 flex items-center justify-center bg-black/55" style={{ fontSize: `${16 * o.display.scale}px` }}>
      <div className="paper relative w-[46em] max-w-[92vw] animate-fade-up px-[2.5em] py-[2em]">
        <span className="stamp animate-stamp absolute right-[1.5em] top-[1.5em] !text-[1em]">Fall gelöst</span>
        <div className="text-[0.75em] font-bold uppercase tracking-[0.25em] text-paper-faded">{o.title} · Auflösung</div>
        <div className="mt-[0.4em] font-display text-[2.4em] font-bold leading-tight">{s.culpritName}</div>
        <div className="mt-[0.3em] font-display text-[1.1em] italic">{s.headline}</div>
        <p className="mt-[0.9em] font-typewriter text-[1em] leading-relaxed">{s.summary}</p>
        {s.correct !== null && (
          <div className={`mt-[1em] inline-block rounded px-[0.8em] py-[0.3em] text-[1em] font-bold ${s.correct ? 'bg-ok-600/20 text-ok-600' : 'bg-blood-500/15 text-blood-700'}`}>
            {s.correct ? 'Die Community hat den Fall gelöst!' : 'Diesmal hat der Täter die Community getäuscht.'}
          </div>
        )}
        {o.leaderboard.length > 0 && (
          <div className="mt-[1.2em] border-t border-paper-faded/30 pt-[0.8em] text-[0.9em]">
            <b>Beste Ermittler:</b> {o.leaderboard.slice(0, 3).map((l) => `${l.name} (${l.points})`).join(' · ')}
          </div>
        )}
      </div>
    </div>
  );
}
