import { describe, expect, it } from 'vitest';
import { matchName, matchTeam, parseChatCommand } from '../server/game/commands.js';
import { Cooldown, RateLimiter } from '../server/security/rateLimit.js';

describe('Chatbefehle', () => {
  it('erkennt alle deutschen Befehle inkl. Aliasse', () => {
    expect(parseChatCommand('!ermitteln')).toEqual({ cmd: 'join' });
    expect(parseChatCommand('!hinweis')).toEqual({ cmd: 'hint' });
    expect(parseChatCommand('!verdächtige')).toEqual({ cmd: 'suspects' });
    expect(parseChatCommand('!Verdaechtige')).toEqual({ cmd: 'suspects' });
    expect(parseChatCommand('!beweis 3')).toEqual({ cmd: 'evidence', index: 3 });
    expect(parseChatCommand('!beweis')).toEqual({ cmd: 'evidence', index: undefined });
    expect(parseChatCommand('!abstimmen 2')).toEqual({ cmd: 'vote', option: 2 });
    expect(parseChatCommand('!a 1')).toEqual({ cmd: 'vote', option: 1 });
    expect(parseChatCommand('!team Analyse')).toEqual({ cmd: 'team', team: 'analyse' });
    expect(parseChatCommand('!theorie @Wendt Die Splitter in der Schürze')).toEqual({ cmd: 'theory', suspect: 'Wendt', text: 'Die Splitter in der Schürze' });
    expect(parseChatCommand('!lösung K-14')).toEqual({ cmd: 'answer', answer: 'K-14' });
    expect(parseChatCommand('!punkte')).toEqual({ cmd: 'points' });
  });
  it('ignoriert normale Nachrichten und ungültige Eingaben', () => {
    expect(parseChatCommand('hallo zusammen')).toBeNull();
    expect(parseChatCommand('!a')).toBeNull();
    expect(parseChatCommand('!a 99')).toBeNull();
    expect(parseChatCommand('!unbekannt')).toBeNull();
    expect(parseChatCommand('!theorie')).toBeNull();
  });
  it('bloße Zahlen zählen nur, wenn erlaubt', () => {
    expect(parseChatCommand('2', { bareNumbers: true })).toEqual({ cmd: 'vote', option: 2 });
    expect(parseChatCommand('2', { bareNumbers: false })).toBeNull();
    expect(parseChatCommand('2024', { bareNumbers: true })).toBeNull();
  });
  it('findet Personen per Teilname und Teams per Präfix', () => {
    const list = [
      { id: 'brandauer', name: 'Dr. Ilse Brandauer' },
      { id: 'wendt', name: 'Jonas Wendt' },
    ];
    expect(matchName(list, 'wendt')?.id).toBe('wendt');
    expect(matchName(list, 'Brandauer')?.id).toBe('brandauer');
    expect(matchName(list, 'ilse')?.id).toBe('brandauer');
    expect(matchName(list, 'xy')).toBeUndefined();
    expect(matchTeam('Verhör')).toBe('verhoer');
    expect(matchTeam('spuri')).toBe('spurensicherung');
    expect(matchTeam('quatsch')).toBeNull();
  });
});

describe('Ratenbegrenzung', () => {
  it('Token-Bucket begrenzt und füllt sich wieder auf', () => {
    const rl = new RateLimiter(3, 1);
    const t = 1000;
    expect([rl.take('u', 1, t), rl.take('u', 1, t), rl.take('u', 1, t), rl.take('u', 1, t)]).toEqual([true, true, true, false]);
    expect(rl.retryAfter('u', 1, t)).toBe(1);
    expect(rl.take('u', 1, t + 1000)).toBe(true);
    expect(rl.take('other', 1, t)).toBe(true);
  });
  it('Cooldown verhindert Wiederholungen innerhalb der Frist', () => {
    const c = new Cooldown();
    expect(c.ready('k', 1000, 0)).toBe(true);
    expect(c.ready('k', 1000, 500)).toBe(false);
    expect(c.ready('k', 1000, 1001)).toBe(true);
  });
});
