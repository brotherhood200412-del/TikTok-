import { useEffect, useMemo, useState } from 'react';
import type { EvidenceContent } from '../../../shared/case/schema';
import type { PublicEvidence, PublicInsight } from '../../../shared/views';
import { Icon } from './ui';

export const EVIDENCE_ICON: Record<string, string> = { document: 'doc', photo: 'eye', audio: 'mic', map: 'map', messages: 'chat', table: 'timeline', object: 'search' };
export const EVIDENCE_KIND_LABEL: Record<string, string> = {
  document: 'Dokument',
  photo: 'Foto',
  audio: 'Tonaufnahme',
  map: 'Karte',
  messages: 'Nachrichten',
  table: 'Protokoll',
  object: 'Gegenstand',
};

interface Props {
  evidence: PublicEvidence;
  insights: Map<string, PublicInsight>;
  onMark?: (itemId: string) => Promise<void> | void;
  /** Streamer-Ansicht: Hotspots hervorheben */
  hotspotItems?: Set<string>;
  busy?: boolean;
}

/** Interaktive Darstellung eines Beweisstücks mit markierbaren Details. */
export function EvidenceViewer({ evidence, insights, onMark, hotspotItems, busy }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => setSelected(null), [evidence.id]);
  const c = evidence.content;
  const found = evidence.found;
  const detail = useMemo(() => itemDetail(c, selected), [c, selected]);

  const itemClass = (id: string) =>
    `${found[id] ? 'hotspot-found bg-blood-500/10' : ''} ${selected === id ? 'bg-brass-400/25' : ''} ${hotspotItems?.has(id) ? 'ring-1 ring-brass-400/80' : ''}`;

  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-300">{evidence.summary}</p>
      <div className="label flex items-center gap-2">
        <Icon name={EVIDENCE_ICON[c.kind]} className="h-3.5 w-3.5" /> {EVIDENCE_KIND_LABEL[c.kind]} · Quelle: {evidence.source}
      </div>

      {c.kind === 'photo' && <PhotoScene content={c} selected={selected} found={found} hotspots={hotspotItems} onSelect={setSelected} />}
      {c.kind === 'map' && <MapView content={c} selected={selected} found={found} hotspots={hotspotItems} onSelect={setSelected} />}

      {c.kind === 'document' && (
        <div className="paper paper-lines relative px-5 py-5 font-typewriter text-[15px] leading-7 md:px-8">
          {c.heading && <div className="mb-2 border-b border-paper-faded/30 pb-2 font-display text-lg font-bold tracking-wide">{c.heading}</div>}
          {c.meta.length > 0 && (
            <div className="mb-3 grid gap-x-4 text-sm sm:grid-cols-2">
              {c.meta.map((m) => (
                <div key={m.label}>
                  <span className="text-paper-faded">{m.label}:</span> {m.value}
                </div>
              ))}
            </div>
          )}
          {c.lines.map((l) => (
            <button key={l.id} type="button" onClick={() => setSelected(l.id)} className={`block w-full rounded px-1 text-left transition hover:bg-paper-200/70 ${itemClass(l.id)}`}>
              {l.text || ' '}
            </button>
          ))}
          {c.footer && <div className="mt-3 text-right text-sm italic text-paper-faded">{c.footer}</div>}
          {c.docType === 'statement' && <span className="stamp mb-2 text-xs md:absolute md:right-4 md:top-3 md:mb-0">Aussage</span>}
          {c.docType === 'report' && <span className="stamp mb-2 text-xs md:absolute md:right-4 md:top-3 md:mb-0">Vertraulich</span>}
        </div>
      )}

      {c.kind === 'table' && (
        <div className="paper overflow-x-auto px-3 py-4 md:px-5">
          <div className="mb-2 font-display text-base font-bold">{c.heading}</div>
          <table className="w-full min-w-[420px] border-collapse font-typewriter text-sm">
            <thead>
              <tr>
                {c.columns.map((col) => (
                  <th key={col} className="border-b-2 border-paper-ink/40 px-2 py-1 text-left font-semibold">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {c.rows.map((r) => (
                <tr key={r.id} onClick={() => setSelected(r.id)} className={`cursor-pointer border-b border-paper-faded/20 hover:bg-paper-200/70 ${itemClass(r.id)}`}>
                  {r.cells.map((cell, i) => (
                    <td key={i} className="px-2 py-1.5 align-top">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {c.note && <div className="mt-2 text-xs italic text-paper-faded">{c.note}</div>}
        </div>
      )}

      {c.kind === 'audio' && <AudioPlayer content={c} itemClass={itemClass} onSelect={setSelected} />}

      {c.kind === 'messages' && (
        <div className="mx-auto max-w-md rounded-[28px] border-4 border-ink-700 bg-ink-950 p-3">
          <div className="mb-2 flex items-center justify-between px-2 text-xs text-ink-400">
            <span>{c.app}</span>
            <span>Gerät: {c.owner}</span>
          </div>
          <div className="space-y-2">
            {c.messages.map((m) => {
              const mine = m.from === c.owner;
              return (
                <button key={m.id} type="button" onClick={() => setSelected(m.id)} className={`flex w-full ${mine ? 'justify-end' : 'justify-start'}`}>
                  <span className={`max-w-[85%] rounded-2xl px-3 py-2 text-left text-sm ${mine ? 'bg-blood-700 text-white' : 'bg-ink-700 text-ink-100'} ${itemClass(m.id)}`}>
                    {!mine && <span className="block text-[11px] font-semibold text-brass-300">{m.from}</span>}
                    {m.text}
                    <span className="mt-0.5 block text-right text-[10px] opacity-70">{m.time}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {c.kind === 'object' && (
        <div className="card-inset space-y-2 p-4">
          <p className="text-sm text-ink-200">{c.description}</p>
          <ul className="space-y-1">
            {c.details.map((d) => (
              <li key={d.id}>
                <button type="button" onClick={() => setSelected(d.id)} className={`w-full rounded px-2 py-1 text-left text-sm hover:bg-ink-700 ${itemClass(d.id)}`}>
                  • {d.text}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Detailleiste + Markieren */}
      <div className="sticky bottom-0 -mx-4 border-t border-ink-700 bg-ink-850/95 px-4 py-3 backdrop-blur">
        {selected ? (
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0 text-sm">
              {detail?.label && <div className="font-semibold text-ink-100">{detail.label}</div>}
              {detail?.text && <div className="text-ink-300">{detail.text}</div>}
              {found[selected] && (
                <div className="mt-1 text-xs font-semibold text-blood-300">
                  <Icon name="check" className="mr-1 inline h-3 w-3" />
                  Gesichert: {insights.get(found[selected])?.title ?? 'Erkenntnis'}
                </div>
              )}
            </div>
            {onMark && !found[selected] && (
              <button className="btn-primary shrink-0" disabled={busy} onClick={() => void onMark(selected)}>
                <Icon name="pin" /> Als verdächtig markieren
              </button>
            )}
          </div>
        ) : (
          <div className="text-xs text-ink-400">
            {onMark ? 'Tippe auf ein Detail, um es genauer anzusehen. Fällt dir etwas auf? Markiere es – richtige Funde werden für alle gesichert.' : 'Element auswählen für Details.'}
          </div>
        )}
      </div>
    </div>
  );
}

function itemDetail(c: EvidenceContent, id: string | null): { label?: string; text?: string } | null {
  if (!id) return null;
  switch (c.kind) {
    case 'photo': {
      const e = c.elements.find((x) => x.id === id);
      return e ? { label: e.label, text: e.detail } : null;
    }
    case 'map': {
      const p = c.places.find((x) => x.id === id);
      if (p) return { label: p.label, text: p.detail };
      const r = c.routes.find((x) => x.id === id);
      return r ? { label: r.label, text: r.detail } : null;
    }
    case 'document':
    case 'object': {
      const l = c.kind === 'document' ? c.lines.find((x) => x.id === id) : c.details.find((x) => x.id === id);
      return l ? { text: `„${l.text}“` } : null;
    }
    case 'audio': {
      const l = c.lines.find((x) => x.id === id);
      return l ? { label: `${l.t} · ${l.speaker}`, text: `„${l.text}“` } : null;
    }
    case 'messages': {
      const m = c.messages.find((x) => x.id === id);
      return m ? { label: `${m.from} · ${m.time}`, text: m.text } : null;
    }
    case 'table': {
      const r = c.rows.find((x) => x.id === id);
      return r ? { text: r.cells.join(' · ') } : null;
    }
  }
}

/* ------------------------------ Foto (stilisierte Tatortaufnahme) ------------------------------ */
const SCENE_BG: Record<string, [string, string, string]> = {
  interior: ['#3a3128', '#2a241e', '#4a3f33'],
  gallery: ['#3b3a37', '#2b2a28', '#57524a'],
  office: ['#2f3338', '#23272b', '#3e444a'],
  street: ['#2b3036', '#1d2125', '#3a3f44'],
  night: ['#141a24', '#0c1018', '#1f2733'],
  platform: ['#2c2f33', '#1c1e21', '#4a4d51'],
  garden: ['#25301f', '#1b2317', '#344229'],
  archive: ['#3a3326', '#28231a', '#4c4331'],
};

function PhotoScene({
  content,
  selected,
  found,
  hotspots,
  onSelect,
}: {
  content: Extract<EvidenceContent, { kind: 'photo' }>;
  selected: string | null;
  found: Record<string, string>;
  hotspots?: Set<string>;
  onSelect: (id: string) => void;
}) {
  const [wall, floor, accent] = SCENE_BG[content.scene] ?? SCENE_BG.interior;
  const [zoom, setZoom] = useState(false);
  return (
    <figure className="mx-auto max-w-3xl rotate-[-0.4deg] bg-paper-50 p-2 pb-8 shadow-[var(--shadow-paper)] md:p-3 md:pb-10">
      <div className={`relative overflow-hidden ${zoom ? 'cursor-zoom-out' : ''}`}>
        <svg viewBox="0 0 100 70" className={`block w-full transition-transform duration-300 ${zoom ? 'scale-[1.6] origin-center' : ''}`} role="img" aria-label={content.caption}>
          <defs>
            <linearGradient id="wallg" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor={wall} />
              <stop offset="1" stopColor={floor} />
            </linearGradient>
            <radialGradient id="vignette" cx="0.5" cy="0.45" r="0.75">
              <stop offset="0.55" stopColor="#000" stopOpacity="0" />
              <stop offset="1" stopColor="#000" stopOpacity="0.65" />
            </radialGradient>
            <filter id="grain">
              <feTurbulence type="fractalNoise" baseFrequency="1.6" numOctaves="2" stitchTiles="stitch" />
              <feColorMatrix type="saturate" values="0" />
              <feComponentTransfer>
                <feFuncA type="table" tableValues="0 0.12" />
              </feComponentTransfer>
              <feBlend in2="SourceGraphic" mode="overlay" />
            </filter>
          </defs>
          <rect width="100" height="70" fill="url(#wallg)" />
          {['interior', 'gallery', 'office', 'archive'].includes(content.scene) && <rect y="48" width="100" height="22" fill={floor} opacity="0.85" />}
          {['street', 'night', 'platform', 'garden'].includes(content.scene) && <rect y="52" width="100" height="18" fill={accent} opacity="0.45" />}
          {content.scene === 'platform' && <rect y="50" width="100" height="1.2" fill="#c9a45c" opacity="0.7" />}
          {content.elements.map((e) => {
            const isSel = selected === e.id;
            const isFound = !!found[e.id];
            const isHot = hotspots?.has(e.id);
            const x = e.x;
            const y = (e.y / 100) * 70;
            const w = e.w;
            const h = (e.h / 100) * 70;
            return (
              <g key={e.id} className="cursor-pointer" onClick={() => onSelect(e.id)} role="button" aria-label={e.label} tabIndex={0} onKeyDown={(ev) => ev.key === 'Enter' && onSelect(e.id)}>
                <SceneShape shape={e.shape} x={x} y={y} w={w} h={h} accent={accent} />
                <rect x={x} y={y} width={w} height={h} fill="transparent" stroke={isFound ? '#d23a3a' : isSel ? '#e0c486' : isHot ? '#c9a45c' : 'transparent'} strokeWidth={isFound || isSel ? 0.6 : 0.35} strokeDasharray={isHot && !isFound && !isSel ? '1 0.8' : undefined} rx="0.8" />
                <rect x={x} y={y} width={w} height={h} fill="#fff" opacity="0" className="transition-opacity hover:opacity-10" />
              </g>
            );
          })}
          <rect width="100" height="70" fill="url(#vignette)" pointerEvents="none" />
          <rect width="100" height="70" filter="url(#grain)" opacity="0.6" pointerEvents="none" fill="transparent" />
          {content.timestamp && (
            <text x="97" y="67" textAnchor="end" fontSize="2.6" fill="#f2a33a" fontFamily="monospace" opacity="0.9" pointerEvents="none">
              {content.timestamp}
            </text>
          )}
        </svg>
        <button type="button" className="btn-secondary btn-sm absolute right-2 top-2 opacity-90" onClick={() => setZoom((z) => !z)}>
          <Icon name="search" /> {zoom ? 'Normal' : 'Zoom'}
        </button>
      </div>
      <figcaption className="mt-2 text-center font-typewriter text-sm text-paper-ink">{content.caption}</figcaption>
      <div className="mt-2 flex flex-wrap justify-center gap-1.5">
        {content.elements.map((e) => (
          <button
            key={e.id}
            type="button"
            onClick={() => onSelect(e.id)}
            className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
              found[e.id] ? 'border-blood-500 bg-blood-500/15 text-blood-700' : selected === e.id ? 'border-paper-ink bg-paper-200 text-paper-ink' : 'border-paper-faded/40 text-paper-faded hover:bg-paper-200'
            }`}
          >
            {e.label}
          </button>
        ))}
      </div>
    </figure>
  );
}

function SceneShape({ shape, x, y, w, h, accent }: { shape: string; x: number; y: number; w: number; h: number; accent: string }) {
  const stroke = '#d8cbb0';
  const fill = '#00000033';
  const sw = 0.35;
  switch (shape) {
    case 'frame':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} fill="#00000055" stroke="#c9a45c" strokeWidth={1.2} />
          <rect x={x + 1.5} y={y + 1.5} width={w - 3} height={h - 3} fill="#1a1612" stroke="#7a6232" strokeWidth={0.3} />
        </g>
      );
    case 'window':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} fill="#7d93a855" stroke={stroke} strokeWidth={sw * 2} />
          <line x1={x + w / 2} y1={y} x2={x + w / 2} y2={y + h} stroke={stroke} strokeWidth={sw} />
          <line x1={x} y1={y + h / 2} x2={x + w} y2={y + h / 2} stroke={stroke} strokeWidth={sw} />
        </g>
      );
    case 'door':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} fill="#2a1f16" stroke={stroke} strokeWidth={sw} />
          <circle cx={x + w * 0.8} cy={y + h * 0.55} r={0.6} fill="#c9a45c" />
        </g>
      );
    case 'person':
      return (
        <g fill="#0d0d0d" opacity="0.85">
          <circle cx={x + w / 2} cy={y + h * 0.15} r={Math.min(w, h) * 0.16} />
          <path d={`M${x + w * 0.15} ${y + h} Q${x + w * 0.15} ${y + h * 0.32} ${x + w / 2} ${y + h * 0.32} Q${x + w * 0.85} ${y + h * 0.32} ${x + w * 0.85} ${y + h} Z`} />
        </g>
      );
    case 'clock':
      return (
        <g>
          <circle cx={x + w / 2} cy={y + h / 2} r={Math.min(w, h) / 2} fill="#e9e1cf" stroke="#333" strokeWidth={0.4} />
          <line x1={x + w / 2} y1={y + h / 2} x2={x + w / 2} y2={y + h * 0.18} stroke="#111" strokeWidth={0.4} />
          <line x1={x + w / 2} y1={y + h / 2} x2={x + w * 0.75} y2={y + h / 2} stroke="#111" strokeWidth={0.4} />
        </g>
      );
    case 'table':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h * 0.25} fill="#5b4632" stroke={stroke} strokeWidth={sw} />
          <rect x={x + 1} y={y + h * 0.25} width={0.8} height={h * 0.75} fill="#3b2d20" />
          <rect x={x + w - 1.8} y={y + h * 0.25} width={0.8} height={h * 0.75} fill="#3b2d20" />
        </g>
      );
    case 'paper':
      return <rect x={x} y={y} width={w} height={h} fill="#efe6d2" opacity="0.9" stroke="#bfae8a" strokeWidth={0.2} transform={`rotate(-3 ${x + w / 2} ${y + h / 2})`} />;
    case 'bag':
      return <rect x={x} y={y} width={w} height={h} rx={1.5} fill="#151515" stroke="#444" strokeWidth={sw} />;
    case 'car':
      return (
        <g>
          <rect x={x} y={y + h * 0.35} width={w} height={h * 0.45} rx={1.5} fill={accent} stroke={stroke} strokeWidth={sw} />
          <rect x={x + w * 0.2} y={y} width={w * 0.55} height={h * 0.4} rx={1.5} fill="#7d93a855" stroke={stroke} strokeWidth={sw} />
          <circle cx={x + w * 0.22} cy={y + h * 0.85} r={h * 0.13} fill="#111" />
          <circle cx={x + w * 0.78} cy={y + h * 0.85} r={h * 0.13} fill="#111" />
        </g>
      );
    case 'plant':
      return (
        <g>
          <rect x={x} y={y + h * 0.5} width={w} height={h * 0.5} fill="#3b2a1d" />
          {[0.15, 0.35, 0.55, 0.75].map((f) => (
            <circle key={f} cx={x + w * f + 1} cy={y + h * 0.45} r={Math.min(w, h) * 0.18} fill="#3f5a2f" />
          ))}
        </g>
      );
    case 'shelf':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} fill="#3a2c1f" stroke={stroke} strokeWidth={sw} />
          {[0.25, 0.5, 0.75].map((f) => (
            <line key={f} x1={x} y1={y + h * f} x2={x + w} y2={y + h * f} stroke="#1c140d" strokeWidth={0.6} />
          ))}
        </g>
      );
    case 'lamp':
      return (
        <g>
          <rect x={x + w / 2 - 0.4} y={y + h * 0.2} width={0.8} height={h * 0.8} fill="#555" />
          <path d={`M${x} ${y + h * 0.22} L${x + w / 2} ${y} L${x + w} ${y + h * 0.22} Z`} fill="#e6c87a" opacity="0.85" />
        </g>
      );
    case 'screen':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h * 0.8} rx={0.6} fill="#0b1a24" stroke="#666" strokeWidth={sw} />
          <rect x={x + w * 0.4} y={y + h * 0.8} width={w * 0.2} height={h * 0.2} fill="#444" />
        </g>
      );
    case 'bottle':
      return <path d={`M${x + w * 0.35} ${y} h${w * 0.3} v${h * 0.3} l${w * 0.2} ${h * 0.15} v${h * 0.55} h${-w * 0.7} v${-h * 0.55} l${w * 0.2} ${-h * 0.15} Z`} fill="#4b6b4a" opacity="0.85" />;
    case 'box':
      return <rect x={x} y={y} width={w} height={h} fill="#6b5236" stroke="#2b2014" strokeWidth={sw} />;
    case 'round':
      return <ellipse cx={x + w / 2} cy={y + h / 2} rx={w / 2} ry={h / 2} fill="#cfcfcf" opacity="0.7" />;
    default:
      return <rect x={x} y={y} width={w} height={h} fill={fill} stroke={stroke} strokeWidth={sw} strokeDasharray="0.8 0.6" rx={0.6} />;
  }
}

/* ------------------------------ Karte ------------------------------ */
function MapView({
  content,
  selected,
  found,
  hotspots,
  onSelect,
}: {
  content: Extract<EvidenceContent, { kind: 'map' }>;
  selected: string | null;
  found: Record<string, string>;
  hotspots?: Set<string>;
  onSelect: (id: string) => void;
}) {
  const pos = new Map(content.places.map((p) => [p.id, p]));
  return (
    <div className="paper p-3">
      <div className="mb-2 font-display text-base font-bold">{content.title}</div>
      <svg viewBox="0 0 100 70" className="w-full rounded-sm bg-paper-200/60" role="img" aria-label={content.title}>
        {[...Array(10)].map((_, i) => (
          <line key={`v${i}`} x1={i * 10} y1={0} x2={i * 10} y2={70} stroke="#6b5f4d" strokeOpacity="0.12" strokeWidth="0.2" />
        ))}
        {[...Array(7)].map((_, i) => (
          <line key={`h${i}`} x1={0} y1={i * 10} x2={100} y2={i * 10} stroke="#6b5f4d" strokeOpacity="0.12" strokeWidth="0.2" />
        ))}
        {content.routes.map((r) => {
          const a = pos.get(r.from)!;
          const b = pos.get(r.to)!;
          const sel = selected === r.id;
          return (
            <g key={r.id} onClick={() => onSelect(r.id)} className="cursor-pointer">
              <line x1={a.x} y1={a.y * 0.7} x2={b.x} y2={b.y * 0.7} stroke="transparent" strokeWidth="3" />
              <line
                x1={a.x}
                y1={a.y * 0.7}
                x2={b.x}
                y2={b.y * 0.7}
                stroke={found[r.id] ? '#b3262e' : sel ? '#a8853f' : hotspots?.has(r.id) ? '#c9a45c' : '#2b2620'}
                strokeWidth={sel || found[r.id] ? 0.8 : 0.45}
                strokeDasharray="1.2 0.8"
              />
              <text x={(a.x + b.x) / 2} y={((a.y + b.y) / 2) * 0.7 - 1} fontSize="2.2" textAnchor="middle" fill="#2b2620" fontFamily="var(--font-type)">
                {r.label}
              </text>
            </g>
          );
        })}
        {content.places.map((p) => {
          const sel = selected === p.id;
          return (
            <g key={p.id} onClick={() => onSelect(p.id)} className="cursor-pointer">
              <circle cx={p.x} cy={p.y * 0.7} r={sel ? 2.2 : 1.6} fill={found[p.id] ? '#b3262e' : hotspots?.has(p.id) ? '#c9a45c' : '#2b2620'} stroke="#f7f1e3" strokeWidth="0.4" />
              <text x={p.x} y={p.y * 0.7 + 4} fontSize="2.5" textAnchor="middle" fill="#2b2620" fontWeight="700">
                {p.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* ------------------------------ Tonaufnahme ------------------------------ */
function AudioPlayer({ content, itemClass, onSelect }: { content: Extract<EvidenceContent, { kind: 'audio' }>; itemClass: (id: string) => string; onSelect: (id: string) => void }) {
  const [shown, setShown] = useState(content.lines.length);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    if (shown >= content.lines.length) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setShown((s) => s + 1), 1600);
    return () => clearTimeout(t);
  }, [playing, shown, content.lines.length]);
  const bars = useMemo(() => Array.from({ length: 48 }, (_, i) => 20 + Math.abs(Math.sin(i * 1.7) * 60) + ((i * 37) % 20)), []);
  return (
    <div className="card-inset p-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="btn-primary h-10 w-10 !rounded-full !p-0"
          onClick={() => {
            if (!playing) setShown(0);
            setPlaying((p) => !p);
          }}
          aria-label={playing ? 'Stopp' : 'Abspielen'}
        >
          <Icon name={playing ? 'pause' : 'play'} />
        </button>
        <div className="flex h-10 flex-1 items-center gap-[2px]">
          {bars.map((b, i) => (
            <span
              key={i}
              className={`w-full rounded-sm ${playing && i / bars.length <= shown / content.lines.length ? 'bg-blood-400' : 'bg-ink-600'}`}
              style={{ height: `${b}%` }}
            />
          ))}
        </div>
        <span className="font-mono text-xs text-ink-400">{content.duration}</span>
      </div>
      {content.recordedAt && <div className="mt-2 text-xs text-ink-400">Aufgezeichnet: {content.recordedAt}</div>}
      <div className="mt-3 space-y-1 font-typewriter text-sm">
        {content.lines.slice(0, shown).map((l) => (
          <button key={l.id} type="button" onClick={() => onSelect(l.id)} className={`flex w-full gap-3 rounded px-2 py-1 text-left hover:bg-ink-700 ${itemClass(l.id)}`}>
            <span className="shrink-0 font-mono text-xs text-ink-400">{l.t}</span>
            <span>
              <span className="text-brass-300">{l.speaker}:</span> {l.text}
            </span>
          </button>
        ))}
      </div>
      <div className="mt-2 text-[11px] text-ink-500">Transkript der Aufnahme. Tippe auf eine Zeile, um sie zu markieren.</div>
    </div>
  );
}
