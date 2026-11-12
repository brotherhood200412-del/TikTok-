import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CopyField, DifficultyBadge, Empty, FullPageMessage, GenreBadge, Icon, Logo, Modal, Section, Spinner, Toggle, useToast } from '../components/ui';
import { api, type MeResponse } from '../lib/api';
import { DIFFICULTY_LABEL, STATUS_LABEL, formatDuration } from '../lib/format';

interface LibraryCase {
  id: string;
  title: string;
  tagline: string;
  genre: string;
  difficulty: string;
  tier: 'free' | 'creator' | 'premium';
  estimatedMinutes: number;
  accent: string;
  exclusive: boolean;
  eventTag: string | null;
  series: { title: string; part: number } | null;
  stats: { suspects: number; evidence: number; puzzles: number };
  playable: boolean;
  lockedReason: string | null;
  playedByMe: number;
  lastPlayedAt: string | null;
  globalPlays: number;
}
interface SessionRow {
  id: string;
  title: string;
  difficulty: string;
  status: string;
  joinCode: string;
  participants: number;
  createdAt: string;
  solved: boolean;
}

const PLAN_LABEL = { free: 'Free', creator: 'Creator', premium: 'Premium' };

export default function Dashboard() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [lib, setLib] = useState<LibraryCase[]>([]);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [community, setCommunity] = useState<{ name: string; points: number; cases: number }[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [start, setStart] = useState<LibraryCase | null>(null);
  const [results, setResults] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();
  const toast = useToast();

  const load = useCallback(async () => {
    const m = await api<MeResponse>('/me');
    setMe(m);
    if (m.auth?.kind !== 'streamer') return;
    const [l, s, c] = await Promise.all([api<{ cases: LibraryCase[] }>('/library'), api<{ sessions: SessionRow[] }>('/sessions'), api<{ entries: { name: string; points: number; cases: number }[] }>('/community/leaderboard')]);
    setLib(l.cases);
    setSessions(s.sessions);
    setCommunity(c.entries);
  }, []);
  useEffect(() => {
    load()
      .catch((e) => toast({ tone: 'error', text: e.message }))
      .finally(() => setLoading(false));
  }, [load, toast]);

  if (loading) return <FullPageMessage title="Dashboard lädt …"><Spinner /></FullPageMessage>;
  if (!me?.streamer) {
    return (
      <FullPageMessage title="Bitte anmelden">
        Das Dashboard ist nur für Streamer. <Link to="/" className="text-blood-300 underline">Zur Anmeldung</Link>
      </FullPageMessage>
    );
  }
  const st = me.streamer;
  const shown = lib.filter((c) => filter === 'all' || c.difficulty === filter);

  return (
    <div className="min-h-dvh">
      <header className="border-b border-ink-700 bg-ink-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <Link to="/">
            <Logo />
          </Link>
          <div className="flex-1" />
          {st.isAdmin && (
            <Link to="/admin" className="btn-ghost btn-sm">
              <Icon name="shield" /> Fallverwaltung
            </Link>
          )}
          <div className="text-right">
            <div className="text-sm font-semibold">{st.displayName}</div>
            <div className="text-[11px] text-ink-400">Plan: {PLAN_LABEL[st.plan]}</div>
          </div>
          <button
            className="btn-ghost btn-sm"
            onClick={async () => {
              await api('/auth/logout', { body: {} });
              nav('/');
            }}
            title="Abmelden"
          >
            <Icon name="logout" />
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6">
        {st.activeSessionId && (
          <div className="card flex flex-col gap-3 border-blood-500/70 p-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="label !text-blood-300">Laufende Ermittlung</div>
              <div className="font-display text-xl font-bold">{sessions.find((s) => s.id === st.activeSessionId)?.title ?? 'Ermittlung'}</div>
            </div>
            <Link to={`/control/${st.activeSessionId}`} className="btn-primary">
              <Icon name="play" /> Zum Kontrollzentrum
            </Link>
          </div>
        )}

        <Section
          title="Fallbibliothek"
          icon="folder"
          action={
            <AssignButton
              disabled={!!st.activeSessionId}
              onPick={(c) => {
                const found = lib.find((x) => x.id === c.id);
                if (found) setStart(found);
              }}
            />
          }
        >
          <div className="mb-4 flex flex-wrap gap-1">
            {['all', 'einsteiger', 'fortgeschritten', 'experte', 'meisterdetektiv'].map((d) => (
              <button key={d} className={`btn-sm ${filter === d ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setFilter(d)}>
                {d === 'all' ? 'Alle' : DIFFICULTY_LABEL[d]}
              </button>
            ))}
          </div>
          {shown.length === 0 ? (
            <Empty title="Keine Fälle">Importiere Fälle mit „npm run cases:import“.</Empty>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {shown.map((c) => (
                <article key={c.id} className={`card relative flex flex-col overflow-hidden ${c.playable ? '' : 'opacity-70'}`}>
                  <div className="h-1.5" style={{ background: `linear-gradient(90deg, ${c.accent}, #b3262e)` }} />
                  <div className="flex flex-1 flex-col p-4">
                    <div className="flex flex-wrap gap-1.5">
                      <DifficultyBadge difficulty={c.difficulty} />
                      <GenreBadge genre={c.genre} />
                      {c.tier !== 'free' && <span className="chip border-brass-500 text-brass-300">{PLAN_LABEL[c.tier]}</span>}
                      {c.exclusive && <span className="chip border-blood-500 text-blood-300">Exklusiv</span>}
                    </div>
                    <h3 className="mt-3 font-display text-xl font-bold">{c.title}</h3>
                    <p className="mt-1 flex-1 text-sm text-ink-300">{c.tagline}</p>
                    <div className="mt-3 grid grid-cols-4 gap-1 text-center text-[11px] text-ink-400">
                      <div className="rounded bg-ink-900 py-1">
                        <b className="block text-sm text-ink-100">{c.stats.suspects}</b>Verdächtige
                      </div>
                      <div className="rounded bg-ink-900 py-1">
                        <b className="block text-sm text-ink-100">{c.stats.evidence}</b>Beweise
                      </div>
                      <div className="rounded bg-ink-900 py-1">
                        <b className="block text-sm text-ink-100">{c.stats.puzzles}</b>Rätsel
                      </div>
                      <div className="rounded bg-ink-900 py-1">
                        <b className="block text-sm text-ink-100">~{c.estimatedMinutes}</b>Min.
                      </div>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-2">
                      <span className="text-[11px] text-ink-500">{c.playedByMe > 0 ? `Von dir ${c.playedByMe}× gespielt` : 'Noch nicht gespielt'}</span>
                      {c.playable ? (
                        <button className="btn-primary btn-sm" disabled={!!st.activeSessionId} onClick={() => setStart(c)}>
                          {c.playedByMe > 0 ? 'Erneut spielen' : 'Fall starten'}
                        </button>
                      ) : (
                        <span className="flex items-center gap-1 text-[11px] text-ink-400">
                          <Icon name="lock" className="h-3 w-3" /> {c.lockedReason}
                        </span>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Section>

        <div className="grid gap-6 lg:grid-cols-2">
          <Section title="Verlauf" icon="clock">
            {sessions.length === 0 ? (
              <Empty icon="clock" title="Noch keine Ermittlungen" />
            ) : (
              <ul className="divide-y divide-ink-700">
                {sessions.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                    <div className="min-w-0">
                      <div className="truncate font-semibold">{s.title}</div>
                      <div className="text-xs text-ink-400">
                        {new Date(s.createdAt).toLocaleDateString('de-DE')} · {STATUS_LABEL[s.status]} · {s.participants} Teilnehmende {s.solved && '· ✓ gelöst'}
                      </div>
                    </div>
                    {s.status === 'ended' ? (
                      <button className="btn-ghost btn-sm" onClick={() => setResults(s.id)}>
                        Ergebnis
                      </button>
                    ) : (
                      <Link className="btn-secondary btn-sm" to={`/control/${s.id}`}>
                        Öffnen
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <div className="space-y-6" id="einstellungen">
            <Section title="Twitch & OBS" icon="twitch">
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span>Twitch-Konto</span>
                  {st.twitchLinked ? (
                    <span className="chip border-ok-600 text-ok-400">verbunden</span>
                  ) : st.chat.enabled ? (
                    <a className="btn-secondary btn-sm" href="/api/auth/twitch/login?role=streamer&return=/dashboard">
                      Mit Twitch verbinden
                    </a>
                  ) : (
                    <span className="chip border-ink-600 text-ink-400">Server ohne Twitch-Konfiguration</span>
                  )}
                </div>
                {st.twitchLinked && (
                  <div className="flex items-center justify-between">
                    <span>Chat-Anbindung (EventSub)</span>
                    <span className="flex items-center gap-2">
                      <span className="text-xs text-ink-400">{st.chat.connected ? 'aktiv' : st.chat.status}</span>
                      <button className="btn-ghost btn-sm" onClick={() => void api('/streamer/twitch/reconnect', { body: {} }).then(load)}>
                        Neu verbinden
                      </button>
                    </span>
                  </div>
                )}
                <CopyField label="OBS-Browserquelle (1920×1080)" value={st.overlayUrl} />
                <button
                  className="btn-ghost btn-sm"
                  onClick={async () => {
                    if (!confirm('Neuen Overlay-Link erzeugen? Der alte Link funktioniert dann nicht mehr.')) return;
                    await api('/streamer/overlay-token', { body: {} });
                    await load();
                  }}
                >
                  Overlay-Link erneuern
                </button>
              </div>
            </Section>
            <ModeratorSection mods={st.moderators} onChange={load} />
            <Section title="Community-Rangliste (alle Fälle)" icon="trophy">
              {community.length === 0 ? (
                <div className="text-sm text-ink-400">Erscheint, sobald Zuschauer mit Twitch-Konto Punkte sammeln.</div>
              ) : (
                <ol className="space-y-1 text-sm">
                  {community.map((c, i) => (
                    <li key={i} className="flex justify-between">
                      <span>
                        <span className="mr-2 font-mono text-ink-500">{i + 1}.</span>
                        {c.name} <span className="text-xs text-ink-500">({c.cases} Fälle)</span>
                      </span>
                      <span className="font-mono text-brass-300">{c.points}</span>
                    </li>
                  ))}
                </ol>
              )}
            </Section>
          </div>
        </div>
      </main>

      <StartModal c={start} onClose={() => setStart(null)} onStarted={(id) => nav(`/control/${id}`)} />
      <ResultsModal id={results} onClose={() => setResults(null)} />
    </div>
  );
}

function AssignButton({ onPick, disabled }: { onPick: (c: { id: string }) => void; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const [difficulty, setDifficulty] = useState('');
  const toast = useToast();
  return (
    <>
      <button className="btn-secondary btn-sm" disabled={disabled} onClick={() => setOpen(true)}>
        <Icon name="dice" /> Fall zuweisen lassen
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="Fall zuweisen lassen">
        <p className="mb-3 text-sm text-ink-300">Wir wählen einen Fall, den du noch nicht gespielt hast – bevorzugt einen, der gerade selten gespielt wird. So erlebt nicht jede Community denselben Fall.</p>
        <select className="input mb-3" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="">Beliebige Schwierigkeit</option>
          {Object.entries(DIFFICULTY_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button
          className="btn-primary w-full"
          onClick={async () => {
            try {
              const r = await api<{ case: { id: string } }>('/library/assign', { body: difficulty ? { difficulty } : {} });
              setOpen(false);
              onPick(r.case);
            } catch (e) {
              toast({ tone: 'error', text: (e as Error).message });
            }
          }}
        >
          Fall ziehen
        </button>
      </Modal>
    </>
  );
}

function StartModal({ c, onClose, onStarted }: { c: LibraryCase | null; onClose: () => void; onStarted: (id: string) => void }) {
  const [s, setS] = useState({ allowGuests: true, guestsCanVote: true, timedEvents: true, theories: true, discussion: true, voteSeconds: 60 });
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  if (!c) return null;
  return (
    <Modal open onClose={onClose} title={c.title}>
      <p className="text-sm text-ink-300">{c.tagline}</p>
      {c.playedByMe > 0 && <div className="mt-2 rounded-md border border-brass-500/50 px-3 py-2 text-xs text-brass-300">Deine Community kennt diesen Fall bereits ({c.playedByMe}×). Wiederholungen sind erlaubt.</div>}
      <div className="mt-4 divide-y divide-ink-700">
        <Toggle checked={s.allowGuests} onChange={(x) => setS({ ...s, allowGuests: x })} label="Gäste ohne Twitch-Login zulassen" />
        <Toggle checked={s.guestsCanVote} onChange={(x) => setS({ ...s, guestsCanVote: x })} label="Gäste dürfen abstimmen" />
        <Toggle checked={s.timedEvents} onChange={(x) => setS({ ...s, timedEvents: x })} label="Zeitgesteuerte Ereignisse" hint="z. B. „Nach 15 Minuten meldet sich die Versicherung“" />
        <Toggle checked={s.theories} onChange={(x) => setS({ ...s, theories: x })} label="Theorien" />
        <Toggle checked={s.discussion} onChange={(x) => setS({ ...s, discussion: x })} label="Diskussion auf der Webseite" />
        <label className="flex items-center justify-between py-2 text-sm">
          Standard-Abstimmungsdauer (Sek.)
          <input type="number" className="input w-24" min={15} max={600} value={s.voteSeconds} onChange={(e) => setS({ ...s, voteSeconds: Number(e.target.value) })} />
        </label>
      </div>
      <button
        className="btn-primary mt-4 w-full"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            const r = await api<{ id: string }>('/sessions', { body: { caseId: c.id, settings: s } });
            onStarted(r.id);
          } catch (e) {
            toast({ tone: 'error', text: (e as Error).message });
          } finally {
            setBusy(false);
          }
        }}
      >
        <Icon name="folder" /> Akte öffnen (Vorbereitung)
      </button>
      <p className="mt-2 text-center text-xs text-ink-500">Zuschauer können schon beitreten. Die Ermittlung startest du im Kontrollzentrum.</p>
    </Modal>
  );
}

function ResultsModal({ id, onClose }: { id: string | null; onClose: () => void }) {
  const [r, setR] = useState<any>(null);
  useEffect(() => {
    setR(null);
    if (id) void api(`/sessions/${id}/results`).then(setR);
  }, [id]);
  if (!id) return null;
  return (
    <Modal open onClose={onClose} title={r?.title ?? 'Ergebnis'}>
      {!r ? (
        <Spinner />
      ) : (
        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Stat label="Dauer" value={formatDuration(r.elapsedMs)} />
            <Stat label="Erkenntnisse" value={`${r.insights}/${r.insightsTotal}`} />
            <Stat label="Rätsel" value={`${r.puzzlesSolved}/${r.puzzlesTotal}`} />
            <Stat label="Teilnehmende" value={r.participants} />
          </div>
          <div>Anklagen: {r.accusations.length === 0 ? 'keine' : r.accusations.map((a: { correct: boolean }) => (a.correct ? '✓ richtig' : '✗ falsch')).join(', ')}</div>
          <div>
            <div className="label mb-1">Beste Ermittler</div>
            <ol className="space-y-1">
              {r.leaderboard.slice(0, 10).map((l: { id: string; name: string; points: number }, i: number) => (
                <li key={l.id} className="flex justify-between">
                  <span>
                    {i + 1}. {l.name}
                  </span>
                  <span className="font-mono text-brass-300">{l.points}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </Modal>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-ink-900 p-2 text-center">
      <div className="text-lg font-bold">{value}</div>
      <div className="text-[11px] text-ink-400">{label}</div>
    </div>
  );
}

function ModeratorSection({ mods, onChange }: { mods: string[]; onChange: () => Promise<void> }) {
  const [login, setLogin] = useState('');
  const toast = useToast();
  return (
    <Section title="Moderation" icon="shield">
      <p className="mb-2 text-xs text-ink-400">Moderatoren melden sich auf der Zuschauerseite mit Twitch an und können Theorien hervorheben, Beiträge ausblenden und Teilnehmende sperren. Die Lösung sehen sie nicht.</p>
      <form
        className="flex gap-2"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api('/streamer/moderators', { body: { login } });
            setLogin('');
            await onChange();
          } catch (er) {
            toast({ tone: 'error', text: (er as Error).message });
          }
        }}
      >
        <input className="input" placeholder="twitch_login" value={login} onChange={(e) => setLogin(e.target.value)} />
        <button className="btn-secondary">Hinzufügen</button>
      </form>
      <div className="mt-2 flex flex-wrap gap-1">
        {mods.map((m) => (
          <span key={m} className="chip border-ink-600 text-ink-200">
            {m}
            <button
              onClick={async () => {
                await api(`/streamer/moderators/${m}`, { method: 'DELETE' });
                await onChange();
              }}
              aria-label="Entfernen"
            >
              <Icon name="x" className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
    </Section>
  );
}
