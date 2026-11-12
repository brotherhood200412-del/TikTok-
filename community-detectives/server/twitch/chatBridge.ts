/**
 * Verbindet den Twitch-Chat eines Streamers mit seiner laufenden Ermittlung.
 * Eingehend: EventSub channel.chat.message → Chatbefehle.
 * Ausgehend: Helix "Send Chat Message" mit Warteschlange und Drosselung.
 */
import { config } from '../config.js';
import { prisma } from '../db.js';
import { matchName, matchTeam, parseChatCommand } from '../game/commands.js';
import type { SessionManager } from '../game/manager.js';
import { ActionError, type LiveSession } from '../game/session.js';
import { Cooldown, RateLimiter } from '../security/rateLimit.js';
import { HelixClient } from './api.js';
import { EventSubClient, type ChatMessageEvent, type EventSubStatus } from './eventsub.js';

interface Conn {
  streamerId: string;
  broadcasterId: string;
  client: EventSubClient;
  helix: HelixClient;
}

export interface ChatStatus {
  enabled: boolean;
  connected: boolean;
  status: EventSubStatus | 'disabled' | 'not_linked';
  lastError: string | null;
}

export class ChatBridge {
  private conns = new Map<string, Conn>();
  private queues = new Map<string, { items: string[]; timer: NodeJS.Timeout | null }>();
  private userLimiter = new RateLimiter(3, 1 / 1.5);
  private cooldown = new Cooldown();
  private joinBatch = new Map<string, { names: string[]; timer: NodeJS.Timeout | null }>();
  /** Für den lokalen Chat-Simulator: ausgehende Bot-Nachrichten. */
  onBotMessage: (streamerId: string, text: string) => void = () => {};
  onStatus: (streamerId: string, status: ChatStatus) => void = () => {};

  constructor(private readonly manager: SessionManager) {}

  status(streamerId: string, linked: boolean): ChatStatus {
    if (!config.twitchEnabled) return { enabled: false, connected: false, status: 'disabled', lastError: null };
    if (!linked) return { enabled: true, connected: false, status: 'not_linked', lastError: null };
    const c = this.conns.get(streamerId);
    return { enabled: true, connected: c?.client.status === 'connected', status: c?.client.status ?? 'idle', lastError: c?.client.lastError ?? null };
  }

  /** Startet die Chat-Anbindung, falls Twitch konfiguriert und verbunden ist. */
  async ensure(streamerId: string) {
    if (!config.twitchEnabled || this.conns.has(streamerId)) return;
    const streamer = await prisma.streamer.findUnique({ where: { id: streamerId }, include: { token: true } });
    if (!streamer?.twitchUserId || !streamer.token) return;
    const helix = new HelixClient(streamerId);
    const broadcasterId = streamer.twitchUserId;
    const client = new EventSubClient({
      url: config.TWITCH_EVENTSUB_WS_URL,
      subscribe: async (sessionId) => {
        await helix.subscribeChat(sessionId, broadcasterId, broadcasterId);
      },
      log: (m) => console.log(`[eventsub:${streamer.login}] ${m}`),
    });
    client.on('chat', (e: ChatMessageEvent) => void this.onChat(streamerId, e));
    client.on('status', () => this.onStatus(streamerId, this.status(streamerId, true)));
    this.conns.set(streamerId, { streamerId, broadcasterId, client, helix });
    client.start();
  }

  stop(streamerId: string) {
    const c = this.conns.get(streamerId);
    c?.client.stop();
    this.conns.delete(streamerId);
  }

  stopAll() {
    for (const id of [...this.conns.keys()]) this.stop(id);
  }

  async restart(streamerId: string) {
    this.stop(streamerId);
    await this.ensure(streamerId);
  }

  /* ------------------------------ Ausgehend ------------------------------ */

  say(session: LiveSession, text: string) {
    const sid = session.streamerId;
    const q = this.queues.get(sid) ?? { items: [], timer: null };
    this.queues.set(sid, q);
    q.items.push(text.slice(0, 480));
    // Bei Stau ältere Meldungen verwerfen statt den Chat zu fluten.
    if (q.items.length > 6) q.items.splice(0, q.items.length - 6);
    if (!q.timer) this.flush(sid);
  }

  private flush(streamerId: string) {
    const q = this.queues.get(streamerId);
    if (!q) return;
    const next = q.items.shift();
    if (!next) {
      q.timer = null;
      return;
    }
    this.onBotMessage(streamerId, next);
    const c = this.conns.get(streamerId);
    if (c && c.client.status === 'connected') {
      c.helix.sendChatMessage(c.broadcasterId, c.broadcasterId, next).catch((e) => console.error('[chat] Senden fehlgeschlagen:', e.message));
    }
    q.timer = setTimeout(() => this.flush(streamerId), 2000);
  }

  /* ------------------------------ Eingehend ------------------------------ */

  private async onChat(streamerId: string, e: ChatMessageEvent) {
    const session = this.manager.activeForStreamer(streamerId);
    if (!session) return;
    await this.handle(session, e);
  }

  /** Verarbeitet eine Chatnachricht. Wird auch vom lokalen Chat-Simulator genutzt. */
  async handle(session: LiveSession, e: Pick<ChatMessageEvent, 'userId' | 'userLogin' | 'userName' | 'text'>): Promise<string | null> {
    if (config.botIgnore.has(e.userLogin.toLowerCase())) return null;
    const cmd = parseChatCommand(e.text, { bareNumbers: session.settings.bareNumberVotes && !!session.vote });
    if (!cmd) return null;
    if (!this.userLimiter.take(`${session.id}:${e.userId}`)) return null;
    const status = session.state.status;
    const reply = (key: string, ms: number, text: string) => {
      if (this.cooldown.ready(`${session.id}:${key}`, ms)) this.say(session, text);
      return text;
    };
    try {
      const p = await session.join({ twitchUserId: e.userId, login: e.userLogin, displayName: e.userName, source: 'chat' });
      const url = `${config.PUBLIC_URL.replace(/\/$/, '')}/play/${session.joinCode}`;
      switch (cmd.cmd) {
        case 'join':
          this.batchJoin(session, p.displayName);
          return 'joined';
        case 'vote':
          session.castVote(p.id, cmd.option - 1);
          return 'voted';
        case 'hint': {
          const n = session.requestHint(p.id);
          return reply('hint', 30_000, `💡 ${n}/${session.settings.hintRequestThreshold} Ermittler bitten um einen Hinweis. Die Spielleitung entscheidet.`);
        }
        case 'suspects': {
          const view = session.publicView();
          const list = view.characters.filter((c) => c.role === 'suspect');
          return reply('suspects', 30_000, `🕵️ Verdächtige: ${list.map((c, i) => `${i + 1}) ${c.name} (${c.occupation})`).join(' · ')}`);
        }
        case 'evidence': {
          const view = session.publicView();
          if (cmd.index) {
            const ev = view.evidence[cmd.index - 1];
            if (!ev) return reply(`ev:none`, 15_000, `Es gibt aktuell ${view.evidence.length} Beweismittel. Alle Details: ${url}`);
            return reply(`ev:${ev.id}`, 20_000, `📁 Beweis ${cmd.index}: ${ev.title} – ${ev.summary}`);
          }
          return reply('evidence', 30_000, `📁 ${view.evidence.length} Beweismittel freigeschaltet: ${view.evidence.slice(0, 8).map((x, i) => `${i + 1}) ${x.title}`).join(' · ')} → !beweis <Nr>`);
        }
        case 'theory': {
          const view = session.publicView();
          const suspect = matchName(view.characters.filter((c) => c.role === 'suspect'), cmd.suspect);
          if (!suspect) return reply(`theory:unknown`, 20_000, `@${e.userName} Wen meinst du? !verdächtige zeigt alle Namen.`);
          const text = cmd.text.length >= 10 ? cmd.text : `${p.displayName} hält ${suspect.name} für verdächtig.${cmd.text ? ' ' + cmd.text : ''}`;
          await session.submitTheory(p.id, suspect.id, text, []);
          return 'theory';
        }
        case 'team': {
          const team = matchTeam(cmd.team);
          if (!team) return reply('team:help', 30_000, 'Teams: Spurensicherung, Analyse, Verhör, Archiv → !team <Name>');
          await session.setTeam(p.id, team);
          return 'team';
        }
        case 'answer': {
          if (status !== 'active' && status !== 'finale') return null;
          const pid = session.activePuzzleId();
          if (!pid) return reply('answer:none', 30_000, `🧩 Welches Rätsel? Lösungen bitte auf ${url} eingeben.`);
          const res = await session.answer(p.id, pid, cmd.answer);
          return res.ok ? 'solved' : 'wrong';
        }
        case 'points': {
          const rank = session.rank(p.id);
          return reply(`points:${p.id}`, 30_000, `@${e.userName} ${p.points} Punkte${rank ? ` · Platz ${rank}` : ''}${p.team ? ` · Team ${p.team}` : ''}`);
        }
        case 'case':
          return reply('case', 30_000, `🗂️ ${session.def.title} – ${session.def.tagline} Ermittle mit: ${url} (Code ${session.joinCode})`);
        case 'help':
          return reply('help', 60_000, 'Befehle: !ermitteln · !a <Nr> · !verdächtige · !beweis <Nr> · !theorie <Name> <Begründung> · !lösung <Antwort> · !hinweis · !team <Name> · !punkte · !fall');
      }
    } catch (err) {
      if (err instanceof ActionError) return `error:${err.code}`;
      console.error('[chat]', err);
    }
    return null;
  }

  private batchJoin(session: LiveSession, name: string) {
    const b = this.joinBatch.get(session.id) ?? { names: [], timer: null };
    this.joinBatch.set(session.id, b);
    if (!b.names.includes(name)) b.names.push(name);
    if (!b.timer) {
      b.timer = setTimeout(() => {
        const names = b.names.splice(0);
        b.timer = null;
        if (names.length && session.settings.chatReplies) {
          const shown = names.slice(0, 8).join(', ');
          this.say(session, `🕵️ Willkommen im Ermittlerteam: ${shown}${names.length > 8 ? ` und ${names.length - 8} weitere` : ''}!`);
        }
      }, 10_000);
    }
  }
}
