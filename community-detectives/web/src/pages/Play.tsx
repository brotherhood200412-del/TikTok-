import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { TEAMS } from '../../../shared/views';
import { EvidenceViewer, EVIDENCE_KIND_LABEL } from '../components/Evidence';
import {
  Board,
  CharacterCard,
  CharacterDetail,
  Discussion,
  Feed,
  InterrogationPanel,
  PuzzleCard,
  SolutionView,
  TheoryForm,
  TheoryList,
  Timeline,
  VoteCard,
  evidenceIcon,
  feedText,
} from '../components/Game';
import { ConnectionBanner, Empty, FullPageMessage, Icon, Logo, Modal, Progress, Spinner, useToast } from '../components/ui';
import { api, type AppConfig, type MeResponse } from '../lib/api';
import { CATEGORY_LABEL, DIFFICULTY_LABEL, GENRE_LABEL, STATUS_LABEL, formatDuration } from '../lib/format';
import { useGameClock, useLive, type ViewerState } from '../lib/live';

interface JoinInfo {
  sessionId: string;
  code: string;
  title: string;
  tagline: string;
  accent: string;
  streamer: string;
  status: string;
  allowGuests: boolean;
  guestsCanVote: boolean;
  hasGuestKey: boolean;
}

export default function Play() {
  const { code = '' } = useParams();
  const [info, setInfo] = useState<JoinInfo | null>(null);
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [guestName, setGuestName] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<JoinInfo>(`/play/${encodeURIComponent(code)}`), api<AppConfig>('/config'), api<MeResponse>('/me')])
      .then(([i, c, m]) => {
        setInfo(i);
        setCfg(c);
        setMe(m);
        const stored = safeGet(`cd_guest_name`);
        if (!m.auth?.twitchUserId && i.hasGuestKey && stored) setGuestName(stored);
      })
      .catch((e: Error) => setErr(e.message));
  }, [code]);

  if (err) return <FullPageMessage title="Ermittlung nicht gefunden">{err} Prüfe den Code im Stream.</FullPageMessage>;
  if (!info || !cfg || !me) return <FullPageMessage title="Akte wird geladen …"><Spinner /></FullPageMessage>;

  const verified = !!me.auth?.twitchUserId;
  if (!verified && !guestName) return <JoinScreen info={info} cfg={cfg} onGuest={setGuestName} />;
  return <Investigation code={info.code} guestName={verified ? undefined : guestName ?? undefined} />;
}

function safeGet(k: string) {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
}
function safeSet(k: string, v: string) {
  try {
    localStorage.setItem(k, v);
  } catch {
    /* ignore */
  }
}

function JoinScreen({ info, cfg, onGuest }: { info: JoinInfo; cfg: AppConfig; onGuest: (n: string) => void }) {
  const [name, setName] = useState(safeGet('cd_guest_name')?.replace(/ \(Gast\)$/, '') ?? '');
  const [devName, setDevName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const returnTo = `/play/${info.code}`;
  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col justify-center gap-6 px-4 py-10">
      <Logo />
      <div className="paper relative px-6 py-7">
        <span className="stamp mb-2 text-xs md:absolute md:right-4 md:top-4 md:mb-0">Akte offen</span>
        <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-paper-faded">Einladung von {info.streamer}</div>
        <h1 className="mt-2 font-display text-3xl font-bold">{info.title}</h1>
        <p className="mt-2 font-typewriter text-paper-ink">{info.tagline}</p>
        <div className="mt-3 text-xs text-paper-faded">Code: {info.code} · Status: {STATUS_LABEL[info.status]}</div>
      </div>
      <div className="card space-y-4 p-5">
        <h2 className="font-display text-lg font-bold">Dem Ermittlerteam beitreten</h2>
        {cfg.twitchEnabled && (
          <a className="btn w-full bg-[#9146ff] text-white hover:bg-[#a970ff]" href={`/api/auth/twitch/login?role=viewer&return=${encodeURIComponent(returnTo)}`}>
            <Icon name="twitch" /> Mit Twitch anmelden
          </a>
        )}
        {cfg.twitchEnabled && <p className="-mt-2 text-xs text-ink-400">Mit Twitch-Login werden deine Punkte aus Chat und Webseite zusammengeführt. Wir lesen nur deinen Namen – keine weiteren Rechte.</p>}
        {cfg.devLogin && (
          <form
            className="space-y-2 rounded-lg border border-dashed border-brass-500/50 p-3"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await api('/auth/dev/login', { body: { login: devName, role: 'viewer' } });
                location.reload();
              } catch (er) {
                setError((er as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="label !text-brass-300">Lokale Entwicklung: als verifizierter Zuschauer</div>
            <div className="flex gap-2">
              <input className="input" placeholder="twitch_name" value={devName} onChange={(e) => setDevName(e.target.value)} />
              <button className="btn-secondary" disabled={busy || devName.length < 3}>
                Anmelden
              </button>
            </div>
          </form>
        )}
        {info.allowGuests ? (
          <form
            className="space-y-2"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError(null);
              try {
                const r = await api<{ name: string }>(`/play/${info.code}/guest`, { body: { name } });
                safeSet('cd_guest_name', r.name);
                onGuest(r.name);
              } catch (er) {
                setError((er as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="label">Oder als Gast</div>
            <div className="flex gap-2">
              <input className="input" placeholder="Dein Ermittlername" maxLength={24} value={name} onChange={(e) => setName(e.target.value)} />
              <button className="btn-primary" disabled={busy || name.trim().length < 2}>
                Beitreten
              </button>
            </div>
            {!info.guestsCanVote && <p className="text-xs text-ink-400">Hinweis: Abstimmen ist in dieser Ermittlung nur mit Twitch-Login möglich.</p>}
          </form>
        ) : (
          <p className="text-sm text-ink-400">Diese Ermittlung erlaubt nur Twitch-Anmeldungen.</p>
        )}
        {error && <div className="rounded-md border border-blood-600 bg-blood-800/40 px-3 py-2 text-sm">{error}</div>}
      </div>
    </div>
  );
}

type Tab = 'akte' | 'beweise' | 'personen' | 'board' | 'raetsel' | 'theorien' | 'team';
const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'akte', label: 'Akte', icon: 'folder' },
  { id: 'beweise', label: 'Beweise', icon: 'doc' },
  { id: 'personen', label: 'Personen', icon: 'users' },
  { id: 'board', label: 'Board', icon: 'link' },
  { id: 'raetsel', label: 'Rätsel', icon: 'puzzle' },
  { id: 'theorien', label: 'Theorien', icon: 'bulb' },
  { id: 'team', label: 'Team', icon: 'trophy' },
];

function Investigation({ code, guestName }: { code: string; guestName?: string }) {
  const hs = useMemo(() => ({ mode: 'viewer' as const, code, guestName }), [code, guestName]);
  const live = useLive<ViewerState>(hs);
  const { state: view, me } = live;
  const toast = useToast();
  const [tab, setTab] = useState<Tab>('akte');
  const [openEvidence, setOpenEvidence] = useState<string | null>(null);
  const [openChar, setOpenChar] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const lastFeed = useRef<number | null>(null);
  const elapsed = useGameClock(view?.elapsedMs ?? 0, view?.runningSince ?? null, live.clockOffset);
  const insightMap = useMemo(() => new Map((view?.insights ?? []).map((i) => [i.id, i])), [view?.insights]);
  const [seenEvidence, setSeenEvidence] = useState<Set<string>>(() => new Set(JSON.parse(safeGet(`cd_seen_${code}`) ?? '[]')));

  // Entdeckungen als Toast anzeigen
  useEffect(() => {
    if (!view) return;
    const max = view.feed.at(-1)?.id ?? 0;
    if (lastFeed.current !== null) {
      for (const f of view.feed.filter((x) => x.id > lastFeed.current!)) {
        if (['insight', 'evidence', 'event', 'puzzle', 'character', 'accusation', 'phase'].includes(f.type)) {
          toast({ tone: 'discovery', title: f.by ? `Entdeckt von ${f.by}` : 'Neu in der Akte', text: feedText(f) });
        }
      }
    }
    lastFeed.current = max;
  }, [view?.feed, toast]);

  if (live.status === 'fatal') {
    return (
      <FullPageMessage title="Verbindung nicht möglich">
        {live.error?.message}
        <div className="mt-4">
          <button
            className="btn-secondary"
            onClick={() => {
              try {
                localStorage.removeItem('cd_guest_name');
              } catch {
                /* ignore */
              }
              location.reload();
            }}
          >
            Erneut versuchen
          </button>
        </div>
      </FullPageMessage>
    );
  }
  if (!view) return <FullPageMessage title="Verbinde mit der Ermittlung …"><Spinner /></FullPageMessage>;

  const playable = view.status === 'active' || view.status === 'finale';
  const result = async (p: Promise<{ ok: boolean; message?: string; code?: string }>, successTone: 'success' | 'discovery' = 'success') => {
    setBusy(true);
    const r = await p;
    setBusy(false);
    if (r.message) toast({ tone: r.ok ? (r.code === 'known' ? 'info' : successTone) : r.code === 'miss' || r.code === 'wrong' ? 'info' : 'error', text: r.message });
    return r.ok;
  };
  const ev = view.evidence.find((e) => e.id === openEvidence);
  const ch = view.characters.find((c) => c.id === openChar);
  const unseen = view.evidence.filter((e) => !seenEvidence.has(e.id)).length;

  return (
    <div className="min-h-dvh pb-24 md:pb-8" style={{ ['--case-accent' as string]: view.case.accent }}>
      <ConnectionBanner status={live.status} error={live.error} />
      {/* Kopfzeile */}
      <header className="sticky top-0 z-30 border-b border-ink-700/80 bg-ink-900/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
          <Logo compact />
          <div className="min-w-0 flex-1">
            <div className="truncate font-display text-base font-bold leading-tight">{view.case.title}</div>
            <div className="flex items-center gap-2 text-[11px] text-ink-400">
              <span className={`h-1.5 w-1.5 rounded-full ${view.status === 'active' ? 'bg-ok-400' : view.status === 'paused' ? 'bg-brass-400' : 'bg-blood-400'}`} />
              {STATUS_LABEL[view.status]} · {formatDuration(elapsed)} · {view.participants} Ermittelnde
            </div>
          </div>
          {me && (
            <div className="text-right">
              <div className="font-mono text-sm font-bold text-brass-300">{me.points} P</div>
              <div className="max-w-28 truncate text-[11px] text-ink-400">
                {me.rank ? `#${me.rank} · ` : ''}
                {me.displayName}
              </div>
            </div>
          )}
        </div>
        <nav className="mx-auto hidden max-w-6xl gap-1 px-4 pb-2 md:flex">
          {TABS.map((t) => (
            <button key={t.id} className={`btn-sm ${tab === t.id ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setTab(t.id)}>
              <Icon name={t.icon} /> {t.label}
              {t.id === 'beweise' && unseen > 0 && <span className="rounded-full bg-blood-500 px-1.5 text-[10px] text-white">{unseen}</span>}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-6xl space-y-4 px-4 py-4">
        {/* Aufgabe & Phase */}
        {view.status !== 'revealed' && view.status !== 'ended' && (
          <div className="card flex flex-col gap-2 p-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="label !text-blood-300">
                {view.status === 'finale' ? 'Finale' : `Phase ${view.phaseIndex + 1}/${view.phases.length}: ${view.phases[view.phaseIndex]?.title}`}
              </div>
              <div className="mt-0.5 font-display text-lg font-bold">{view.task ?? view.phases[view.phaseIndex]?.goal}</div>
              {view.status === 'lobby' && <div className="mt-1 text-sm text-ink-400">Die Ermittlung startet gleich. Lies schon einmal die Akte!</div>}
              {view.status === 'paused' && <div className="mt-1 text-sm text-brass-300">Die Spielleitung hat pausiert.</div>}
            </div>
            <div className="min-w-48">
              <div className="mb-1 flex justify-between text-xs text-ink-400">
                <span>Ermittlungsfortschritt</span>
                <span>
                  {view.progress.insights}/{view.progress.insightsTotal}
                </span>
              </div>
              <Progress value={view.progress.insights} max={view.progress.insightsTotal} />
            </div>
          </div>
        )}

        {view.vote && !view.solution && (
          <VoteCard
            vote={view.vote}
            myVote={me?.myVote}
            clockOffset={live.clockOffset}
            onVote={(i) => void result(live.act('vote', { option: i }))}
          />
        )}
        {view.interrogation && tab !== 'personen' && <InterrogationPanel view={view} />}
        {view.solution && <SolutionView view={view} />}

        {tab === 'akte' && (
          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="space-y-4">
              <div className="paper relative px-5 py-6 md:px-7">
                <span className="stamp mb-2 text-xs md:absolute md:right-4 md:top-4 md:mb-0">{GENRE_LABEL[view.case.genre]}</span>
                <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-paper-faded">
                  {view.case.briefing.location} · {view.case.briefing.date}
                </div>
                <h1 className="mt-1 max-w-[80%] font-display text-2xl font-bold">{view.case.title}</h1>
                <div className="mt-1 text-xs text-paper-faded">Schwierigkeit: {DIFFICULTY_LABEL[view.case.difficulty]}</div>
                <div className="mt-3 space-y-3 font-typewriter text-[15px] leading-7">
                  {view.case.briefing.intro.split('\n').filter(Boolean).map((p, i) => (
                    <p key={i}>{p}</p>
                  ))}
                </div>
                <div className="mt-4 border-t border-paper-faded/30 pt-3 text-sm">
                  <b>Auftrag:</b> {view.case.briefing.objective}
                </div>
              </div>
              {view.events.length > 0 && (
                <div className="space-y-2">
                  {view.events.map((e) => (
                    <div key={e.id} className="card border-l-4 !border-l-blood-500 p-4">
                      <div className="label">{e.source}</div>
                      <div className="font-display text-base font-bold">{e.title}</div>
                      <p className="mt-1 text-sm text-ink-200">{e.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-4">
              <div className="card p-4">
                <div className="mb-3 font-display text-base font-bold">Rekonstruierte Zeitlinie</div>
                <Timeline view={view} />
              </div>
              <div className="card p-4">
                <div className="mb-3 font-display text-base font-bold">Ermittlungsprotokoll</div>
                <Feed feed={view.feed} limit={15} />
              </div>
            </div>
          </div>
        )}

        {tab === 'beweise' && (
          <div>
            <p className="mb-3 text-sm text-ink-400">Öffne Beweise, untersuche Details und markiere, was dir verdächtig vorkommt. Richtige Funde werden für das ganze Team gesichert.</p>
            {view.evidence.length === 0 ? (
              <Empty title="Noch keine Beweise" />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {[...view.evidence].reverse().map((e) => {
                  const nFound = Object.keys(e.found).length;
                  return (
                    <button
                      key={e.id}
                      className="card group p-4 text-left transition hover:border-ink-500"
                      onClick={() => {
                        setOpenEvidence(e.id);
                        setSeenEvidence((s) => {
                          const n = new Set(s).add(e.id);
                          safeSet(`cd_seen_${code}`, JSON.stringify([...n]));
                          return n;
                        });
                      }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="flex h-9 w-9 items-center justify-center rounded-md bg-paper-100 text-paper-ink">
                          <Icon name={evidenceIcon(e.content.kind)} />
                        </span>
                        {!seenEvidence.has(e.id) && <span className="chip border-blood-500 bg-blood-500/15 text-blood-300">Neu</span>}
                      </div>
                      <div className="mt-2 font-display text-base font-bold">{e.title}</div>
                      <div className="mt-0.5 line-clamp-2 text-sm text-ink-400">{e.summary}</div>
                      <div className="mt-2 text-[11px] text-ink-500">
                        {EVIDENCE_KIND_LABEL[e.content.kind]} · {nFound > 0 ? `${nFound} Detail(s) gesichert` : 'unberührt'}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {tab === 'personen' && (
          <div className="space-y-4">
            {view.interrogation && <InterrogationPanel view={view} />}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {view.characters.map((c) => (
                <CharacterCard key={c.id} c={c} onClick={() => setOpenChar(c.id)} active={view.interrogation?.character === c.id} />
              ))}
            </div>
          </div>
        )}

        {tab === 'board' && (
          <div className="space-y-4">
            <Board
              view={view}
              onConnect={playable ? async (a, b) => void (await result(live.act('connect', { a, b }), 'discovery')) : undefined}
              onOpen={(it) => (it.kind === 'evidence' ? setOpenEvidence(it.id) : it.kind === 'character' ? setOpenChar(it.id) : undefined)}
            />
            <div className="grid gap-3 md:grid-cols-2">
              {view.insights.map((i) => (
                <div key={i.id} className="card p-3">
                  <div className="label">{CATEGORY_LABEL[i.category]}</div>
                  <div className="font-semibold">{i.title}</div>
                  <p className="text-sm text-ink-300">{i.text}</p>
                  {i.by && <div className="mt-1 text-[11px] text-ink-500">gefunden von {i.by}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'raetsel' && (
          <div className="grid gap-4 md:grid-cols-2">
            {view.puzzles.length === 0 && <Empty icon="puzzle" title="Noch keine Rätsel">Rätsel tauchen auf, sobald die Ermittlung sie hergibt.</Empty>}
            {view.puzzles.map((p) => (
              <PuzzleCard
                key={p.id}
                p={p}
                focused={view.spotlight?.type === 'puzzle' && view.spotlight.id === p.id}
                evidenceTitle={(id) => view.evidence.find((e) => e.id === id)?.title ?? id}
                onAnswer={playable ? (a) => result(live.act('answer', { puzzle: p.id, answer: a }), 'discovery') : undefined}
                onHint={playable ? () => void result(live.act('hint')) : undefined}
              />
            ))}
          </div>
        )}

        {tab === 'theorien' && (
          <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
            {view.settings.theories && playable ? (
              <TheoryForm view={view} onSubmit={(suspect, text, evidence) => result(live.act('theory', { suspect, text, evidence }))} />
            ) : (
              <div className="card p-4 text-sm text-ink-400">Theorien können gerade nicht eingereicht werden.</div>
            )}
            <TheoryList view={view} upvoted={me?.upvoted} myId={me?.participantId} onUpvote={(id) => void result(live.act('upvote', { theory: id }))} onModerate={me?.moderator ? (id, status) => void result(live.mod('theoryStatus', { theory: id, status })) : undefined} />
          </div>
        )}

        {tab === 'team' && (
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="card p-4">
              <div className="mb-3 font-display text-base font-bold">Dein Team</div>
              <div className="space-y-2">
                {TEAMS.map((t) => {
                  const stats = view.teams.find((x) => x.id === t.id);
                  return (
                    <button key={t.id} className={`w-full rounded-lg border p-3 text-left ${me?.team === t.id ? 'border-blood-500 bg-blood-500/10' : 'border-ink-600 hover:bg-ink-750'}`} onClick={() => void result(live.act('team', { team: t.id }))}>
                      <div className="flex justify-between">
                        <span className="font-semibold">{t.label}</span>
                        <span className="font-mono text-xs text-ink-400">
                          {stats?.points ?? 0} P · {stats?.members ?? 0}
                        </span>
                      </div>
                      <div className="text-xs text-ink-400">Schwerpunkt: {t.focus}</div>
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="card p-4">
              <div className="mb-3 font-display text-base font-bold">Ermittler-Rangliste</div>
              {view.leaderboard.length === 0 ? (
                <div className="text-sm text-ink-400">Noch keine Punkte vergeben.</div>
              ) : (
                <ol className="space-y-1.5">
                  {view.leaderboard.map((l, i) => (
                    <li key={l.id} className={`flex items-center justify-between rounded-md px-2 py-1.5 text-sm ${l.id === me?.participantId ? 'bg-blood-500/15' : ''}`}>
                      <span>
                        <span className="mr-2 font-mono text-xs text-ink-500">{i + 1}.</span>
                        {l.name}
                      </span>
                      <span className="font-mono text-brass-300">{l.points}</span>
                    </li>
                  ))}
                </ol>
              )}
              <p className="mt-3 text-xs text-ink-500">Punkte gibt es für gesicherte Details, Verbindungen, gelöste Rätsel, Abstimmungen und Theorien, die andere überzeugen.</p>
            </div>
            <div>
              <div className="mb-2 font-display text-base font-bold">Diskussion</div>
              <Discussion
                messages={view.discussion}
                enabled={view.settings.discussion}
                onSend={(t) => result(live.act('message', { text: t }))}
                onHide={me?.moderator ? (id) => void result(live.mod('hideMessage', { message: id })) : undefined}
              />
            </div>
          </div>
        )}
      </main>

      {/* Mobile Navigation */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-7 border-t border-ink-700 bg-ink-900/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {TABS.map((t) => (
          <button key={t.id} className={`relative flex flex-col items-center gap-0.5 py-2 text-[10px] ${tab === t.id ? 'text-blood-300' : 'text-ink-400'}`} onClick={() => setTab(t.id)}>
            <Icon name={t.icon} className="h-5 w-5" />
            {t.label}
            {t.id === 'beweise' && unseen > 0 && <span className="absolute right-2 top-1 h-2 w-2 rounded-full bg-blood-500" />}
          </button>
        ))}
      </nav>

      <Modal open={!!ev} onClose={() => setOpenEvidence(null)} title={ev?.title} wide>
        {ev && <EvidenceViewer evidence={ev} insights={insightMap} busy={busy} onMark={playable ? (item) => void result(live.act('mark', { evidence: ev.id, item }), 'discovery') : undefined} />}
      </Modal>
      <Modal open={!!ch} onClose={() => setOpenChar(null)} title={ch?.name}>
        {ch && <CharacterDetail c={ch} log={view.interrogationLog} />}
      </Modal>
    </div>
  );
}
