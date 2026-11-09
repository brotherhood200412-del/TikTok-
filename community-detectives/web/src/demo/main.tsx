import { StrictMode, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { DifficultyBadge, GenreBadge, Icon, Logo, ToastProvider } from '../components/ui';
import { LocalTransportContext } from '../lib/live';
import Control from '../pages/Control';
import Overlay from '../pages/Overlay';
import { Investigation } from '../pages/Play';
import '../styles.css';
import { CASES, LocalGame } from './localGame';

const game = new LocalGame();

// In der Vorschau gibt es keinen Server: API-Aufrufe der Oberflächen werden lokal beantwortet.
const realFetch = window.fetch.bind(window);
window.fetch = async (input, init) => {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url;
  if (!url.startsWith('/api/')) return realFetch(input, init);
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  if (url === '/api/config') return json({ twitchEnabled: false, devLogin: false, chatSimulator: true, publicUrl: 'Vorschau' });
  if (url.endsWith('/simulate-chat')) {
    const b = JSON.parse(String(init?.body ?? '{}')) as { user: string; text: string };
    return json({ ok: true, result: game.chat(b.user, b.text) });
  }
  return json({ error: 'In der Vorschau nicht verfügbar.' }, 404);
};
// Bestätigungsdialoge sind in der Vorschau-Umgebung gesperrt.
window.confirm = () => true;

function DemoBar() {
  const nav = useNavigate();
  const loc = useLocation();
  const code = game.data?.code;
  const tabs = [
    { label: 'Zuschauer', icon: 'users', to: code ? `/play/${code}` : '/' },
    { label: 'Streamer', icon: 'play', to: '/control/local' },
    { label: 'Overlay', icon: 'eye', to: '/overlay/local' },
    { label: 'Fälle', icon: 'folder', to: '/' },
  ];
  const active = (to: string) => (to === '/' ? loc.pathname === '/' || loc.pathname === '/dashboard' : loc.pathname.startsWith(to.split('/').slice(0, 2).join('/')));
  return (
    <div className="relative z-[80] border-b border-ink-700 bg-ink-950" style={{ paddingLeft: 'max(12px, env(safe-area-inset-left, 0px))', paddingRight: 'max(12px, env(safe-area-inset-right, 0px))' }}>
      <div className="mx-auto flex max-w-6xl items-center gap-2 py-2">
        <span className="hidden sm:inline">
          <Logo />
        </span>
        <span className="sm:hidden">
          <Logo compact />
        </span>
        <span className="chip ml-1 border-brass-500/60 text-brass-300">Vorschau</span>
        <div className="ml-auto flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.label}
              disabled={!code && t.label !== 'Fälle'}
              onClick={() => nav(t.to)}
              className={`btn-sm flex-col !gap-0.5 sm:flex-row ${active(t.to) ? 'btn-secondary' : 'btn-ghost'}`}
            >
              <Icon name={t.icon} />
              <span className="text-[10px] sm:text-xs">{t.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Home() {
  const nav = useNavigate();
  const [name, setName] = useState(game.data?.myName ?? '');
  const running = game.def;
  return (
    <main className="mx-auto max-w-6xl space-y-6 py-6" style={{ paddingLeft: 'max(16px, env(safe-area-inset-left, 0px))', paddingRight: 'max(16px, env(safe-area-inset-right, 0px))' }}>
      <section className="space-y-3">
        <div className="label !text-blood-300">Interaktive Kriminalfälle für Twitch</div>
        <h1 className="font-display text-4xl font-bold leading-tight md:text-5xl">
          Dein Chat ist <span className="italic text-blood-400">das Ermittlerteam.</span>
        </h1>
        <p className="max-w-2xl text-ink-300">
          Wähle einen Fall. Oben wechselst du jederzeit zwischen der Ansicht der Zuschauer, dem Kontrollzentrum des Streamers und dem OBS-Overlay. Diese Vorschau läuft komplett in deinem Browser; Twitch-Chat und Mitspieler auf anderen Geräten gibt es in der vollständigen Version.
        </p>
      </section>
      {running && (
        <div className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="label">Laufende Ermittlung</div>
            <div className="font-display text-xl font-bold">{running.title}</div>
          </div>
          <button className="btn-primary" onClick={() => nav(`/play/${game.data!.code}`)}>
            <Icon name="play" /> Weiter ermitteln
          </button>
        </div>
      )}
      <div className="card max-w-md p-4">
        <label htmlFor="demo-name" className="label mb-1 block">
          Dein Ermittlername
        </label>
        <input id="demo-name" className="input" maxLength={24} placeholder="z. B. Sherlock" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CASES.map((c) => (
          <article key={c.id} className="card flex flex-col overflow-hidden">
            <div className="h-1.5" style={{ background: `linear-gradient(90deg, ${c.accent}, #b3262e)` }} />
            <div className="flex flex-1 flex-col p-4">
              <div className="flex flex-wrap gap-1.5">
                <DifficultyBadge difficulty={c.difficulty} />
                <GenreBadge genre={c.genre} />
              </div>
              <h2 className="mt-3 font-display text-xl font-bold">{c.title}</h2>
              <p className="mt-1 flex-1 text-sm text-ink-300">{c.tagline}</p>
              <div className="mt-3 text-[11px] text-ink-400">
                {c.characters.filter((x) => x.role === 'suspect').length} Verdächtige · {c.evidence.length} Beweise · {c.puzzles.length} Rätsel · ca. {c.estimatedMinutes} Min.
              </div>
              <button
                className="btn-primary mt-3"
                onClick={() => {
                  game.newGame(c.id, name.trim() || 'Ermittler');
                  nav(`/play/${game.data!.code}`);
                }}
              >
                {running?.id === c.id ? 'Neu beginnen' : 'Fall starten'}
              </button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}

function Play() {
  const loc = useLocation();
  const code = loc.pathname.split('/')[2] ?? '';
  return <Investigation code={code} guestName={game.data?.myName} />;
}

function OverlayDemo() {
  // Das Overlay ist für 1920×1080 gebaut; auf schmalen Bildschirmen wird es verkleinert.
  const [scale] = useState(() => Math.min(1, window.innerWidth / 560));
  return (
    <div className="relative overflow-hidden" style={{ height: 'calc(100dvh - 64px)', background: 'radial-gradient(800px 500px at 30% 40%, #2a3340, #0b0d12 70%)' }}>
      <div className="absolute bottom-3 left-4 right-4 z-0 hidden text-xs text-ink-400 sm:block">So sieht das Overlay über deinem Stream aus. In OBS ist der Hintergrund durchsichtig.</div>
      <div style={{ transform: `scale(${scale})`, transformOrigin: 'top left', width: `${100 / scale}%`, height: `${100 / scale}%`, position: 'relative' }}>
        <Overlay />
      </div>
    </div>
  );
}

function App() {
  const start = game.data ? `/play/${game.data.code}` : '/';
  return (
    <LocalTransportContext.Provider value={game}>
      <MemoryRouter initialEntries={[start]}>
        <ToastProvider>
          <DemoBar />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/dashboard" element={<Home />} />
            <Route path="/play/:code" element={<Play />} />
            <Route path="/control/:id" element={<Control />} />
            <Route path="/overlay/:token" element={<OverlayDemo />} />
            <Route path="*" element={<Home />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </LocalTransportContext.Provider>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
