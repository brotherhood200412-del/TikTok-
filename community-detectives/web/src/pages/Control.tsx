import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { EvidenceViewer } from '../components/Evidence';
import { Board, CharacterDetail, Discussion, Feed, InterrogationPanel, SolutionView, TheoryList, Timeline, VoteCard } from '../components/Game';
import { ConnectionBanner, CopyField, Empty, FullPageMessage, Icon, Logo, Modal, Progress, Section, Spinner, Toggle, useToast } from '../components/ui';
import { api, type AppConfig } from '../lib/api';
import { CATEGORY_LABEL, MOOD_LABEL, STATUS_LABEL, formatDuration } from '../lib/format';
import { useGameClock, useLive, type OwnerState } from '../lib/live';

type CenterTab = 'beweise' | 'verhoer' | 'raetsel' | 'ereignisse' | 'erkenntnisse' | 'board' | 'loesung' | 'einstellungen';

export default function Control() {
  const { id = '' } = useParams();
  const hs = useMemo(() => ({ mode: 'control' as const, sessionId: id }), [id]);
  const live = useLive<OwnerState>(hs);
  const { state: v } = live;
  const toast = useToast();
  const nav = useNavigate();
  const [tab, setTab] = useState<CenterTab>('beweise');
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [streamerMode, setStreamerMode] = useState(true);
  const elapsed = useGameClock(v?.elapsedMs ?? 0, v?.runningSince ?? null, live.clockOffset);

  useEffect(() => {
    void api<AppConfig>('/config').then(setCfg);
  }, []);
  useEffect(() => {
    const n = live.notices.at(-1);
    if (n) toast({ tone: 'info', title: n.kind === 'hint' ? 'Hinweis-Anfrage' : 'Hinweis', text: n.text });
  }, [live.notices, toast]);

  if (live.status === 'fatal') return <FullPageMessage title="Kein Zugriff">{live.error?.message} <Link className="text-blood-300 underline" to="/dashboard">Zum Dashboard</Link></FullPageMessage>;
  if (!v) return <FullPageMessage title="Kontrollzentrum lädt …"><Spinner /></FullPageMessage>;

  const run = async (action: string, payload?: unknown, success?: string) => {
    const r = await live.control(action, payload);
    toast({ tone: r.ok ? 'success' : 'error', text: r.ok ? success ?? r.message ?? 'OK' : r.message ?? 'Fehler' });
    return r.ok;
  };
  const s = v.secrets;
  const joinUrl = `${cfg?.publicUrl ?? location.origin}/play/${v.joinCode}`;
  const done = v.status === 'revealed' || v.status === 'ended';

  return (
    <div className="min-h-dvh">
      <ConnectionBanner status={live.status} error={live.error} />
      <header className="sticky top-0 z-30 border-b border-ink-700 bg-ink-900/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-2.5">
          <Link to="/dashboard">
            <Logo compact />
          </Link>
          <div className="min-w-0 flex-1">
            <div className="truncate font-display text-lg font-bold">{v.case.title}</div>
            <div className="text-xs text-ink-400">
              Kontrollzentrum · {STATUS_LABEL[v.status]} · {formatDuration(elapsed)} · {v.participants} Teilnehmende · Code <b className="font-mono text-ink-200">{v.joinCode}</b>
            </div>
          </div>
          <button className={`btn-sm ${streamerMode ? 'btn-secondary' : 'btn-primary'}`} onClick={() => setStreamerMode((m) => !m)} title="Geheime Inhalte unkenntlich machen, solange der Bildschirm übertragen wird">
            <Icon name={streamerMode ? 'eyeoff' : 'eye'} /> {streamerMode ? 'Streamer-Modus an' : 'Geheimes sichtbar'}
          </button>
          <ChatBadge status={live.chatStatus} />
        </div>
      </header>

      <div className="mx-auto grid max-w-[1600px] gap-4 p-4 xl:grid-cols-[340px_1fr_380px]">
        {/* ------------------------------ Ablauf ------------------------------ */}
        <div className="space-y-4">
          <Section title="Spielablauf" icon="play">
            <div className="flex flex-wrap gap-2">
              {v.status === 'lobby' && (
                <button className="btn-primary w-full" onClick={() => void run('start', {}, 'Ermittlung gestartet!')}>
                  <Icon name="play" /> Ermittlung starten
                </button>
              )}
              {(v.status === 'active' || v.status === 'finale') && (
                <button className="btn-secondary flex-1" onClick={() => void run('pause')}>
                  <Icon name="pause" /> Pause
                </button>
              )}
              {v.status === 'paused' && (
                <button className="btn-primary flex-1" onClick={() => void run('resume')}>
                  <Icon name="play" /> Fortsetzen
                </button>
              )}
            </div>
            <div className="mt-3">
              <div className="mb-1 flex justify-between text-xs text-ink-400">
                <span>Erkenntnisse</span>
                <span>
                  {v.progress.insights}/{v.progress.insightsTotal} · Rätsel {v.progress.puzzlesSolved}/{v.progress.puzzlesTotal}
                </span>
              </div>
              <Progress value={v.progress.insights} max={v.progress.insightsTotal} />
            </div>
            <div className="mt-4 label">Phasen</div>
            <div className="mt-1 space-y-1">
              {v.phases.map((p, i) => (
                <button
                  key={p.id}
                  disabled={done}
                  onClick={() => void run('phase', { phase: p.id })}
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${i === v.phaseIndex ? 'border-blood-500 bg-blood-500/10' : 'border-ink-700 hover:bg-ink-750'}`}
                >
                  <div className="font-semibold">
                    {i + 1}. {p.title}
                  </div>
                  <div className="text-xs text-ink-400">{p.goal}</div>
                </button>
              ))}
            </div>
            <TaskEditor current={v.task} onSave={(t) => void run('task', { task: t }, 'Aufgabe aktualisiert.')} />
          </Section>

          <Section title="Finale & Auflösung" icon="scale">
            <div className="space-y-2">
              {v.status === 'active' && (
                <button className="btn-primary w-full" onClick={() => void run('finale', {}, 'Finale gestartet – jetzt Anklage-Abstimmung starten!')}>
                  <Icon name="scale" /> Finale starten
                </button>
              )}
              {v.status === 'finale' && (
                <>
                  <button className="btn-primary w-full" onClick={() => void run('startVote', { kind: 'accuse' }, 'Anklage-Abstimmung läuft.')}>
                    <Icon name="vote" /> Anklage-Abstimmung starten
                  </button>
                  <button className="btn-ghost w-full" onClick={() => void run('cancelFinale')}>
                    Zurück zur Ermittlung
                  </button>
                </>
              )}
              {v.status === 'solved' && v.accusation.proof && (
                <button className="btn-secondary w-full" onClick={() => void run('startVote', { kind: 'proof' }, 'Beweisfrage läuft.')}>
                  <Icon name="vote" /> Beweisfrage abstimmen lassen
                </button>
              )}
              {v.accusation.attempts.length > 0 && (
                <div className="text-xs text-ink-400">
                  Anklagen: {v.accusation.attempts.map((a) => `${v.characters.find((c) => c.id === a.suspect)?.name ?? a.suspect} ${a.correct ? '✓' : '✗'}`).join(' · ')}
                </div>
              )}
              {!done && (
                <button
                  className={v.status === 'solved' ? 'btn-primary w-full' : 'btn-secondary w-full'}
                  onClick={() => {
                    if (v.status !== 'solved' && !confirm('Auflösung jetzt zeigen? Die Lösung wird für alle sichtbar.')) return;
                    void run('reveal', {}, 'Auflösung wird angezeigt.');
                  }}
                >
                  <Icon name="star" /> Auflösung zeigen
                </button>
              )}
              {v.status !== 'ended' && (
                <button
                  className="btn-ghost w-full text-blood-300"
                  onClick={async () => {
                    if (!confirm('Sitzung endgültig beenden?')) return;
                    if (await run('end', {}, 'Sitzung beendet.')) nav('/dashboard');
                  }}
                >
                  Sitzung beenden
                </button>
              )}
            </div>
          </Section>

          <VoteControl v={v} clockOffset={live.clockOffset} run={run} />
        </div>

        {/* ------------------------------ Mitte ------------------------------ */}
        <div className="min-w-0 space-y-4">
          {v.interrogation && <InterrogationPanel view={v} />}
          <div className="card flex flex-wrap gap-1 p-1.5">
            {(
              [
                ['beweise', 'Beweise', 'doc'],
                ['verhoer', 'Vernehmung', 'mic'],
                ['raetsel', 'Rätsel', 'puzzle'],
                ['ereignisse', 'Ereignisse', 'alert'],
                ['erkenntnisse', 'Erkenntnisse', 'bulb'],
                ['board', 'Board & Zeitlinie', 'link'],
                ['loesung', 'Lösung', 'lock'],
                ['einstellungen', 'Einstellungen', 'shield'],
              ] as [CenterTab, string, string][]
            ).map(([id, label, icon]) => (
              <button key={id} className={`btn-sm ${tab === id ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setTab(id)}>
                <Icon name={icon} /> {label}
              </button>
            ))}
          </div>
          {tab === 'beweise' && <EvidenceTab v={v} run={run} streamerMode={streamerMode} />}
          {tab === 'verhoer' && <InterrogationTab v={v} run={run} streamerMode={streamerMode} />}
          {tab === 'raetsel' && (
            <div className="space-y-3">
              {s.puzzles.map((p) => {
                const pub = v.puzzles.find((x) => x.id === p.id);
                return (
                  <div key={p.id} className={`card p-4 ${p.available ? '' : 'opacity-60'}`}>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="font-display text-base font-bold">{p.title}</div>
                        <div className="text-xs text-ink-400">{p.available ? (p.solved ? `Gelöst${pub?.solvedBy ? ` von ${pub.solvedBy}` : ''}` : `Offen · ${pub?.attempts ?? 0} Versuche`) : `Gesperrt: ${p.unlock}`}</div>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        <button className="btn-secondary btn-sm" disabled={!p.available} onClick={() => void run('spotlight', { type: 'puzzle', id: p.id }, 'Im Fokus.')}>
                          <Icon name="eye" /> Fokus
                        </button>
                        <button className="btn-secondary btn-sm" disabled={!p.available || p.solved || (pub?.hints.length ?? 0) >= p.hints.length} onClick={() => void run('hint', { puzzle: p.id }, 'Hinweis freigegeben.')}>
                          <Icon name="bulb" /> Hinweis {pub?.hints.length ?? 0}/{p.hints.length}
                        </button>
                        <button className="btn-ghost btn-sm" disabled={p.solved} onClick={() => confirm('Rätsel auflösen? Es gibt dafür keine Punkte.') && void run('solvePuzzle', { puzzle: p.id })}>
                          Auflösen
                        </button>
                      </div>
                    </div>
                    {pub && <p className="mt-2 text-sm text-ink-300">{pub.prompt}</p>}
                    <Secret hidden={streamerMode}>
                      <div className="mt-2 rounded-md bg-ink-900 px-3 py-2 text-sm">
                        <span className="label mr-2">Lösung</span>
                        <span className="font-mono text-brass-300">{p.answer}</span>
                      </div>
                    </Secret>
                  </div>
                );
              })}
            </div>
          )}
          {tab === 'ereignisse' && (
            <div className="space-y-3">
              <p className="text-sm text-ink-400">Ereignisse mit Zeit- oder Bedingungsauslöser starten automatisch (sofern zeitgesteuerte Ereignisse aktiv sind). Du kannst verfügbare Ereignisse auch dramaturgisch passend selbst auslösen.</p>
              {s.events.map((e) => (
                <div key={e.id} className="card p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-display text-base font-bold">{e.title}</div>
                      <div className="text-xs text-ink-400">Auslöser: {e.trigger}</div>
                    </div>
                    {e.fired ? (
                      <span className="chip border-ok-600 text-ok-400">ausgelöst</span>
                    ) : (
                      <button className="btn-secondary btn-sm" disabled={!e.available} onClick={() => void run('fireEvent', { event: e.id }, 'Ereignis ausgelöst.')}>
                        <Icon name="bolt" /> Jetzt auslösen
                      </button>
                    )}
                  </div>
                  <Secret hidden={streamerMode && !e.fired}>
                    <p className="mt-2 text-sm text-ink-300">{e.text}</p>
                  </Secret>
                </div>
              ))}
            </div>
          )}
          {tab === 'erkenntnisse' && (
            <div className="grid gap-2 md:grid-cols-2">
              {s.insightsAll.map((i) => {
                const pub = v.insights.find((x) => x.id === i.id);
                return (
                  <div key={i.id} className={`card p-3 ${i.found ? '' : 'opacity-70'}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-ink-400">{pub ? CATEGORY_LABEL[pub.category] : 'nicht gefunden'}</span>
                      <span className="flex gap-1">
                        {i.key && <span className="chip border-brass-500 text-brass-300">Schlüssel</span>}
                        {i.found && (
                          <button className="btn-ghost btn-sm !py-0.5" onClick={() => void run('spotlight', { type: 'insight', id: i.id }, 'Im Overlay.')}>
                            <Icon name="eye" />
                          </button>
                        )}
                      </span>
                    </div>
                    <Secret hidden={streamerMode && !i.found}>
                      <div className="font-semibold">{i.title}</div>
                    </Secret>
                    {pub && <p className="text-sm text-ink-300">{pub.text}</p>}
                    {pub?.by && <div className="text-[11px] text-ink-500">von {pub.by}</div>}
                  </div>
                );
              })}
            </div>
          )}
          {tab === 'board' && (
            <div className="space-y-4">
              <Board view={v} />
              <div className="card p-4">
                <div className="mb-3 font-display text-base font-bold">Zeitlinie der Community</div>
                <Timeline view={v} />
              </div>
            </div>
          )}
          {tab === 'loesung' && (
            <Secret hidden={streamerMode} big>
              {v.solution ? (
                <SolutionView view={v} />
              ) : (
                <div className="space-y-4">
                  <div className="paper px-5 py-5">
                    <div className="stamp mb-2 text-xs">Streng geheim</div>
                    <div className="font-display text-2xl font-bold">Täter: {s.culpritName}</div>
                    <p className="mt-2 font-typewriter">{s.solution.summary}</p>
                    <p className="mt-2 text-sm">
                      <b>Motiv:</b> {s.solution.motive}
                    </p>
                    <p className="mt-1 text-sm">
                      <b>Tathergang:</b> {s.solution.method}
                    </p>
                  </div>
                  <div className="card p-4">
                    <div className="mb-2 font-display text-base font-bold">Lösungskette</div>
                    <ol className="space-y-1 text-sm">
                      {s.solution.chain.map((c) => (
                        <li key={c.insight} className={c.found ? 'text-ok-400' : 'text-ink-300'}>
                          {c.found ? '✓' : '○'} <b>{c.title}</b> – {c.explanation}
                        </li>
                      ))}
                    </ol>
                  </div>
                  <div className="card p-4">
                    <div className="mb-2 font-display text-base font-bold">Spielleiter-Notizen</div>
                    <ul className="space-y-1 text-sm text-ink-300">
                      {s.gmNotes.map((n, i) => (
                        <li key={i}>
                          {n.phase && <span className="chip mr-2 border-ink-600 text-ink-400">{v.phases.find((p) => p.id === n.phase)?.title}</span>}
                          {n.text}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="card p-4">
                    <div className="mb-2 font-display text-base font-bold">Geheimnisse der Figuren</div>
                    <ul className="space-y-2 text-sm">
                      {Object.entries(s.characterSecrets).map(([cid, secret]) => (
                        <li key={cid}>
                          <b>{v.characters.find((c) => c.id === cid)?.name ?? cid}:</b> <span className="text-ink-300">{secret}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </Secret>
          )}
          {tab === 'einstellungen' && <SettingsTab v={v} run={run} />}
        </div>

        {/* ------------------------------ Community ------------------------------ */}
        <div className="space-y-4">
          <Section title="Zuschauer & Overlay" icon="link">
            <div className="space-y-3">
              <CopyField label="Link für Zuschauer" value={joinUrl} />
              <div className="flex items-center justify-between rounded-lg bg-ink-900 px-3 py-2">
                <span className="text-xs text-ink-400">Beitrittscode</span>
                <span className="font-mono text-xl font-bold tracking-[0.3em] text-brass-300">{v.joinCode}</span>
              </div>
              <Link to="/dashboard#einstellungen" className="text-xs text-ink-400 underline">
                OBS-Overlay-Link im Dashboard
              </Link>
            </div>
          </Section>

          {v.vote === null && v.hintRequests > 0 && (
            <div className="card border-brass-500/60 p-3 text-sm text-brass-300">
              <Icon name="bulb" className="mr-1 inline" /> {v.hintRequests} Hinweis-Anfrage(n) aus der Community.
            </div>
          )}

          <Section title="Rangliste" icon="trophy">
            <ParticipantList v={v} run={run} live={live} />
          </Section>

          <Section title="Theorien" icon="bulb">
            <div className="scroll-thin max-h-96 overflow-y-auto">
              <TheoryList
                view={v}
                onModerate={(id, status) =>
                  void live.mod('theoryStatus', { theory: id, status }).then((r) => toast({ tone: r.ok ? 'success' : 'error', text: r.message ?? '' }))
                }
              />
            </div>
          </Section>

          <Section title="Diskussion" icon="chat">
            <Discussion messages={v.discussion} enabled onHide={(id) => void live.mod('hideMessage', { message: id })} />
          </Section>

          {cfg?.chatSimulator && <ChatSimulator sessionId={v.sessionId} bot={live.bot} />}

          <Section title="Protokoll" icon="clock">
            <div className="scroll-thin max-h-80 overflow-y-auto">
              <Feed feed={v.feed} limit={40} />
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------ Hilfskomponenten ------------------------------ */

function Secret({ hidden, children, big = false }: { hidden: boolean; children: ReactNode; big?: boolean }) {
  const [peek, setPeek] = useState(false);
  if (!hidden || peek) return <>{children}</>;
  if (!big) {
    return (
      <button type="button" className="chip my-1 border-ink-600 text-ink-400 hover:text-ink-100" onClick={() => setPeek(true)}>
        <Icon name="lock" className="h-3 w-3" /> geheim · anzeigen
      </button>
    );
  }
  return (
    <div className="relative">
      <div className="pointer-events-none select-none blur-md" aria-hidden="true">
        {children}
      </div>
      <button className={`absolute inset-0 flex items-center justify-center gap-2 text-xs font-semibold text-ink-200 ${big ? 'text-base' : ''}`} onMouseDown={() => setPeek(true)} onMouseLeave={() => setPeek(false)} onClick={() => setPeek(true)}>
        <Icon name="lock" /> Geheim – klicken zum Aufdecken
      </button>
    </div>
  );
}

function ChatBadge({ status }: { status: { enabled: boolean; connected: boolean; status: string; lastError: string | null } | null }) {
  if (!status) return null;
  const label = !status.enabled ? 'Twitch nicht konfiguriert' : status.status === 'not_linked' ? 'Twitch nicht verbunden' : status.connected ? 'Chat verbunden' : `Chat: ${status.status}`;
  return (
    <span className={`chip ${status.connected ? 'border-ok-600 text-ok-400' : 'border-ink-600 text-ink-400'}`} title={status.lastError ?? ''}>
      <Icon name="twitch" className="h-3 w-3" /> {label}
    </span>
  );
}

function TaskEditor({ current, onSave }: { current: string | null; onSave: (t: string) => void }) {
  const [t, setT] = useState(current ?? '');
  useEffect(() => setT(current ?? ''), [current]);
  return (
    <form
      className="mt-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(t);
      }}
    >
      <div className="label mb-1">Aktuelle Aufgabe (Overlay)</div>
      <div className="flex gap-2">
        <input className="input" value={t} maxLength={200} onChange={(e) => setT(e.target.value)} />
        <button className="btn-secondary btn-sm">Setzen</button>
      </div>
    </form>
  );
}

type Run = (action: string, payload?: unknown, success?: string) => Promise<boolean>;

function VoteControl({ v, clockOffset, run }: { v: OwnerState; clockOffset: number; run: Run }) {
  const [kind, setKind] = useState('interrogate');
  const [question, setQuestion] = useState('');
  const [options, setOptions] = useState('');
  const [seconds, setSeconds] = useState(60);
  const last = v.lastVote;
  return (
    <Section title="Abstimmungen" icon="vote">
      {v.vote?.status === 'open' ? (
        <div className="space-y-2">
          <VoteCard vote={v.vote} clockOffset={clockOffset} />
          <div className="flex gap-2">
            <button className="btn-primary flex-1" onClick={() => void run('closeVote', {}, 'Abstimmung beendet.')}>
              Jetzt auswerten
            </button>
            <button className="btn-ghost" onClick={() => void run('cancelVote')}>
              Abbrechen
            </button>
          </div>
        </div>
      ) : (
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            void run(
              'startVote',
              { kind, question: question || undefined, options: kind === 'custom' ? options.split('\n').map((o) => o.trim()).filter(Boolean) : undefined, seconds },
              'Abstimmung gestartet.',
            );
          }}
        >
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="interrogate">Wen vernehmen wir?</option>
            <option value="question">Welche Frage stellen wir? (laufende Vernehmung)</option>
            <option value="examine">Welchen Beweis untersuchen wir?</option>
            <option value="hint">Hinweis für Rätsel im Fokus aufdecken?</option>
            <option value="accuse">Anklage: Wer ist schuldig?</option>
            <option value="custom">Eigene Abstimmung</option>
          </select>
          <input className="input" placeholder="Frage (optional – sonst Standard)" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={200} />
          {kind === 'custom' && <textarea className="input min-h-20" placeholder={'Eine Option pro Zeile'} value={options} onChange={(e) => setOptions(e.target.value)} />}
          <div className="flex items-center gap-2">
            <label className="text-xs text-ink-400">Dauer</label>
            <input type="number" className="input w-24" min={15} max={600} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} />
            <span className="text-xs text-ink-400">Sek.</span>
            <button className="btn-primary ml-auto" disabled={v.status !== 'active' && v.status !== 'finale' && v.status !== 'solved'}>
              Starten
            </button>
          </div>
          <p className="text-[11px] text-ink-500">Ergebnisse werden automatisch angewendet (z. B. Vernehmung starten, Frage stellen). Bei Gleichstand entscheidest du.</p>
        </form>
      )}
      {last && last.status === 'closed' && last.tie && v.vote?.status !== 'open' && (
        <div className="mt-3 rounded-md border border-brass-500/60 p-3">
          <div className="text-sm text-brass-300">Gleichstand bei „{last.question}“ – entscheide:</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {last.tie.map((i) => (
              <button key={i} className="btn-secondary btn-sm" onClick={() => void run('applyVote', { index: i }, 'Ergebnis übernommen.')}>
                {last.options[i].label}
              </button>
            ))}
          </div>
        </div>
      )}
    </Section>
  );
}

function EvidenceTab({ v, run, streamerMode }: { v: OwnerState; run: Run; streamerMode: boolean }) {
  const [open, setOpen] = useState<string | null>(null);
  const insightMap = useMemo(() => new Map(v.insights.map((i) => [i.id, i])), [v.insights]);
  const ev = v.evidence.find((e) => e.id === open);
  const hot = useMemo(() => new Set(v.secrets.hotspots.filter((h) => h.evidence === open).map((h) => h.item)), [v.secrets.hotspots, open]);
  return (
    <div className="space-y-4">
      <div className="grid gap-2 md:grid-cols-2">
        {v.evidence.map((e) => {
          const hs = v.secrets.hotspots.filter((h) => h.evidence === e.id);
          return (
            <div key={e.id} className={`card p-3 ${v.spotlight?.type === 'evidence' && v.spotlight.id === e.id ? '!border-brass-400' : ''}`}>
              <div className="flex items-start justify-between gap-2">
                <button className="min-w-0 text-left" onClick={() => setOpen(e.id)}>
                  <div className="font-semibold">{e.title}</div>
                  <div className="text-xs text-ink-400">
                    Hotspots: {hs.filter((h) => h.found).length}/{hs.length}
                  </div>
                </button>
                <button className="btn-secondary btn-sm" onClick={() => void run('spotlight', { type: 'evidence', id: e.id }, 'Im Overlay.')}>
                  <Icon name="eye" /> Fokus
                </button>
              </div>
            </div>
          );
        })}
      </div>
      {v.secrets.lockedEvidence.length > 0 && (
        <div className="card p-4">
          <div className="mb-2 font-display text-base font-bold">Noch gesperrt ({v.secrets.lockedEvidence.length})</div>
          <Secret hidden={streamerMode} big>
          <div className="space-y-2">
            {v.secrets.lockedEvidence.map((e) => (
              <div key={e.id} className="flex items-center justify-between gap-2 text-sm">
                <div className="min-w-0">
                  <div className="font-semibold text-ink-200">{e.title}</div>
                  <div className="text-xs text-ink-500">Freischaltung: {e.unlock}</div>
                </div>
                <button className="btn-ghost btn-sm" onClick={() => confirm('Beweismittel vorzeitig freigeben?') && void run('unlockEvidence', { evidence: e.id }, 'Freigegeben.')}>
                  Freigeben
                </button>
              </div>
            ))}
          </div>
          </Secret>
        </div>
      )}
      <Modal open={!!ev} onClose={() => setOpen(null)} title={ev?.title} wide>
        {ev && <EvidenceViewer evidence={ev} insights={insightMap} hotspotItems={streamerMode ? undefined : hot} />}
      </Modal>
    </div>
  );
}

function InterrogationTab({ v, run, streamerMode }: { v: OwnerState; run: Run; streamerMode: boolean }) {
  const [charOpen, setCharOpen] = useState<string | null>(null);
  const current = v.interrogation?.character;
  const it = v.secrets.interrogations.find((i) => i.character === current);
  const ch = v.characters.find((c) => c.id === charOpen);
  return (
    <div className="space-y-4">
      <div className="grid gap-2 md:grid-cols-3">
        {v.characters
          .filter((c) => c.interrogable)
          .map((c) => (
            <div key={c.id} className={`card p-3 ${current === c.id ? '!border-blood-500' : ''}`}>
              <button className="text-left" onClick={() => setCharOpen(c.id)}>
                <div className="font-semibold">{c.name}</div>
                <div className="text-xs text-ink-400">{c.occupation}</div>
              </button>
              <div className="mt-2 flex gap-1">
                {current === c.id ? (
                  <button className="btn-ghost btn-sm" onClick={() => void run('endInterrogation')}>
                    Beenden
                  </button>
                ) : (
                  <button className="btn-secondary btn-sm" onClick={() => void run('interrogate', { character: c.id }, `Vernehmung ${c.name}.`)}>
                    <Icon name="mic" /> Vernehmen
                  </button>
                )}
              </div>
            </div>
          ))}
      </div>
      {it ? (
        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between">
            <div className="font-display text-lg font-bold">Fragen an {it.name}</div>
            <button className="btn-secondary btn-sm" onClick={() => void run('startVote', { kind: 'question' }, 'Abstimmung über die Frage läuft.')}>
              <Icon name="vote" /> Community wählt Frage
            </button>
          </div>
          <div className="space-y-2">
            {it.topics.map((t) => (
              <div key={t.id} className={`rounded-md border p-3 ${t.available ? 'border-ink-600' : 'border-ink-700 opacity-50'}`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold">
                      {t.question} {t.asked && <span className="text-xs text-ok-400">✓ gestellt</span>}
                    </div>
                    {!t.available && <div className="text-xs text-ink-500">Gesperrt: {streamerMode ? '…' : t.unlock}</div>}
                  </div>
                  <button className="btn-primary btn-sm" disabled={!t.available} onClick={() => void run('ask', { topic: t.id })}>
                    Fragen
                  </button>
                </div>
                <Secret hidden={streamerMode}>
                  <div className="mt-2 space-y-1">
                    {t.responses.map((r, i) => (
                      <div key={i} className="text-xs text-ink-400">
                        <span className="text-brass-300">[{r.when}]</span> ({MOOD_LABEL[r.mood]}) {r.text.slice(0, 160)}
                        {r.text.length > 160 ? '…' : ''}
                        {r.reveals && <span className="text-blood-300"> → Erkenntnis</span>}
                      </div>
                    ))}
                  </div>
                </Secret>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <Empty icon="mic" title="Keine Vernehmung aktiv">Starte eine Vernehmung oder lass die Community abstimmen, wen ihr befragt.</Empty>
      )}
      <Modal open={!!ch} onClose={() => setCharOpen(null)} title={ch?.name}>
        {ch && <CharacterDetail c={ch} log={v.interrogationLog} />}
      </Modal>
    </div>
  );
}

function SettingsTab({ v, run }: { v: OwnerState; run: Run }) {
  const st = v.sessionSettings;
  const set = (patch: Record<string, unknown>) => void run('settings', patch, 'Gespeichert.');
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Section title="Teilnahme" icon="users">
        <Toggle checked={st.allowGuests} onChange={(x) => set({ allowGuests: x })} label="Gäste erlauben" hint="Zuschauer ohne Twitch-Login können mitspielen." />
        <Toggle checked={st.guestsCanVote} onChange={(x) => set({ guestsCanVote: x })} label="Gäste dürfen abstimmen" hint="Aus = nur verifizierte Twitch-Accounts zählen (Schutz vor Mehrfachaccounts)." />
        <Toggle checked={st.theories} onChange={(x) => set({ theories: x })} label="Theorien erlauben" />
        <Toggle checked={st.discussion} onChange={(x) => set({ discussion: x })} label="Diskussion auf der Webseite" />
      </Section>
      <Section title="Spielablauf" icon="clock">
        <Toggle checked={st.timedEvents} onChange={(x) => set({ timedEvents: x })} label="Zeitgesteuerte Ereignisse" hint="Aus = Ereignisse löst du manuell aus." />
        <Toggle checked={st.autoApplyVotes} onChange={(x) => set({ autoApplyVotes: x })} label="Abstimmungsergebnisse automatisch anwenden" />
        <Toggle checked={st.chatReplies} onChange={(x) => set({ chatReplies: x })} label="Antworten im Twitch-Chat" />
        <Toggle checked={st.bareNumberVotes} onChange={(x) => set({ bareNumberVotes: x })} label="Abstimmen mit bloßer Zahl im Chat" hint='z. B. „2“ statt „!a 2“' />
        <div className="mt-2 flex items-center gap-2 text-sm">
          Hinweis-Schwelle
          <input type="number" min={1} max={500} defaultValue={st.hintRequestThreshold} className="input w-24" onBlur={(e) => set({ hintRequestThreshold: Number(e.target.value) })} />
        </div>
      </Section>
      <Section title="Overlay" icon="eye">
        <div className="flex gap-2">
          {(['left', 'right'] as const).map((p) => (
            <button key={p} className={`btn-sm ${st.overlay.position === p ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => set({ overlay: { position: p } })}>
              {p === 'left' ? 'Links' : 'Rechts'}
            </button>
          ))}
        </div>
        <Toggle checked={st.overlay.showLeaderboard} onChange={(x) => set({ overlay: { showLeaderboard: x } })} label="Rangliste anzeigen" />
        <Toggle checked={st.overlay.showFeed} onChange={(x) => set({ overlay: { showFeed: x } })} label="Entdeckungen einblenden" />
        <Toggle checked={st.overlay.showJoin} onChange={(x) => set({ overlay: { showJoin: x } })} label="Beitrittscode anzeigen" />
        <div className="mt-2 flex items-center gap-2 text-sm">
          Skalierung
          <input type="range" min={0.6} max={1.6} step={0.1} defaultValue={st.overlay.scale} onMouseUp={(e) => set({ overlay: { scale: Number((e.target as HTMLInputElement).value) } })} />
        </div>
      </Section>
    </div>
  );
}

function ParticipantList({ v, run, live }: { v: OwnerState; run: Run; live: ReturnType<typeof useLive<OwnerState>> }) {
  const [q, setQ] = useState('');
  const toast = useToast();
  const list = v.participantList.filter((p) => p.name.toLowerCase().includes(q.toLowerCase())).slice(0, 50);
  return (
    <div>
      <input className="input mb-2" placeholder="Teilnehmende suchen …" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="mb-2 grid grid-cols-2 gap-1 text-xs">
        {v.teams.map((t) => (
          <div key={t.id} className="rounded bg-ink-900 px-2 py-1">
            {t.label}: <b className="text-brass-300">{t.points}</b> ({t.members})
          </div>
        ))}
      </div>
      <ul className="scroll-thin max-h-72 space-y-1 overflow-y-auto">
        {list.map((p) => (
          <li key={p.id} className={`group flex items-center justify-between gap-2 rounded px-2 py-1 text-sm hover:bg-ink-750 ${p.banned ? 'opacity-40 line-through' : ''}`}>
            <span className="min-w-0 truncate">
              {p.name} {p.verified && <Icon name="twitch" className="inline h-3 w-3 text-[#a970ff]" />} <span className="text-[10px] text-ink-500">{p.source}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="font-mono text-brass-300">{p.points}</span>
              <button className="hidden text-xs text-ok-400 group-hover:inline" title="10 Bonuspunkte" onClick={() => void run('award', { participant: p.id, amount: 10, reason: 'Starke Ermittlungsarbeit' }, '+10 Punkte')}>
                +10
              </button>
              <button
                className="hidden text-xs text-blood-300 group-hover:inline"
                onClick={() => void live.mod('ban', { participant: p.id, banned: !p.banned }).then((r) => toast({ tone: r.ok ? 'success' : 'error', text: r.message ?? '' }))}
              >
                {p.banned ? 'entsperren' : 'sperren'}
              </button>
            </span>
          </li>
        ))}
        {list.length === 0 && <li className="text-sm text-ink-400">Noch niemand dabei.</li>}
      </ul>
    </div>
  );
}

function ChatSimulator({ sessionId, bot }: { sessionId: string; bot: { text: string; at: number }[] }) {
  const [user, setUser] = useState('zuschauer_1');
  const [text, setText] = useState('!ermitteln');
  const [log, setLog] = useState<{ user: string; text: string; result: string | null }[]>([]);
  const send = async () => {
    try {
      const r = await api<{ result: string | null }>(`/sessions/${sessionId}/simulate-chat`, { body: { user, text } });
      setLog((l) => [...l.slice(-30), { user, text, result: r.result }]);
    } catch (e) {
      setLog((l) => [...l.slice(-30), { user, text, result: (e as Error).message }]);
    }
  };
  const merged = [...log.map((l, i) => ({ k: `u${i}`, node: <span><b className="text-[#a970ff]">{l.user}:</b> {l.text} <span className="text-ink-500">→ {l.result ?? 'ignoriert'}</span></span> })), ...bot.slice(-10).map((b, i) => ({ k: `b${i}`, node: <span className="text-brass-300">🤖 {b.text}</span> }))];
  return (
    <Section title="Chat-Simulator (lokal)" icon="twitch">
      <p className="mb-2 text-xs text-ink-400">Testet Chatbefehle ohne Twitch-Verbindung – genau derselbe Verarbeitungsweg wie echte EventSub-Nachrichten.</p>
      <div className="scroll-thin mb-2 max-h-40 space-y-1 overflow-y-auto rounded bg-ink-950 p-2 text-xs">{merged.map((m) => <div key={m.k}>{m.node}</div>)}</div>
      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <div className="flex gap-2">
          <input className="input w-36" value={user} onChange={(e) => setUser(e.target.value)} />
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <div className="flex flex-wrap gap-1">
          {['!ermitteln', '!a 1', '!a 2', '!verdächtige', '!beweis 1', '!hinweis', '!team analyse', '!punkte'].map((c) => (
            <button type="button" key={c} className="chip border-ink-600 text-ink-300 hover:bg-ink-700" onClick={() => setText(c)}>
              {c}
            </button>
          ))}
          <button className="btn-secondary btn-sm ml-auto">Senden</button>
        </div>
      </form>
    </Section>
  );
}
