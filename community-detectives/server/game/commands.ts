/**
 * Parser für Twitch-Chatbefehle. Rein funktional und damit gut testbar.
 */
export type ChatCommand =
  | { cmd: 'join' }
  | { cmd: 'hint' }
  | { cmd: 'suspects' }
  | { cmd: 'evidence'; index?: number }
  | { cmd: 'theory'; suspect: string; text: string }
  | { cmd: 'vote'; option: number }
  | { cmd: 'team'; team: string }
  | { cmd: 'answer'; answer: string }
  | { cmd: 'points' }
  | { cmd: 'case' }
  | { cmd: 'help' };

const ALIASES: Record<string, ChatCommand['cmd']> = {
  ermitteln: 'join',
  join: 'join',
  mitmachen: 'join',
  hinweis: 'hint',
  tipp: 'hint',
  verdächtige: 'suspects',
  verdaechtige: 'suspects',
  verdachtige: 'suspects',
  beweis: 'evidence',
  beweise: 'evidence',
  theorie: 'theory',
  abstimmen: 'vote',
  vote: 'vote',
  a: 'vote',
  team: 'team',
  lösung: 'answer',
  loesung: 'answer',
  losung: 'answer',
  code: 'answer',
  antwort: 'answer',
  punkte: 'points',
  fall: 'case',
  hilfe: 'help',
  befehle: 'help',
};

export function parseChatCommand(raw: string, opts: { bareNumbers: boolean } = { bareNumbers: true }): ChatCommand | null {
  const text = raw.trim().replace(/\s+/g, ' ');
  if (!text) return null;
  if (opts.bareNumbers && /^[1-9]$/.test(text)) return { cmd: 'vote', option: Number(text) };
  if (!text.startsWith('!')) return null;
  const [head, ...rest] = text.slice(1).split(' ');
  const cmd = ALIASES[head.toLowerCase()];
  if (!cmd) return null;
  const args = rest.join(' ').trim();
  switch (cmd) {
    case 'vote': {
      const n = Number.parseInt(args, 10);
      return Number.isInteger(n) && n >= 1 && n <= 20 ? { cmd, option: n } : null;
    }
    case 'evidence': {
      const n = Number.parseInt(args, 10);
      return { cmd, index: Number.isInteger(n) && n > 0 ? n : undefined };
    }
    case 'theory': {
      const [suspect, ...why] = rest;
      if (!suspect) return null;
      return { cmd, suspect: suspect.replace(/^@/, ''), text: why.join(' ').slice(0, 280) };
    }
    case 'team':
      return args ? { cmd, team: args.toLowerCase() } : null;
    case 'answer':
      return args ? { cmd, answer: args.slice(0, 120) } : null;
    default:
      return { cmd } as ChatCommand;
  }
}

/** Findet eine verdächtige Person anhand eines (Teil-)Namens. */
export function matchName<T extends { id: string; name: string }>(list: T[], query: string): T | undefined {
  const q = norm(query);
  if (!q) return undefined;
  return (
    list.find((c) => c.id === query.toLowerCase()) ??
    list.find((c) => norm(c.name) === q) ??
    list.find((c) => norm(c.name).split(' ').some((part) => part === q)) ??
    list.find((c) => norm(c.name).includes(q) && q.length >= 3)
  );
}

function norm(s: string) {
  return s
    .toLowerCase()
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/ß/g, 'ss')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/^dr\.?\s+/, '')
    .replace(/[^a-z0-9 ]/g, '')
    .trim();
}

export function matchTeam(q: string) {
  const s = norm(q);
  if (s.startsWith('spur')) return 'spurensicherung';
  if (s.startsWith('ana')) return 'analyse';
  if (s.startsWith('verh')) return 'verhoer';
  if (s.startsWith('arch')) return 'archiv';
  return null;
}
