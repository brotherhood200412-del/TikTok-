import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { DIFFICULTY_LABEL, DIFFICULTY_LEVEL, GENRE_LABEL, initials } from '../lib/format';
import type { ConnStatus } from '../lib/live';

/* ------------------------------ Icons ------------------------------ */
const paths: Record<string, string> = {
  search: 'M11 4a7 7 0 1 0 4.2 12.6l4.1 4.1 1.4-1.4-4.1-4.1A7 7 0 0 0 11 4Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z',
  folder: 'M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Z',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0H5Z',
  users: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm7.5 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2 20a7 7 0 0 1 14 0H2Zm15 0a8.5 8.5 0 0 0-2.4-5.9A5.5 5.5 0 0 1 22 20h-5Z',
  link: 'M10.6 13.4a1 1 0 0 0 1.4 0l4.6-4.6a3 3 0 0 0-4.2-4.2l-1.6 1.6 1.4 1.4 1.6-1.6a1 1 0 1 1 1.4 1.4L10.6 12a1 1 0 0 0 0 1.4ZM13.4 10.6a1 1 0 0 0-1.4 0l-4.6 4.6a3 3 0 0 0 4.2 4.2l1.6-1.6-1.4-1.4-1.6 1.6a1 1 0 1 1-1.4-1.4L13.4 12a1 1 0 0 0 0-1.4Z',
  puzzle: 'M10 3a2 2 0 0 1 2 2v1h4a1 1 0 0 1 1 1v4h1a2 2 0 1 1 0 4h-1v4a1 1 0 0 1-1 1h-4v-1a2 2 0 1 0-4 0v1H4a1 1 0 0 1-1-1v-4h1a2 2 0 1 0 0-4H3V7a1 1 0 0 1 1-1h4V5a2 2 0 0 1 2-2Z',
  vote: 'M4 13h4v7H4v-7Zm6-9h4v16h-4V4Zm6 5h4v11h-4V9Z',
  bulb: 'M12 2a7 7 0 0 0-4 12.7V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.3A7 7 0 0 0 12 2ZM9 20h6v2H9v-2Z',
  clock: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5v5.4l3.3 3.3-1.4 1.4L11 13.2V7h2Z',
  chat: 'M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9l-5 4v-4H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z',
  play: 'M7 4v16l13-8L7 4Z',
  pause: 'M6 4h4v16H6V4Zm8 0h4v16h-4V4Z',
  eye: 'M12 5c5 0 9 4.5 10 7-1 2.5-5 7-10 7S3 14.5 2 12c1-2.5 5-7 10-7Zm0 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
  eyeoff: 'M3.3 2 2 3.3l3.2 3.2C3.6 7.8 2.5 9.6 2 12c1 2.5 5 7 10 7 1.9 0 3.6-.6 5.1-1.5l3.6 3.6 1.3-1.3L3.3 2ZM12 5c5 0 9 4.5 10 7-.4 1-1.3 2.4-2.6 3.7L16 12.3A4 4 0 0 0 11.7 8L8.9 5.4C9.9 5.1 10.9 5 12 5Z',
  lock: 'M7 10V7a5 5 0 0 1 10 0v3h1a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h1Zm2 0h6V7a3 3 0 0 0-6 0v3Z',
  star: 'm12 2 3 6.6 7 .7-5.3 4.8 1.6 7L12 17.5 5.7 21l1.6-7L2 9.3l7-.7L12 2Z',
  pin: 'M14 2l8 8-3 1-4 4 1 5-2 2-4.5-4.5L4 23l-1-1 5.5-5.5L4 12l2-2 5 1 4-4 1-3Z',
  alert: 'M12 2 1 21h22L12 2Zm-1 7h2v6h-2V9Zm0 8h2v2h-2v-2Z',
  check: 'm9 16.2-4.2-4.2-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2Z',
  x: 'm6.4 5 5.6 5.6L17.6 5 19 6.4 13.4 12l5.6 5.6-1.4 1.4-5.6-5.6L6.4 19 5 17.6 10.6 12 5 6.4 6.4 5Z',
  doc: 'M6 2h8l6 6v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1Zm7 1.5V9h5.5L13 3.5ZM8 13h8v2H8v-2Zm0 4h8v2H8v-2Z',
  scale: 'M11 3h2v2h6l2 7a4 4 0 0 1-8 0l2-5h-2v13h4v2H7v-2h4V7H9l2 5a4 4 0 0 1-8 0l2-7h6V3Z',
  timeline: 'M3 11h18v2H3v-2Zm3-5h2v12H6V6Zm5 3h2v6h-2V9Zm5-4h2v14h-2V5Z',
  copy: 'M8 3h11a1 1 0 0 1 1 1v13h-2V5H8V3ZM4 7h11a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1Z',
  logout: 'M10 3h9a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1h-9v-2h8V5h-8V3Zm-.6 5.4L6.8 11H15v2H6.8l2.6 2.6L8 17l-5-5 5-5 1.4 1.4Z',
  bolt: 'M13 2 4 14h7l-1 8 9-12h-7l1-8Z',
  trophy: 'M7 3h10v3h3v3a4 4 0 0 1-4 4h-.3A5 5 0 0 1 13 15.9V18h3v3H8v-3h3v-2.1A5 5 0 0 1 8.3 13H8a4 4 0 0 1-4-4V6h3V3Zm10 5v3a2 2 0 0 0 1-1.7V8h-1ZM6 8v1.3A2 2 0 0 0 7 11V8H6Z',
  shield: 'M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z',
  mic: 'M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3Zm-7 9h2a5 5 0 0 0 10 0h2a7 7 0 0 1-6 6.9V21h-2v-3.1A7 7 0 0 1 5 11Z',
  map: 'M9 3 3 5v16l6-2 6 2 6-2V3l-6 2-6-2Zm0 2.2 6 2v11.6l-6-2V5.2Z',
  plus: 'M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z',
  dice: 'M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm3 3.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Zm8 8a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Zm-4-4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z',
  twitch: 'M4 3 3 6v13h4v3h3l3-3h3l5-5V3H4Zm15 10-3 3h-4l-3 3v-3H6V5h13v8Zm-3-6h-2v5h2V7Zm-5 0H9v5h2V7Z',
};
export function Icon({ name, className = 'h-4 w-4' }: { name: keyof typeof paths | string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d={paths[name] ?? paths.search} />
    </svg>
  );
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg viewBox="0 0 64 64" className="h-7 w-7" aria-hidden="true">
        <circle cx="27" cy="27" r="14" fill="none" stroke="#efe6d2" strokeWidth="5" />
        <path d="M37 37l14 14" stroke="#b3262e" strokeWidth="7" strokeLinecap="round" />
      </svg>
      {!compact && (
        <span className="leading-none">
          <span className="block font-display text-[15px] font-bold tracking-[0.18em] text-ink-100">COMMUNITY</span>
          <span className="block text-[10px] font-semibold tracking-[0.42em] text-blood-400">DETECTIVES</span>
        </span>
      )}
    </span>
  );
}

/* ------------------------------ Toasts ------------------------------ */
interface Toast {
  id: number;
  text: string;
  tone: 'info' | 'success' | 'error' | 'discovery';
  title?: string;
}
const ToastCtx = createContext<(t: Omit<Toast, 'id'>) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((t: Omit<Toast, 'id'>) => {
    const id = Date.now() + Math.random();
    setToasts((l) => [...l.slice(-3), { ...t, id }]);
    setTimeout(() => setToasts((l) => l.filter((x) => x.id !== id)), t.tone === 'discovery' ? 6000 : 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-14 z-[60] flex flex-col items-center gap-2 px-4 md:top-auto md:bottom-6 md:items-end" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto w-full max-w-sm animate-fade-up rounded-lg border px-4 py-3 text-sm shadow-2xl ${
              t.tone === 'error'
                ? 'border-blood-600 bg-blood-800/95 text-white'
                : t.tone === 'success'
                  ? 'border-ok-600 bg-ink-800/95 text-ink-100'
                  : t.tone === 'discovery'
                    ? 'border-brass-500/70 bg-ink-850/95 text-ink-100'
                    : 'border-ink-600 bg-ink-800/95 text-ink-100'
            }`}
          >
            {t.title && <div className={`label mb-0.5 ${t.tone === 'discovery' ? '!text-brass-300' : ''}`}>{t.title}</div>}
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ------------------------------ Modal ------------------------------ */
export function Modal({ open, onClose, title, children, wide = false }: { open: boolean; onClose: () => void; title?: ReactNode; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', h);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', h);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm md:items-center md:p-6" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className={`card flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-b-none md:rounded-xl ${wide ? 'md:max-w-5xl' : 'md:max-w-xl'} animate-fade-up`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-ink-700 px-4 py-3">
          <div className="min-w-0 font-display text-lg font-bold">{title}</div>
          <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Schließen">
            <Icon name="x" />
          </button>
        </div>
        <div className="scroll-thin overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  );
}

/* ------------------------------ Kleinteile ------------------------------ */
export function DifficultyBadge({ difficulty }: { difficulty: string }) {
  const lvl = DIFFICULTY_LEVEL[difficulty] ?? 1;
  return (
    <span className="chip border-ink-600 bg-ink-800 text-ink-200" title={`Schwierigkeit: ${DIFFICULTY_LABEL[difficulty]}`}>
      <span className="flex gap-0.5">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={`h-2 w-1 rounded-sm ${i <= lvl ? 'bg-blood-400' : 'bg-ink-600'}`} />
        ))}
      </span>
      {DIFFICULTY_LABEL[difficulty] ?? difficulty}
    </span>
  );
}

export function GenreBadge({ genre }: { genre: string }) {
  return <span className="chip border-ink-600 text-ink-300">{GENRE_LABEL[genre] ?? genre}</span>;
}

export function Avatar({ name, color, size = 40, stress = 0 }: { name: string; color: string; size?: number; stress?: number }) {
  return (
    <div
      className="relative flex shrink-0 items-center justify-center rounded-full font-display font-bold text-paper-50"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.36,
        background: `radial-gradient(circle at 30% 25%, ${color}, #111 120%)`,
        boxShadow: stress > 60 ? '0 0 0 2px #d23a3a' : stress > 30 ? '0 0 0 2px #c9a45c' : '0 0 0 1px rgb(255 255 255 / 0.1)',
      }}
    >
      {initials(name)}
    </div>
  );
}

export function Progress({ value, max, className = '' }: { value: number; max: number; className?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-ink-700 ${className}`} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full bg-gradient-to-r from-blood-600 to-blood-400 transition-all duration-700" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ConnectionBanner({ status, error }: { status: ConnStatus; error: { message: string } | null }) {
  if (status === 'online') return null;
  if (status === 'fatal') return null;
  return (
    <div className="fixed inset-x-0 top-0 z-[70] flex justify-center p-2">
      <div className="flex items-center gap-2 rounded-full border border-brass-500/50 bg-ink-850/95 px-4 py-1.5 text-xs text-brass-300 shadow-xl">
        <span className="h-2 w-2 animate-pulse rounded-full bg-brass-400" />
        {status === 'connecting' ? 'Verbinde …' : 'Verbindung unterbrochen – wird automatisch wiederhergestellt …'}
        {error && status !== 'connecting' && <span className="hidden text-ink-400 md:inline">({error.message})</span>}
      </div>
    </div>
  );
}

export function Empty({ icon = 'search', title, children }: { icon?: string; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-ink-600 px-6 py-10 text-center">
      <Icon name={icon} className="h-7 w-7 text-ink-500" />
      <div className="font-display text-base font-semibold text-ink-200">{title}</div>
      {children && <div className="max-w-sm text-sm text-ink-400">{children}</div>}
    </div>
  );
}

export function Section({ title, icon, action, children, className = '' }: { title: ReactNode; icon?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card p-4 ${className}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-display text-base font-bold text-ink-100">
          {icon && <Icon name={icon} className="h-4 w-4 text-blood-400" />}
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-3 py-1.5">
      <span>
        <span className="text-sm text-ink-100">{label}</span>
        {hint && <span className="block text-xs text-ink-400">{hint}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition ${checked ? 'bg-blood-500' : 'bg-ink-600'}`}
      >
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition ${checked ? 'left-[18px]' : 'left-0.5'}`} />
      </button>
    </label>
  );
}

export function CopyField({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div>
      {label && <div className="label mb-1">{label}</div>}
      <div className="flex gap-2">
        <input className="input font-mono text-xs" readOnly value={value} onFocus={(e) => e.currentTarget.select()} />
        <button
          className="btn-secondary btn-sm"
          onClick={() => {
            void navigator.clipboard?.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          <Icon name={copied ? 'check' : 'copy'} /> {copied ? 'Kopiert' : 'Kopieren'}
        </button>
      </div>
    </div>
  );
}

export function Spinner() {
  return <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-ink-500 border-t-blood-400" />;
}

export function FullPageMessage({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 p-6 text-center">
      <Logo />
      <h1 className="title-display text-2xl">{title}</h1>
      {children && <div className="max-w-md text-ink-300">{children}</div>}
    </div>
  );
}
