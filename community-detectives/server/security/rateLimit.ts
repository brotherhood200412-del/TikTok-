/**
 * Token-Bucket-Ratenbegrenzung (im Speicher). Schützt vor Spam, Brute-Force
 * bei Rätseln und Punkte-Farming. Einträge verfallen automatisch.
 */
export class RateLimiter {
  private buckets = new Map<string, { tokens: number; updated: number }>();
  constructor(
    private readonly capacity: number,
    private readonly refillPerSec: number,
  ) {}

  take(key: string, cost = 1, now = Date.now()): boolean {
    let b = this.buckets.get(key);
    if (!b) {
      b = { tokens: this.capacity, updated: now };
      this.buckets.set(key, b);
    }
    b.tokens = Math.min(this.capacity, b.tokens + ((now - b.updated) / 1000) * this.refillPerSec);
    b.updated = now;
    if (b.tokens < cost) return false;
    b.tokens -= cost;
    if (this.buckets.size > 50_000) this.sweep(now);
    return true;
  }

  /** Sekunden bis wieder ein Token verfügbar ist. */
  retryAfter(key: string, cost = 1, now = Date.now()): number {
    const b = this.buckets.get(key);
    if (!b) return 0;
    const tokens = Math.min(this.capacity, b.tokens + ((now - b.updated) / 1000) * this.refillPerSec);
    return tokens >= cost ? 0 : Math.ceil((cost - tokens) / this.refillPerSec);
  }

  sweep(now = Date.now()) {
    const full = (this.capacity / this.refillPerSec) * 1000;
    for (const [k, b] of this.buckets) if (now - b.updated > full) this.buckets.delete(k);
  }
}

/** Einfache Cooldowns pro Schlüssel (z. B. Chat-Antworten des Bots). */
export class Cooldown {
  private until = new Map<string, number>();
  ready(key: string, ms: number, now = Date.now()) {
    const u = this.until.get(key) ?? 0;
    if (now < u) return false;
    this.until.set(key, now + ms);
    return true;
  }
}
