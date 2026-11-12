import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Icon, Logo } from '../components/ui';
import { api, type AppConfig, type MeResponse } from '../lib/api';

export default function Landing() {
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [code, setCode] = useState('');
  const [dev, setDev] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();
  useEffect(() => {
    void api<AppConfig>('/config').then(setCfg);
    void api<MeResponse>('/me').then(setMe);
  }, []);
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5">
        <Logo />
        {me?.streamer && (
          <Link className="btn-secondary btn-sm" to="/dashboard">
            Zum Dashboard
          </Link>
        )}
      </header>
      <main className="mx-auto grid max-w-6xl gap-10 px-4 pb-16 pt-6 lg:grid-cols-[1.2fr_1fr] lg:pt-14">
        <section>
          <div className="label !text-blood-300">Interaktive Kriminalfälle für Twitch</div>
          <h1 className="mt-3 font-display text-4xl font-bold leading-[1.05] md:text-6xl">
            Dein Chat ist
            <br />
            <span className="italic text-blood-400">das Ermittlerteam.</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg text-ink-300">
            Du leitest den Fall. Deine Community untersucht Beweise, verhört Verdächtige, deckt Widersprüche auf und überführt gemeinsam den Täter – live im Stream.
          </p>
          <div className="mt-8 grid max-w-xl gap-3 sm:grid-cols-3">
            {[
              ['search', 'Echte Fälle', 'Logisch konstruiert, fair lösbar – mit falschen Fährten und Wendungen.'],
              ['users', 'Für große Chats', 'Abstimmungen, Theorien und Teams – geschützt gegen Spam und Bots.'],
              ['eye', 'OBS-Overlay', 'Elegantes Overlay mit Abstimmungen, Fokus und Auflösung.'],
            ].map(([icon, t, d]) => (
              <div key={t} className="card p-4">
                <Icon name={icon} className="h-5 w-5 text-blood-400" />
                <div className="mt-2 font-semibold">{t}</div>
                <div className="mt-1 text-xs text-ink-400">{d}</div>
              </div>
            ))}
          </div>
        </section>
        <section className="space-y-5">
          <form
            className="paper relative px-6 py-6"
            onSubmit={(e) => {
              e.preventDefault();
              if (code.trim()) nav(`/play/${code.trim().toUpperCase()}`);
            }}
          >
            <span className="stamp mb-2 text-xs md:absolute md:right-4 md:top-4 md:mb-0">Zuschauer</span>
            <div className="font-display text-2xl font-bold">Einer Ermittlung beitreten</div>
            <p className="mt-1 font-typewriter text-sm">Den Code zeigt der Streamer im Stream an.</p>
            <div className="mt-4 flex gap-2">
              <input
                className="w-full rounded-md border-2 border-paper-ink/30 bg-paper-50 px-3 py-2 font-mono text-xl uppercase tracking-[0.3em] text-paper-ink outline-none focus:border-blood-500"
                placeholder="CODE"
                maxLength={8}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                aria-label="Beitrittscode"
              />
              <button className="btn-primary">Los</button>
            </div>
          </form>
          <div className="card space-y-3 p-6">
            <div className="font-display text-xl font-bold">Für Streamer</div>
            {cfg?.twitchEnabled && (
              <a className="btn w-full bg-[#9146ff] text-white hover:bg-[#a970ff]" href="/api/auth/twitch/login?role=streamer&return=/dashboard">
                <Icon name="twitch" /> Mit Twitch anmelden
              </a>
            )}
            {cfg?.devLogin && (
              <form
                className="space-y-2 rounded-lg border border-dashed border-brass-500/50 p-3"
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    await api('/auth/dev/login', { body: { login: dev, role: 'streamer' } });
                    nav('/dashboard');
                  } catch (er) {
                    setErr((er as Error).message);
                  }
                }}
              >
                <div className="label !text-brass-300">Lokaler Entwicklungs-Login (ohne Twitch)</div>
                <div className="flex gap-2">
                  <input className="input" placeholder="streamer_name" value={dev} onChange={(e) => setDev(e.target.value)} />
                  <button className="btn-secondary" disabled={dev.length < 3}>
                    Anmelden
                  </button>
                </div>
                {err && <div className="text-xs text-blood-300">{err}</div>}
              </form>
            )}
            {cfg && !cfg.twitchEnabled && !cfg.devLogin && <p className="text-sm text-ink-400">Twitch-Anmeldung ist auf diesem Server nicht konfiguriert.</p>}
          </div>
        </section>
      </main>
      <footer className="border-t border-ink-800 py-6 text-center text-xs text-ink-500">COMMUNITY DETECTIVES · Alle Fälle, Personen und Orte sind frei erfunden.</footer>
    </div>
  );
}
