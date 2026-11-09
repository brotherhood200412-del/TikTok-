import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { DifficultyBadge, FullPageMessage, GenreBadge, Icon, Logo, Section, Spinner, useToast } from '../components/ui';
import { api } from '../lib/api';

interface AdminCase {
  id: string;
  title: string;
  version: number;
  genre: string;
  difficulty: string;
  tier: string;
  published: boolean;
  exclusive: boolean;
  eventTag: string | null;
  importedAt: string;
  sessions: number;
  reservations: string[];
  validation: { ok: boolean; errors: string[]; warnings: string[]; stats: Record<string, number> };
}

export default function Admin() {
  const [cases, setCases] = useState<AdminCase[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const toast = useToast();
  const load = useCallback(() => api<{ cases: AdminCase[] }>('/admin/cases').then((r) => setCases(r.cases)).catch((e) => setError(e.message)), []);
  useEffect(() => void load(), [load]);
  if (error) return <FullPageMessage title="Kein Zugriff">{error}</FullPageMessage>;
  if (!cases) return <FullPageMessage title="Lade Fallverwaltung …"><Spinner /></FullPageMessage>;
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6">
      <header className="flex items-center justify-between">
        <Link to="/dashboard"><Logo /></Link>
        <button
          className="btn-secondary btn-sm"
          onClick={async () => {
            const r = await api<{ results: { id: string; ok: boolean }[] }>('/admin/cases/import', { body: {} });
            toast({ tone: 'success', text: `${r.results.filter((x) => x.ok).length}/${r.results.length} Fälle gültig importiert.` });
            void load();
          }}
        >
          <Icon name="folder" /> Fälle neu importieren & validieren
        </button>
      </header>
      <Section title="Fallverwaltung & Qualitätssicherung" icon="shield">
        <p className="mb-4 text-sm text-ink-400">Fälle liegen als YAML in <code>content/cases/</code>. Nur Fälle ohne Validierungsfehler können veröffentlicht werden.</p>
        <div className="space-y-3">
          {cases.map((c) => (
            <div key={c.id} className="card-inset p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-display text-lg font-bold">{c.title} <span className="text-xs text-ink-500">v{c.version} · {c.id}</span></div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    <DifficultyBadge difficulty={c.difficulty} />
                    <GenreBadge genre={c.genre} />
                    <span className="chip border-ink-600 text-ink-300">{c.tier}</span>
                    {c.exclusive && <span className="chip border-blood-500 text-blood-300">Exklusiv: {c.eventTag}</span>}
                    <span className={`chip ${c.validation.ok ? 'border-ok-600 text-ok-400' : 'border-blood-500 text-blood-300'}`}>{c.validation.ok ? 'Validiert' : `${c.validation.errors.length} Fehler`}</span>
                    {c.validation.warnings.length > 0 && <span className="chip border-brass-500 text-brass-300">{c.validation.warnings.length} Hinweise</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-ink-400">{c.sessions}× gespielt</span>
                  <button className="btn-ghost btn-sm" onClick={() => setOpen(open === c.id ? null : c.id)}>Bericht</button>
                  <button
                    className={c.published ? 'btn-secondary btn-sm' : 'btn-primary btn-sm'}
                    onClick={async () => {
                      try {
                        await api(`/admin/cases/${c.id}/publish`, { body: { published: !c.published } });
                        void load();
                      } catch (e) {
                        toast({ tone: 'error', text: (e as Error).message });
                      }
                    }}
                  >
                    {c.published ? 'Zurückziehen' : 'Veröffentlichen'}
                  </button>
                </div>
              </div>
              {open === c.id && (
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex flex-wrap gap-3 text-xs text-ink-300">
                    {Object.entries(c.validation.stats).map(([k, v]) => <span key={k}>{k}: <b>{v}</b></span>)}
                  </div>
                  {c.validation.errors.map((e, i) => <div key={i} className="text-blood-300">✘ {e}</div>)}
                  {c.validation.warnings.map((w, i) => <div key={i} className="text-brass-300">⚠ {w}</div>)}
                  {c.validation.ok && c.validation.warnings.length === 0 && <div className="text-ok-400">Keine Auffälligkeiten.</div>}
                  <ReservationForm caseId={c.id} reservations={c.reservations} onDone={load} />
                </div>
              )}
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

function ReservationForm({ caseId, reservations, onDone }: { caseId: string; reservations: string[]; onDone: () => void }) {
  const [login, setLogin] = useState('');
  const toast = useToast();
  return (
    <form
      className="flex flex-wrap items-center gap-2 border-t border-ink-700 pt-2"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await api('/admin/reservations', { body: { caseId, login } });
          setLogin('');
          onDone();
        } catch (er) {
          toast({ tone: 'error', text: (er as Error).message });
        }
      }}
    >
      <span className="text-xs text-ink-400">Reserviert für: {reservations.join(', ') || '–'}</span>
      <input className="input max-w-48" placeholder="streamer_login" value={login} onChange={(e) => setLogin(e.target.value)} />
      <button className="btn-secondary btn-sm">Reservieren</button>
    </form>
  );
}
